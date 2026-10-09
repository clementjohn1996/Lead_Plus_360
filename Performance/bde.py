"""BDE target tracking, colour-coded achievement, PIP / appraisal rules.

Every rule lives here and is shared by the dashboard, profile, calendar, signals,
management command, PIP and appraisal screens.

Revenue source of truth: CRM leads that are currently in stage "Won", owned by the
BDE. Value = Deal.value when a deal exists, otherwise Lead.estimated_value. The won
date is the latest time the lead moved to "won" (falling back to updated_at). A lead
that later leaves "won" (cancelled / refunded) stops counting automatically, and each
lead counts exactly once (no duplicates).
"""
import calendar
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal

from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from HR.models import Employee
from LeadManager.models import Lead

from .models import (
    Appraisal, BDEConfig, BDETarget, ImprovementPlan, MonthlyPerformance,
    PerformanceAlert, PerformanceAudit,
)

BDE_ROLE = "bd_executive"
COLOUR_LABELS = {"red": "Below expectation", "yellow": "Developing", "green": "Strong"}
STATUS_LABELS = dict(MonthlyPerformance.STATUSES)
HISTORY_MONTHS = 12


# ---------------------------------------------------------------- dates
def month_start(d):
    return d.replace(day=1)


def add_months(d, n):
    idx = d.year * 12 + (d.month - 1) + n
    return date(idx // 12, idx % 12 + 1, 1)


def month_end(d):
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def last_completed_month(today=None):
    return add_months(month_start(today or timezone.localdate()), -1)


# ---------------------------------------------------------------- audit
def audit(user, action, employee=None, old="", new=""):
    PerformanceAudit.objects.create(
        user=user if getattr(user, "pk", None) else None, employee=employee,
        action=action, old_value=str(old)[:255], new_value=str(new)[:255],
    )


# ---------------------------------------------------------------- people
def bde_employees(include_exited=False):
    qs = Employee.objects.select_related("user", "department", "manager__user").filter(
        user__profile__role__name=BDE_ROLE, user__profile__role__is_active=True
    )
    return qs if include_exited else qs.exclude(status="exited")


def is_bde(employee):
    return bde_employees(include_exited=True).filter(pk=employee.pk).exists()


def target_for(employee, cfg=None):
    cfg = cfg or BDEConfig.get()
    row = BDETarget.objects.filter(employee=employee).first()
    return row.monthly_target if row else cfg.default_target


def set_target(employee, value, user=None):
    value = Decimal(value)
    if value <= 0:
        raise ValueError("Target must be greater than zero.")
    old = target_for(employee)
    BDETarget.objects.update_or_create(employee=employee, defaults={"monthly_target": value})
    audit(user, "Target changed", employee, old, value)


def prorated_target(employee, month, target):
    """Scale the target when the employee joined or left part-way through the month."""
    days = calendar.monthrange(month.year, month.month)[1]
    start, end = month, month_end(month)
    first = max(start, employee.date_of_joining)
    last = min(end, employee.date_of_exit) if employee.date_of_exit else end
    active = (last - first).days + 1
    if active >= days:
        return target
    if active <= 0:
        return None
    return (target * active / days).quantize(Decimal("0.01"))


def was_active(employee, month):
    if employee.date_of_joining > month_end(month):
        return False
    if employee.date_of_exit and employee.date_of_exit < month:
        return False
    if employee.status == "exited" and not employee.date_of_exit:
        return False
    return True


# ---------------------------------------------------------------- revenue
def won_leads(employee, month):
    start = timezone.make_aware(timezone.datetime.combine(month, timezone.datetime.min.time()))
    end = timezone.make_aware(timezone.datetime.combine(add_months(month, 1), timezone.datetime.min.time()))
    qs = (
        Lead.objects.filter(owner_id=employee.user_id, stage="won")
        .annotate(won_at=Coalesce(
            Max("status_history__changed_at", filter=Q(status_history__to_stage="won")), "updated_at"))
        .filter(won_at__gte=start, won_at__lt=end)
        .select_related("deal")
    )
    rows = []
    for lead in qs:
        deal = getattr(lead, "deal", None)
        if deal and deal.status == "lost":
            continue
        value = deal.value if deal and deal.value > 0 else lead.estimated_value
        rows.append((lead, max(value, Decimal("0"))))
    return rows


def revenue_for(employee, month):
    return sum((v for _, v in won_leads(employee, month)), Decimal("0"))


# ---------------------------------------------------------------- slabs / colours
def slab_for(revenue, target, cfg):
    if revenue <= 0 or target <= 0:
        return 0
    pct = Decimal(revenue) * 100 / Decimal(target)
    slab = (pct * cfg.slabs / 100).to_integral_value(rounding=ROUND_CEILING)
    return int(min(slab, cfg.slabs))


def colour_for_slab(slab, cfg):
    if slab <= cfg.red_max:
        return "red"
    return "yellow" if slab <= cfg.yellow_max else "green"


def segments(record_or_slab, cfg=None):
    """Data for the N-column indicator: each column has its colour and whether it is filled."""
    cfg = cfg or BDEConfig.get()
    slab = record_or_slab if isinstance(record_or_slab, int) else record_or_slab.slab
    return [{"n": n, "colour": colour_for_slab(n, cfg), "filled": n <= slab} for n in range(1, cfg.slabs + 1)]


def category_for(pct, colour):
    text = COLOUR_LABELS[colour]
    return f"{text} - target exceeded" if pct > 100 else text


# ---------------------------------------------------------------- rule engine
def _longest_run(colours, wanted):
    best = run = 0
    for c in colours:
        run = run + 1 if c == wanted else 0
        best = max(best, run)
    return best


def trailing_run(colours, wanted):
    run = 0
    for c in reversed(colours):
        if c != wanted:
            break
        run += 1
    return run


def evaluate(colours, cfg=None):
    """colours: oldest to newest, one entry per month in the window; None = no data.

    Returns (status, reason). The configured completed-month window is a hard minimum; PIP/appraisal rules are evaluated only after enough history exists."""
    cfg = cfg or BDEConfig.get()
    # The four-month policy is a minimum-data gate. A short history must never
    # trigger PIP/appraisal simply because the available months contain a run.
    if not colours or any(c is None for c in colours) or len(colours) < cfg.window_months:
        return "insufficient", "Fewer than %d months of data" % cfg.window_months
    if _longest_run(colours, "red") >= cfg.red_pip_months:
        return "pip", f"{cfg.red_pip_months}+ consecutive Red months"
    if _longest_run(colours, "yellow") >= cfg.yellow_pip_months:
        return "pip", f"{cfg.yellow_pip_months}+ consecutive Yellow months"
    green, yellow = colours.count("green"), colours.count("yellow")
    if green >= cfg.appraisal_green_months:
        return "appraisal", f"{green} Green months"
    if green >= cfg.appraisal_mixed_green and yellow >= cfg.appraisal_mixed_yellow:
        return "appraisal", f"{green} Green + {yellow} Yellow months"
    if yellow >= cfg.neutral_yellow and green >= cfg.neutral_green:
        return "neutral", f"{yellow} Yellow + {green} Green months"
    return ("neutral" if "red" in colours else "on_track"), "No PIP or appraisal pattern"


def window_colours(employee, end_month, cfg=None):
    cfg = cfg or BDEConfig.get()
    months = [add_months(end_month, -i) for i in range(cfg.window_months - 1, -1, -1)]
    recs = {r.month: r for r in MonthlyPerformance.objects.filter(employee=employee, month__in=months)}
    return months, [recs[m].effective_colour if m in recs else None for m in months]


def status_as_of(employee, end_month, cfg=None):
    months, colours = window_colours(employee, end_month, cfg)
    status, reason = evaluate(colours, cfg)
    return status, reason, months, colours


def current_status(employee, today=None, cfg=None):
    return status_as_of(employee, last_completed_month(today), cfg)[:2]


# ---------------------------------------------------------------- recalculation
def recalc_month(employee, month, user=None, today=None):
    """Compute and save one month's record. Keeps remarks, review date and colour override."""
    cfg = BDEConfig.get()
    today = today or timezone.localdate()
    month = month_start(month)
    if not was_active(employee, month):
        return None
    configured_target = prorated_target(employee, month, target_for(employee, cfg))
    if configured_target is None:
        return None
    rec = MonthlyPerformance.objects.filter(employee=employee, month=month).first()
    # Once a month has ended, its target is historical data. Recalculating revenue
    # (for corrections/cancellations) must not silently rewrite the target used for
    # that month after management changes the employee's current target.
    target = rec.target if rec and month < month_start(today) else configured_target
    revenue = revenue_for(employee, month)
    pct = (revenue * 100 / target).quantize(Decimal("0.01"))
    slab = slab_for(revenue, target, cfg)
    colour = colour_for_slab(slab, cfg)
    if rec is None:
        rec = MonthlyPerformance.objects.create(
            employee=employee, month=month, target=target, revenue=revenue,
            achievement_pct=pct, slab=slab, colour=colour,
        )
    rec.target, rec.revenue, rec.achievement_pct, rec.slab, rec.colour = target, revenue, pct, slab, colour
    rec.category = category_for(pct, rec.effective_colour)
    rec.is_closed = month < month_start(today)
    rec.save()
    return rec


def _refresh_statuses(employee, months, cfg):
    open_plan = ImprovementPlan.objects.filter(employee=employee, status__in=ImprovementPlan.OPEN).first()
    for rec in MonthlyPerformance.objects.filter(employee=employee, month__in=months):
        status, _, _, _ = status_as_of(employee, rec.month, cfg)
        rec.status = status
        rec.appraisal_status = "eligible" if status == "appraisal" else ""
        rec.pip_status = open_plan.status if open_plan and status == "pip" else ("pip" if status == "pip" else "")
        rec.save(update_fields=["status", "appraisal_status", "pip_status", "updated_at"])


def _alert(employee, kind, month, message):
    return PerformanceAlert.objects.get_or_create(
        employee=employee, kind=kind, month=month, defaults={"message": message[:255]}
    )[1]


def _label(months, colours, wanted):
    picked = [m for m, c in zip(months, colours) if c == wanted]
    return ", ".join(m.strftime("%b %Y") for m in picked)


def ensure_pip(employee, reason, months_text, user=None, today=None):
    today = today or timezone.localdate()
    if ImprovementPlan.objects.filter(employee=employee, status__in=ImprovementPlan.OPEN).exists():
        return None
    if ImprovementPlan.objects.filter(employee=employee, trigger_months=months_text).exists():
        return None
    plan = ImprovementPlan.objects.create(
        employee=employee, status="draft", auto_created=True, manager=employee.manager,
        trigger_reason=reason, trigger_months=months_text, duration_days=60,
        reason=f"Automatically flagged: {reason} ({months_text}).",
        goals="Agree improvement objectives with the employee.",
        target_requirements=f"Reach at least Slab {BDEConfig.get().red_max + 1} (Yellow) each month.",
        start_date=today, review_date=today + timedelta(days=30), created_by=None,
    )
    audit(user, "PIP created", employee, "", f"{reason} ({months_text})")
    return plan


def ensure_appraisal(employee, months, colours, user=None):
    end = months[-1]
    if Appraisal.objects.filter(employee=employee, period_end=end).exists():
        return None
    recs = MonthlyPerformance.objects.filter(employee=employee, month__in=months)
    pcts = [r.achievement_pct for r in recs]
    appraisal = Appraisal.objects.create(
        employee=employee, period_start=months[0], period_end=end,
        history=" ".join(f"{m:%b}:{(c or 'none')}" for m, c in zip(months, colours)),
        avg_achievement=(sum(pcts) / len(pcts)).quantize(Decimal("0.01")) if pcts else 0,
        green_months=colours.count("green"), yellow_months=colours.count("yellow"), red_months=colours.count("red"),
    )
    audit(user, "Appraisal created", employee, "", f"{months[0]:%b %Y} to {end:%b %Y}")
    return appraisal


def process_employee(employee, today=None, user=None):
    """Create alerts, PIPs and appraisals from the latest completed months. Idempotent."""
    cfg = BDEConfig.get()
    today = today or timezone.localdate()
    last = last_completed_month(today)
    status, reason, months, colours = status_as_of(employee, last, cfg)
    name = employee.full_name

    red_run, yellow_run = trailing_run(colours, "red"), trailing_run(colours, "yellow")
    if red_run == 1:
        _alert(employee, "first_red", last, f"{name}: first Red month ({last:%b %Y}).")
    if red_run >= cfg.red_pip_months:
        _alert(employee, "pip_red", last, f"{name}: {red_run} consecutive Red months - PIP.")
    if yellow_run == cfg.yellow_pip_months - 1:
        _alert(employee, "third_yellow", last, f"{name}: {yellow_run} consecutive Yellow months.")
    if yellow_run >= cfg.yellow_pip_months:
        _alert(employee, "pip_yellow", last, f"{name}: {yellow_run} consecutive Yellow months - PIP.")

    if status == "pip":
        wanted = "red" if _longest_run(colours, "red") >= cfg.red_pip_months else "yellow"
        ensure_pip(employee, reason, _label(months, colours, wanted), user, today)
    elif status == "appraisal":
        if ensure_appraisal(employee, months, colours, user):
            _alert(employee, "appraisal", last, f"{name}: eligible for appraisal ({reason}).")

    current = MonthlyPerformance.objects.filter(employee=employee, month=month_start(today)).first()
    if current and current.achievement_pct > 100:
        _alert(employee, "target_exceeded", current.month, f"{name} exceeded the target ({current.achievement_pct}%).")
    elif current and current.achievement_pct == 100:
        _alert(employee, "target_hit", current.month, f"{name} achieved the target.")

    rec = MonthlyPerformance.objects.filter(employee=employee, month=last).first()
    if rec and rec.is_closed and not rec.manager_remarks and not rec.review_date:
        _alert(employee, "review_due", last, f"{name}: review {last:%b %Y} performance.")
    if ImprovementPlan.objects.filter(
        employee=employee, status__in=("active", "extended", "under_review"), review_date__lte=today
    ).exists():
        _alert(employee, "pip_review_due", month_start(today), f"{name}: PIP review is due.")

    _refresh_statuses(employee, months + [month_start(today)], cfg)
    return status


def sync_employee(employee, today=None, user=None, history=HISTORY_MONTHS):
    """Recalculate recent months (including the current one) and apply the rules."""
    today = today or timezone.localdate()
    cur = month_start(today)
    first = max(add_months(cur, -(history - 1)), month_start(employee.date_of_joining))
    month = first
    while month <= cur:
        recalc_month(employee, month, user, today)
        month = add_months(month, 1)
    return process_employee(employee, today, user)


def recalc_for_lead(lead):
    """Called when a lead/deal changes; cheap no-op unless a BDE's won revenue is affected."""
    if not lead.owner_id:
        return
    won_before = lead.stage == "won" or lead.status_history.filter(to_stage="won").exists()
    if not won_before:
        return
    employee = bde_employees().filter(user_id=lead.owner_id).first()
    if employee:
        today = timezone.localdate()
        won_at = lead.status_history.filter(to_stage="won").aggregate(m=Max("changed_at"))["m"]
        months = {month_start(today)}
        if won_at:
            months.add(month_start(timezone.localtime(won_at).date()))
        for m in months:
            recalc_month(employee, m, None, today)
        process_employee(employee, today)


def run_monthly(today=None, user=None):
    """Scheduled job: finalise completed months and evaluate every BDE."""
    count = 0
    for employee in bde_employees():
        sync_employee(employee, today, user)
        count += 1
    audit(user, "Monthly performance calculated", None, "", f"{count} BDEs")
    return count


def ensure_up_to_date(today=None):
    """Lazy catch-up for both the current month and the latest completed month."""
    today = today or timezone.localdate()
    current = month_start(today)
    last = last_completed_month(today)
    for employee in bde_employees():
        months = set(MonthlyPerformance.objects.filter(
            employee=employee, month__in=(current, last)
        ).values_list("month", flat=True))
        if current not in months or (employee.date_of_joining <= month_end(last) and last not in months):
            sync_employee(employee, today)


# ---------------------------------------------------------------- read models
def employee_summary(employee, today=None, cfg=None):
    cfg = cfg or BDEConfig.get()
    today = today or timezone.localdate()
    status, reason = current_status(employee, today, cfg)
    rec = MonthlyPerformance.objects.filter(employee=employee, month=month_start(today)).first()
    return {
        "employee": employee, "record": rec, "status": status, "status_label": STATUS_LABELS[status],
        "reason": reason, "segments": segments(rec, cfg) if rec else segments(0, cfg),
        "open_pip": ImprovementPlan.objects.filter(employee=employee, status__in=ImprovementPlan.OPEN).first(),
    }


def dashboard(employees, today=None):
    cfg = BDEConfig.get()
    rows = [employee_summary(e, today, cfg) for e in employees]
    recs = [r["record"] for r in rows if r["record"]]
    target = sum((r.target for r in recs), Decimal("0"))
    revenue = sum((r.revenue for r in recs), Decimal("0"))
    counts = {k: 0 for k, _ in MonthlyPerformance.STATUSES}
    for r in rows:
        counts[r["status"]] += 1
    rows.sort(key=lambda r: r["record"].achievement_pct if r["record"] else Decimal("-1"), reverse=True)
    return {
        "rows": rows, "total": len(rows), "counts": counts,
        "on_target": sum(1 for r in recs if r.achievement_pct >= 100),
        "below": sum(1 for r in recs if r.achievement_pct < 100),
        "target": target, "revenue": revenue,
        "pct": (revenue * 100 / target).quantize(Decimal("0.1")) if target else Decimal("0"),
    }


def calendar_rows(employees, year):
    months = [date(year, m, 1) for m in range(1, 13)]
    recs = {(r.employee_id, r.month): r for r in
            MonthlyPerformance.objects.filter(employee__in=employees, month__year=year)}
    return months, [{
        "employee": e, "cells": [recs.get((e.pk, m)) for m in months],
    } for e in employees]

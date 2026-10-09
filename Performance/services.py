"""Performance scoring: automatic metrics from system data plus manual KPI entries."""
from calendar import monthrange
from datetime import date, timedelta

from django.conf import settings
from django.db.models import F, Q, Sum
from django.utils import timezone

from HR.models import Employee

from .models import KPI, KPIEntry

RATINGS = [(90, "Outstanding", "excellent"), (75, "Strong", "good"), (60, "On track", "ok"), (0, "Needs attention", "low")]


def month_bounds(month):
    first = month.replace(day=1)
    return first, first.replace(day=monthrange(first.year, first.month)[1])


def rating(score):
    if score is None:
        return "No data yet", "none"
    for floor, label, css in RATINGS:
        if score >= floor:
            return label, css
    return RATINGS[-1][1], RATINGS[-1][2]


def _elapsed_workdays(first, last):
    end = min(last, timezone.localdate())
    off = set(settings.WEEKLY_OFF_DAYS)
    day, count = first, 0
    while day <= end:
        if day.weekday() not in off:
            count += 1
        day += timedelta(days=1)
    return count


def _leads_won_qs(user, first, last):
    from LeadManager.models import Lead

    return Lead.objects.filter(
        owner=user, status_history__to_stage="won",
        status_history__changed_at__date__range=(first, last),
    ).distinct()


def _m_leads_created(emp, first, last):
    from LeadManager.models import Lead

    return Lead.objects.filter(owner=emp.user, created_at__date__range=(first, last)).count()


def _m_leads_won(emp, first, last):
    return _leads_won_qs(emp.user, first, last).count()


def _m_revenue_won(emp, first, last):
    return float(_leads_won_qs(emp.user, first, last).aggregate(v=Sum("estimated_value"))["v"] or 0)


def _m_activities(emp, first, last):
    from LeadManager.models import Activity

    return Activity.objects.filter(
        created_by=emp.user, created_at__date__range=(first, last)
    ).exclude(activity_type="status").count()


def _done_tasks(emp, first, last):
    from LeadManager.models import Task

    return Task.objects.filter(assigned_to=emp.user, status="done", updated_at__date__range=(first, last))


def _m_tasks_completed(emp, first, last):
    return _done_tasks(emp, first, last).count()


def _m_tasks_on_time(emp, first, last):
    qs = _done_tasks(emp, first, last)
    total = qs.count()
    if not total:
        return None
    return round(100 * qs.filter(updated_at__lte=F("due_at")).count() / total, 1)


def _m_followups(emp, first, last):
    from LeadManager.models import FollowUpSchedule

    return FollowUpSchedule.objects.filter(
        assigned_to=emp.user, status="completed", completed_at__date__range=(first, last)
    ).count()


def _m_work_assigned(emp, first, last):
    from Delivery.models import WorkAssignment
    return WorkAssignment.objects.filter(employee=emp.user, created_at__date__range=(first, last)).count()


def _m_work_completed(emp, first, last):
    from Delivery.models import WorkAssignment
    return WorkAssignment.objects.filter(employee=emp.user, status="completed", completed_at__date__range=(first, last)).count()


def _m_work_on_time(emp, first, last):
    from Delivery.models import WorkAssignment
    qs = WorkAssignment.objects.filter(employee=emp.user, status="completed", completed_at__date__range=(first, last))
    total = qs.count()
    if not total:
        return None
    return round(100 * qs.filter(completed_at__date__lte=F("due_date")).count() / total, 1)


def _m_work_completion_rate(emp, first, last):
    from Delivery.models import WorkAssignment
    total = WorkAssignment.objects.filter(employee=emp.user, created_at__date__range=(first, last)).count()
    if not total:
        return None
    done = WorkAssignment.objects.filter(employee=emp.user, status="completed", created_at__date__range=(first, last)).count()
    return round(100 * done / total, 1)


def _m_handovers(emp, first, last):
    from LeadManager.models import ServiceHandover

    return ServiceHandover.objects.filter(
        accepted_by=emp.user, accepted_at__date__range=(first, last)
    ).count()


def _attendance(emp, first, last):
    from Attendance.models import AttendanceRecord

    return AttendanceRecord.objects.filter(employee=emp, date__range=(first, last), check_in__isnull=False)


def _m_attendance_rate(emp, first, last):
    workdays = _elapsed_workdays(max(first, emp.date_of_joining), last)
    if not workdays:
        return None
    recs = _attendance(emp, first, last)
    attended = recs.exclude(status="half_day").count() + 0.5 * recs.filter(status="half_day").count()
    return round(min(100.0, 100 * attended / workdays), 1)


def _m_punctuality(emp, first, last):
    recs = _attendance(emp, first, last)
    total = recs.count()
    if not total:
        return None
    return round(100 * recs.exclude(status="late").count() / total, 1)


AUTO_METRICS = {
    "leads_created": _m_leads_created,
    "leads_won": _m_leads_won,
    "revenue_won": _m_revenue_won,
    "activities_logged": _m_activities,
    "tasks_completed": _m_tasks_completed,
    "tasks_on_time_pct": _m_tasks_on_time,
    "followups_completed": _m_followups,
    "work_assigned": _m_work_assigned,
    "work_completed": _m_work_completed,
    "work_on_time_pct": _m_work_on_time,
    "work_completion_rate": _m_work_completion_rate,
    "handovers_accepted": _m_handovers,
    "attendance_rate": _m_attendance_rate,
    "punctuality_pct": _m_punctuality,
}


def applicable_kpis(employee):
    return KPI.objects.filter(is_active=True).filter(
        Q(department__isnull=True) | Q(department_id=employee.department_id)
    )


def achievement(actual, target, higher_is_better=True):
    """Fraction of the target achieved, capped at 1.0. None if it cannot be computed."""
    if actual is None or target is None:
        return None
    actual, target = float(actual), float(target)
    if higher_is_better:
        if target <= 0:
            return None
        return min(actual / target, 1.0)
    if actual <= 0:
        return 1.0
    if target <= 0:
        return 0.0
    return min(target / actual, 1.0)


def employee_score(employee, month):
    first, last = month_bounds(month)
    entries = {e.kpi_id: e for e in KPIEntry.objects.filter(employee=employee, month=first)}
    rows, weighted, weights = [], 0.0, 0
    for kpi in applicable_kpis(employee):
        entry = entries.get(kpi.pk)
        if kpi.auto_key:
            actual = AUTO_METRICS[kpi.auto_key](employee, first, last)
        else:
            actual = float(entry.actual) if entry and entry.actual is not None else None
        target = entry.target if entry and entry.target is not None else kpi.default_target
        ach = achievement(actual, target, kpi.higher_is_better)
        if ach is not None:
            weighted += ach * kpi.weight
            weights += kpi.weight
        rows.append({
            "kpi": kpi, "actual": actual, "target": float(target),
            "percent": round(ach * 100) if ach is not None else None,
        })
    score = round(100 * weighted / weights) if weights else None
    label, css = rating(score)
    return {"employee": employee, "score": score, "label": label, "css": css, "kpis": rows}


def leaderboard(month, department=None, tv_only=False):
    employees = Employee.objects.exclude(status="exited").select_related("user", "department")
    if department:
        employees = employees.filter(department=department)
    if tv_only:
        employees = employees.filter(show_on_tv=True)
    results = [employee_score(e, month) for e in employees]
    results.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), r["employee"].full_name))
    rank = 0
    for r in results:
        if r["score"] is not None:
            rank += 1
            r["rank"] = rank
        else:
            r["rank"] = None
    return results


def trend(employee, months=6, until=None):
    until = (until or timezone.localdate()).replace(day=1)
    points, cursor = [], until
    for _ in range(months):
        points.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    points.reverse()
    return [{"month": m, "score": employee_score(employee, m)["score"]} for m in points]


def parse_month(value, default=None):
    default = default or timezone.localdate().replace(day=1)
    try:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    except (AttributeError, ValueError):
        return default

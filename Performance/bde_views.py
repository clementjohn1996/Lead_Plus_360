import csv
from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Control.permissions import can_manage_team, hr_required, is_hr, permission_required
from HR.models import Employee

from . import bde
from .models import (
    Appraisal, BDEConfig, BDETarget, ImprovementPlan, MonthlyPerformance,
    PerformanceAlert, PerformanceAudit,
)

team_required = permission_required(lambda u: can_manage_team(u) or is_hr(u))


def _own(user):
    return getattr(user, "employee", None)


def is_team_manager(user, employee):
    own = _own(user)
    return bool(own and employee.manager_id == own.pk)


def can_view(user, employee):
    own = _own(user)
    return is_hr(user) or is_team_manager(user, employee) or bool(own and own.pk == employee.pk)


def can_review(user, employee):
    return is_hr(user) or is_team_manager(user, employee)


def scoped_bdes(user):
    qs = bde.bde_employees()
    if is_hr(user):
        return qs
    own = _own(user)
    return qs.filter(manager_id=own.pk) if own else qs.none()


# ------------------------------------------------------------------ dashboard
@team_required
def dashboard(request):
    bde.ensure_up_to_date()
    data = bde.dashboard(scoped_bdes(request.user))
    alerts = PerformanceAlert.objects.filter(employee__in=[r["employee"] for r in data["rows"]],
                                             is_read=False).select_related("employee__user")[:15]
    return render(request, "Performance/bde_dashboard.html", {
        "d": data, "alerts": alerts, "cfg": BDEConfig.get(), "month": timezone.localdate().replace(day=1),
        "is_hr": is_hr(request.user),
    })


@login_required
def profile(request, pk=None):
    if pk is None:
        employee = _own(request.user)
        if not employee or not bde.is_bde(employee):
            raise PermissionDenied
    else:
        employee = get_object_or_404(Employee.objects.select_related("user", "department", "manager__user"), pk=pk)
        if not bde.is_bde(employee) or not can_view(request.user, employee):
            raise PermissionDenied
    cfg = BDEConfig.get()
    if bde.is_bde(employee) and not MonthlyPerformance.objects.filter(employee=employee).exists():
        bde.sync_employee(employee)
    summary = bde.employee_summary(employee, cfg=cfg)
    history = list(MonthlyPerformance.objects.filter(employee=employee).order_by("-month")[:12])
    last_months = [r for r in history if r.is_closed][:cfg.window_months][::-1]
    trend_max = max([float(r.achievement_pct) for r in history] + [100.0])
    trend = [{"rec": r, "height": max(4, round(float(r.achievement_pct) / trend_max * 100))} for r in history[::-1]]
    for row in trend:
        row["segments"] = bde.segments(row["rec"], cfg)
    return render(request, "Performance/bde_profile.html", {
        "emp": employee, "s": summary, "history": history, "window": last_months, "trend": trend,
        "cfg": cfg, "plans": employee.improvement_plans.all(), "appraisals": employee.appraisals.all(),
        "is_bde": bde.is_bde(employee), "target": bde.target_for(employee, cfg),
        "can_review": can_review(request.user, employee), "is_hr": is_hr(request.user),
        "is_self": _own(request.user) and _own(request.user).pk == employee.pk,
    })


@team_required
def calendar_view(request):
    try:
        year = int(request.GET.get("year", timezone.localdate().year))
    except ValueError:
        year = timezone.localdate().year
    employees = list(scoped_bdes(request.user))
    months, rows = bde.calendar_rows(employees, year)
    return render(request, "Performance/bde_calendar.html", {
        "months": months, "rows": rows, "year": year, "prev": year - 1, "next": year + 1,
    })


# ------------------------------------------------------------------ records
@login_required
@require_POST
def record_update(request, pk):
    rec = get_object_or_404(MonthlyPerformance.objects.select_related("employee"), pk=pk)
    emp = rec.employee
    if not can_review(request.user, emp):
        raise PermissionDenied
    remarks = request.POST.get("manager_remarks", "").strip()
    review_raw = request.POST.get("review_date", "")
    review_date = None
    if review_raw:
        try:
            review_date = date.fromisoformat(review_raw)
        except ValueError:
            messages.error(request, "Invalid review date.")
            return redirect("bde_profile", pk=emp.pk)
    rec.manager_remarks, rec.review_date = remarks, review_date
    if is_hr(request.user) and "colour_override" in request.POST:
        new = request.POST.get("colour_override", "")
        if new not in ("", "red", "yellow", "green"):
            raise PermissionDenied
        if new != rec.colour_override:
            bde.audit(request.user, "Performance colour manually adjusted", emp,
                      rec.colour_override or rec.colour, new or "automatic")
            rec.colour_override = new
            rec.category = bde.category_for(rec.achievement_pct, rec.effective_colour)
    rec.save()
    bde.process_employee(emp)
    messages.success(request, f"Saved review for {rec.month:%b %Y}.")
    return redirect("bde_profile", pk=emp.pk)


# ------------------------------------------------------------------ settings
class ConfigForm(forms.ModelForm):
    class Meta:
        model = BDEConfig
        exclude = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control")


@hr_required
def config(request):
    cfg = BDEConfig.get()
    form = ConfigForm(request.POST or None, instance=cfg)
    if request.method == "POST" and request.POST.get("form") == "config" and form.is_valid():
        old = {f: getattr(cfg, f) for f in form.fields}
        new_cfg = form.save()
        changes = [f"{f}: {old[f]} -> {getattr(new_cfg, f)}" for f in form.fields if old[f] != getattr(new_cfg, f)]
        if changes:
            bde.audit(request.user, "Performance rule changed", None, "", "; ".join(changes))
        messages.success(request, "Settings saved. Use Recalculate to apply them to existing months.")
        return redirect("bde_config")
    rows = [{"employee": e, "target": bde.target_for(e, cfg),
             "custom": hasattr(e, "bde_target")} for e in bde.bde_employees()]
    return render(request, "Performance/bde_config.html", {"form": form, "rows": rows, "cfg": cfg})


@hr_required
@require_POST
def target_update(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.POST.get("reset"):
        row = BDETarget.objects.filter(employee=employee).first()
        if row:
            bde.audit(request.user, "Target changed", employee, row.monthly_target, "default")
            row.delete()
        messages.success(request, f"{employee.full_name} now uses the default target.")
    else:
        try:
            bde.set_target(employee, Decimal(request.POST.get("target", "").replace(",", "")), request.user)
            messages.success(request, f"Target updated for {employee.full_name}.")
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a target greater than zero.")
    return redirect("bde_config")


@hr_required
@require_POST
def recalculate(request):
    count = bde.run_monthly(user=request.user)
    messages.success(request, f"Performance recalculated for {count} BDEs.")
    return redirect(request.POST.get("next") or "bde_dashboard")


@hr_required
def audit_log(request):
    return render(request, "Performance/bde_audit.html", {
        "entries": PerformanceAudit.objects.select_related("user", "employee__user")[:300]})


@team_required
@require_POST
def alerts_clear(request):
    PerformanceAlert.objects.filter(employee__in=scoped_bdes(request.user)).update(is_read=True)
    return redirect("bde_dashboard")


@team_required
def export_csv(request):
    cfg = BDEConfig.get()
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="bde-performance.csv"'
    writer = csv.writer(response)
    writer.writerow(["Employee", "Month", "Target", "Revenue", "Achievement %", f"Slab (of {cfg.slabs})",
                     "Colour", "Category", "Status", "Manager remarks", "Review date"])
    recs = MonthlyPerformance.objects.filter(employee__in=scoped_bdes(request.user)).select_related("employee__user")
    for r in recs.order_by("employee_id", "month"):
        writer.writerow([r.employee.full_name, f"{r.month:%Y-%m}", r.target, r.revenue, r.achievement_pct, r.slab,
                         r.effective_colour, r.category, bde.STATUS_LABELS[r.status], r.manager_remarks, r.review_date or ""])
    return response


# ------------------------------------------------------------------ appraisals
class AppraisalForm(forms.ModelForm):
    class Meta:
        model = Appraisal
        fields = ["manager_comments", "strengths", "improvement_areas", "recommended_increment_pct",
                  "recommended_promotion", "decision", "review_date"]
        widgets = {"review_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "manager_comments": forms.Textarea(attrs={"rows": 3}),
                   "strengths": forms.Textarea(attrs={"rows": 3}),
                   "improvement_areas": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, hr=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not hr:
            for name in ("recommended_increment_pct", "recommended_promotion", "decision"):
                del self.fields[name]
        for f in self.fields.values():
            if not isinstance(f.widget, forms.CheckboxInput):
                f.widget.attrs.setdefault("class", "form-control")

    def clean_recommended_increment_pct(self):
        v = self.cleaned_data.get("recommended_increment_pct")
        if v is not None and not 0 <= v <= 100:
            raise forms.ValidationError("Enter a percentage between 0 and 100.")
        return v


@team_required
def appraisal_list(request):
    qs = Appraisal.objects.filter(employee__in=scoped_bdes(request.user)).select_related("employee__user")
    return render(request, "Performance/appraisal_list.html", {"appraisals": qs})


@login_required
def appraisal_detail(request, pk):
    appraisal = get_object_or_404(Appraisal.objects.select_related("employee__user"), pk=pk)
    if not can_view(request.user, appraisal.employee):
        raise PermissionDenied
    editable = can_review(request.user, appraisal.employee)
    form = None
    if editable:
        form = AppraisalForm(request.POST or None, instance=appraisal, hr=is_hr(request.user))
        if request.method == "POST" and form.is_valid():
            old = appraisal.decision
            saved = form.save()
            if "decision" in form.fields and old != saved.decision:
                bde.audit(request.user, "Appraisal decision changed", appraisal.employee, old, saved.decision)
            messages.success(request, "Appraisal saved. No salary or promotion changes were made automatically.")
            return redirect("bde_appraisal", pk=pk)
    return render(request, "Performance/appraisal_detail.html", {"a": appraisal, "form": form})

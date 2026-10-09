from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Control.permissions import hr_required, is_hr, manager_required
from HR.models import Employee
from LeadManager.models import Department

from . import bde, bde_views, services
from .models import KPI, ImprovementPlan, ImprovementUpdate, KPIEntry, TVDisplay, TVPoster


def _month_nav(month):
    prev = (month - timedelta(days=1)).replace(day=1)
    nxt = (month + timedelta(days=32)).replace(day=1)
    current = timezone.localdate().replace(day=1)
    return {"prev": prev.strftime("%Y-%m"), "next": nxt.strftime("%Y-%m") if nxt <= current else None}


def _can_see(user, employee):
    if is_hr(user):
        return True
    own = getattr(user, "employee", None)
    return bool(own and (own.pk == employee.pk or employee.manager_id == own.pk))


@manager_required
def leaderboard(request):
    month = services.parse_month(request.GET.get("month"))
    dept = request.GET.get("department", "")
    department = Department.objects.filter(pk=dept).first() if dept.isdigit() else None
    return render(request, "Performance/leaderboard.html", {
        "results": services.leaderboard(month, department),
        "month": month, "nav": _month_nav(month),
        "departments": Department.objects.all(), "department": department,
    })


@login_required
def employee_performance(request, pk=None):
    if pk is None:
        employee = getattr(request.user, "employee", None)
        if not employee:
            raise PermissionDenied
    else:
        employee = get_object_or_404(Employee.objects.select_related("user", "department"), pk=pk)
        if not _can_see(request.user, employee):
            raise PermissionDenied
    month = services.parse_month(request.GET.get("month"))
    result = services.employee_score(employee, month)
    history = services.trend(employee, 6, month)
    return render(request, "Performance/employee.html", {
        "emp": employee, "result": result, "history": history, "month": month, "nav": _month_nav(month),
        "can_edit": is_hr(request.user) or (getattr(request.user, "employee", None) and employee.manager_id == request.user.employee.pk),
    })


@manager_required
def entries(request, pk):
    employee = get_object_or_404(Employee.objects.select_related("user"), pk=pk)
    own = getattr(request.user, "employee", None)
    if not (is_hr(request.user) or (own and employee.manager_id == own.pk)):
        raise PermissionDenied
    month = services.parse_month(request.GET.get("month") or request.POST.get("month"))
    kpis = [k for k in services.applicable_kpis(employee) if not k.is_auto]
    existing = {e.kpi_id: e for e in KPIEntry.objects.filter(employee=employee, month=month)}
    if request.method == "POST":
        saved = 0
        for kpi in kpis:
            actual, target = request.POST.get(f"actual_{kpi.pk}", "").strip(), request.POST.get(f"target_{kpi.pk}", "").strip()
            try:
                actual_v = forms.DecimalField(max_digits=12, decimal_places=2, required=False).clean(actual)
                target_v = forms.DecimalField(max_digits=12, decimal_places=2, required=False).clean(target)
            except forms.ValidationError:
                messages.error(request, f"Invalid number for {kpi.name}.")
                return redirect(request.path + f"?month={month:%Y-%m}")
            if actual_v is None and target_v is None:
                continue
            KPIEntry.objects.update_or_create(
                employee=employee, kpi=kpi, month=month, defaults={"actual": actual_v, "target": target_v},
            )
            saved += 1
        messages.success(request, f"Saved {saved} KPI entr{'y' if saved == 1 else 'ies'}.")
        return redirect("performance_employee", pk=employee.pk)
    rows = [{"kpi": k, "entry": existing.get(k.pk)} for k in kpis]
    return render(request, "Performance/entries.html", {"emp": employee, "rows": rows, "month": month})


class KPIForm(forms.ModelForm):
    class Meta:
        model = KPI
        fields = ["name", "description", "department", "auto_key", "unit", "weight", "higher_is_better",
                  "default_target", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")


@hr_required
def kpis(request, pk=None):
    instance = get_object_or_404(KPI, pk=pk) if pk else None
    if request.method == "POST":
        form = KPIForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "KPI saved.")
            return redirect("performance_kpis")
    else:
        form = KPIForm(instance=instance)
    return render(request, "Performance/kpis.html", {
        "form": form, "kpis": KPI.objects.select_related("department"), "editing": instance,
    })


class TVPosterForm(forms.ModelForm):
    class Meta:
        model = TVPoster
        fields = ["title", "subtitle", "image", "seconds", "sort_order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["image"].widget.attrs["accept"] = "image/*"

    def clean_seconds(self):
        value = self.cleaned_data["seconds"]
        if not 5 <= value <= 120:
            raise forms.ValidationError("Choose between 5 and 120 seconds.")
        return value


class TVForm(forms.ModelForm):
    class Meta:
        model = TVDisplay
        fields = ["name", "department", "seconds_per_slide"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_seconds_per_slide(self):
        value = self.cleaned_data["seconds_per_slide"]
        if not 5 <= value <= 120:
            raise forms.ValidationError("Choose between 5 and 120 seconds.")
        return value


@hr_required
def tv_manage(request):
    if request.method == "POST":
        form = TVForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "TV display created.")
            return redirect("performance_tv_manage")
    else:
        form = TVForm(initial={"seconds_per_slide": 12})
    poster_form = TVPosterForm(prefix="poster")
    displays = TVDisplay.objects.select_related("department")
    for d in displays:
        d.url = request.build_absolute_uri(f"/tv/{d.token}/")
    posters = TVPoster.objects.all()
    return render(request, "Performance/tv_manage.html", {"form": form, "poster_form": poster_form, "posters": posters, "displays": displays})


@hr_required
@require_POST
def tv_poster_create(request):
    form = TVPosterForm(request.POST, request.FILES, prefix="poster")
    if form.is_valid():
        form.save()
        messages.success(request, "TV poster added to the playlist.")
    return redirect("performance_tv_manage")


@hr_required
@require_POST
def tv_poster_action(request, pk):
    poster = get_object_or_404(TVPoster, pk=pk)
    action = request.POST.get("action")
    if action == "toggle":
        poster.is_active = not poster.is_active
        poster.save(update_fields=["is_active"])
    elif action == "delete":
        poster.delete()
        messages.success(request, "TV poster deleted.")
    return redirect("performance_tv_manage")


@hr_required
@require_POST
def tv_action(request, pk):
    display = get_object_or_404(TVDisplay, pk=pk)
    action = request.POST.get("action")
    if action == "regenerate":
        display.regenerate_token()
        messages.success(request, "New URL generated. The old URL no longer works.")
    elif action == "toggle":
        display.is_active = not display.is_active
        display.save(update_fields=["is_active"])
    elif action == "delete":
        display.delete()
        messages.success(request, "TV display deleted.")
    return redirect("performance_tv_manage")


PIP_THRESHOLD = 60


class PIPForm(forms.ModelForm):
    class Meta:
        model = ImprovementPlan
        fields = ["employee", "manager", "trigger_reason", "trigger_months", "reason", "goals", "target_requirements",
                  "start_date", "review_date", "duration_days", "start_score", "target_score"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "review_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "reason": forms.Textarea(attrs={"rows": 3}), "target_requirements": forms.Textarea(attrs={"rows": 2}), "goals": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.exclude(status="exited")
        self.fields["manager"].queryset = Employee.objects.exclude(status="exited")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        data = super().clean()
        if data.get("start_date") and data.get("review_date") and data["review_date"] < data["start_date"]:
            self.add_error("review_date", "Review date must be after the start date.")
        return data


@bde_views.team_required
def pip_list(request):
    status = request.GET.get("status", "open")
    employees = bde_views.scoped_bdes(request.user)
    employee_ids = list(employees.values_list("pk", flat=True))
    plans = ImprovementPlan.objects.select_related("employee__user", "employee__department").filter(employee_id__in=employee_ids)
    if status == "open":
        plans = plans.filter(status__in=ImprovementPlan.OPEN)
    elif status != "all":
        plans = plans.filter(status=status)
    month = timezone.localdate().replace(day=1)
    in_pip = set(ImprovementPlan.objects.filter(employee_id__in=employee_ids, status__in=ImprovementPlan.OPEN).values_list("employee_id", flat=True))
    at_risk = [r for r in services.leaderboard(month)
               if r["score"] is not None and r["score"] < PIP_THRESHOLD
               and r["employee"].pk not in in_pip and r["employee"].pk in employee_ids]
    return render(request, "Performance/pip_list.html", {
        "plans": plans, "status": status, "at_risk": at_risk, "threshold": PIP_THRESHOLD,
        "statuses": ImprovementPlan.STATUS, "is_hr": is_hr(request.user),
    })


@hr_required
def pip_create(request):
    initial = {"start_date": timezone.localdate(), "review_date": timezone.localdate() + timedelta(days=30)}
    emp_id = request.GET.get("employee", "")
    if emp_id.isdigit():
        employee = Employee.objects.filter(pk=emp_id).first()
        if employee:
            initial["employee"] = employee
            initial["start_score"] = services.employee_score(employee, timezone.localdate().replace(day=1))["score"]
    form = PIPForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        plan = form.save(commit=False)
        plan.created_by = request.user
        plan.save()
        bde.audit(request.user, "PIP created", plan.employee, "", plan.get_status_display())
        messages.success(request, "Improvement plan created.")
        return redirect("pip_detail", pk=plan.pk)
    return render(request, "Performance/pip_form.html", {"form": form})


@login_required
def pip_detail(request, pk):
    plan = get_object_or_404(ImprovementPlan.objects.select_related("employee__user"), pk=pk)
    if not bde_views.can_review(request.user, plan.employee):
        raise PermissionDenied
    current = services.employee_score(plan.employee, timezone.localdate().replace(day=1))["score"]
    return render(request, "Performance/pip_detail.html", {
        "plan": plan, "current_score": current, "today": timezone.localdate(), "is_hr": is_hr(request.user),
    })


@login_required
@require_POST
def pip_update(request, pk):
    plan = get_object_or_404(ImprovementPlan.objects.select_related("employee"), pk=pk)
    if not bde_views.can_review(request.user, plan.employee):
        raise PermissionDenied
    note = request.POST.get("note", "").strip()
    score = request.POST.get("score", "").strip()
    if not note:
        messages.error(request, "Write a note for the check-in.")
    else:
        ImprovementUpdate.objects.create(
            plan=plan, date=timezone.localdate(), note=note, author=request.user,
            score=int(score) if score.isdigit() and int(score) <= 100 else None,
        )
        bde.audit(request.user, "PIP review added", plan.employee, "", note[:200])
        messages.success(request, "Review added.")
    return redirect("pip_detail", pk=plan.pk)


@hr_required
@require_POST
def pip_close(request, pk):
    plan = get_object_or_404(ImprovementPlan, pk=pk)
    action = request.POST.get("action")
    old_status = plan.status
    if action == "extend":
        raw = request.POST.get("review_date", "")
        try:
            new_date = timezone.datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Choose a valid new review date.")
            return redirect("pip_detail", pk=plan.pk)
        plan.review_date, plan.status = new_date, "extended"
        plan.save(update_fields=["review_date", "status"])
        messages.success(request, "Plan extended.")
    elif action in ("improved", "failed", "cancelled", "closed"):
        plan.status = action
        plan.outcome = request.POST.get("outcome", "").strip()
        plan.closed_at = timezone.now()
        plan.save(update_fields=["status", "outcome", "closed_at"])
        messages.success(request, "Plan closed.")
    elif action in ("activate", "under_review"):
        plan.status = "active" if action == "activate" else "under_review"
        plan.save(update_fields=["status"])
        messages.success(request, f"Plan is now {plan.get_status_display().lower()}.")
    elif action == "reopen":
        plan.status, plan.closed_at = "active", None
        plan.save(update_fields=["status", "closed_at"])
        messages.success(request, "Plan reopened.")
    if plan.status != old_status:
        bde.audit(request.user, "PIP status changed", plan.employee, old_status, plan.status)
    return redirect("pip_detail", pk=plan.pk)


@hr_required
@require_POST
def pip_delete(request, pk):
    get_object_or_404(ImprovementPlan, pk=pk).delete()
    messages.success(request, "Plan deleted.")
    return redirect("pip_list")

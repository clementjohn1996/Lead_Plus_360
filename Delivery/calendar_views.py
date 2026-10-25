from calendar import monthrange
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from Control.permissions import is_admin, role_name
from LeadManager.models import Lead
from .calendar_models import DeliveryPackage, PackageTaskTemplate, DeliveryPlan, DeliveryCalendarTask
from .calendar_forms import DeliveryPlanForm, CalendarTaskForm, QuickTaskForm, BDMReviewForm, PackageForm, PackageTaskTemplateForm

MANAGEMENT_ROLES = {"management", "project_manager", "bd_manager", "hr"}


def can_view_calendar(user):
    return is_admin(user) or role_name(user) in MANAGEMENT_ROLES or role_name(user) in {"bd_executive", "bd_team_lead", "digital_marketing", "graphic_designer", "videographer", "video_editor", "developer"}


def visible_plans(user):
    qs = DeliveryPlan.objects.select_related("lead", "package", "bde", "bdm", "approved_by").prefetch_related("tasks")
    role = role_name(user)
    if is_admin(user) or role in MANAGEMENT_ROLES:
        return qs
    if role in {"bd_executive", "bd_team_lead"}:
        return qs.filter(Q(bde=user) | Q(lead__owner=user) | Q(lead__manager=user)).distinct()
    return qs.filter(tasks__assigned_to=user).distinct()

@login_required
def calendar_dashboard(request):
    if not can_view_calendar(request.user): raise PermissionDenied
    qs = visible_plans(request.user)
    month_raw = request.GET.get("month", "")
    try:
        year, month = [int(x) for x in month_raw.split("-")]
        current = date(year, month, 1)
    except Exception:
        today = timezone.localdate(); current = date(today.year, today.month, 1)
    first_weekday, days = monthrange(current.year, current.month)
    # Monday-first calendar: Python weekday already Monday=0.
    cells = []
    for i in range(first_weekday): cells.append(None)
    tasks = list(DeliveryCalendarTask.objects.filter(plan__in=qs, start_date__year=current.year, start_date__month=current.month).select_related("plan", "plan__lead"))
    by_day = {}
    for task in tasks: by_day.setdefault(task.start_date.day, []).append(task)
    for day in range(1, days + 1): cells.append({"day": day, "date_str": current.replace(day=day).strftime("%Y-%m-%d"), "tasks": by_day.get(day, [])})
    while len(cells) % 7: cells.append(None)
    return render(request, "Delivery/calendar.html", {"plans": qs.order_by("start_date"), "cells": cells, "current": current, "today": timezone.localdate(), "month_prev": (current.replace(day=1)-timedelta(days=1)).strftime("%Y-%m"), "month_next": (current.replace(day=28)+timedelta(days=4)).replace(day=1).strftime("%Y-%m"), "role": role_name(request.user), "is_bdm": role_name(request.user)=="bd_manager" or is_admin(request.user), "reminders": upcoming_reminders(request.user)})

@login_required
def plan_create(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    if not (is_admin(request.user) or request.user == lead.owner or role_name(request.user) in {"bd_executive", "bd_team_lead", "bd_manager", "management"}): raise PermissionDenied
    existing = getattr(lead, "delivery_plan", None)
    if existing: return redirect("delivery_calendar_plan_edit", pk=existing.pk)
    form = DeliveryPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        plan = form.save(commit=False); plan.lead=lead; plan.bde=request.user; plan.package_name=plan.package_name or (plan.package.name if plan.package_id else "Custom package"); plan.save()
        if plan.package_id:
            cursor = plan.start_date
            for tpl in plan.package.task_templates.filter(active=True):
                task_start = cursor
                task_due = task_start + timedelta(days=max(tpl.default_duration_days - 1, 0))
                task_kwargs = dict(plan=plan, template=tpl, task_type=tpl.task_type, title=tpl.title, icon=tpl.icon, gif_url=tpl.gif_url, start_date=task_start, due_date=task_due, final_date=task_due)
                if tpl.task_type == "video":
                    task_kwargs.update(shoot_date=task_start, draft_date=task_start + timedelta(days=max(tpl.default_duration_days // 2, 1)))
                else:
                    task_kwargs.update(draft_date=task_start + timedelta(days=max(tpl.default_duration_days // 2, 1)), launch_date=task_start + timedelta(days=max(tpl.default_duration_days // 2, 1)))
                DeliveryCalendarTask.objects.create(**task_kwargs)
                cursor = task_due + timedelta(days=1)
        messages.success(request, "Delivery calendar created. Add dates to each task and submit it to the BDM.")
        return redirect("delivery_calendar_plan_edit", pk=plan.pk)
    return render(request, "Delivery/calendar_plan_form.html", {"form": form, "lead": lead, "packages": DeliveryPackage.objects.filter(is_active=True).prefetch_related("task_templates")})

@login_required
def plan_edit(request, pk):
    plan = get_object_or_404(DeliveryPlan.objects.select_related("lead", "package", "bde", "bdm"), pk=pk)
    role = role_name(request.user)
    can_edit = is_admin(request.user) or request.user == plan.bde or (role in {"bd_manager", "management"} and plan.status not in {"approved", "in_progress", "completed", "cancelled"})
    if not (can_edit or is_admin(request.user)): raise PermissionDenied
    if request.method == "POST":
        form = DeliveryPlanForm(request.POST, instance=plan)
        if form.is_valid():
            plan = form.save(commit=False); plan.package_name=plan.package_name or (plan.package.name if plan.package_id else "Custom package"); plan.save(); messages.success(request, "Plan details updated."); return redirect("delivery_calendar_plan_edit", pk=pk)
    else: form = DeliveryPlanForm(instance=plan)
    return render(request, "Delivery/calendar_plan_edit.html", {"plan": plan, "form": form, "task_form": CalendarTaskForm(), "review_form": BDMReviewForm(), "can_edit": can_edit, "can_review": is_admin(request.user) or role in {"bd_manager", "management"}})

@login_required
def task_add(request, plan_id):
    plan = get_object_or_404(DeliveryPlan, pk=plan_id)
    if not (is_admin(request.user) or request.user == plan.bde or role_name(request.user) in {"bd_manager", "management"}) or plan.status not in {"draft", "changes_requested"}: raise PermissionDenied
    if request.method == "POST":
        form=CalendarTaskForm(request.POST)
        if form.is_valid():
            task=form.save(commit=False); task.plan=plan; task.save(); messages.success(request, "Calendar task added.")
    return redirect("delivery_calendar_plan_edit", pk=plan_id)

@login_required
def task_edit(request, pk):
    task=get_object_or_404(DeliveryCalendarTask.objects.select_related("plan"), pk=pk); plan=task.plan
    if not (is_admin(request.user) or request.user == plan.bde or role_name(request.user) in {"bd_manager", "management"}) or plan.status not in {"draft", "changes_requested"}: raise PermissionDenied
    form=CalendarTaskForm(request.POST or None, instance=task)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Task schedule updated."); return redirect("delivery_calendar_plan_edit", pk=plan.pk)
    return render(request,"Delivery/calendar_task_form.html",{"form":form,"task":task,"plan":plan})

@login_required
def submit_plan(request, pk):
    plan=get_object_or_404(DeliveryPlan, pk=pk)
    if not (is_admin(request.user) or request.user==plan.bde or role_name(request.user) in {"bd_executive","bd_team_lead"}): raise PermissionDenied
    if request.method!="POST": return redirect("delivery_calendar_plan_edit",pk=pk)
    if not plan.tasks.exists() or plan.tasks.filter(due_date__isnull=True).exists(): messages.error(request,"Every task needs a due/final date before BDM approval."); return redirect("delivery_calendar_plan_edit",pk=pk)
    plan.status="pending_approval"; plan.submitted_at=timezone.now(); plan.bdm = plan.bdm or __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.filter(profile__role__name="bd_manager", is_active=True).first(); plan.save(update_fields=["status","submitted_at","bdm","updated_at"]); messages.success(request,"Plan submitted to BDM for approval."); return redirect("delivery_calendar_plan_edit",pk=pk)

@login_required
def review_plan(request, pk):
    plan=get_object_or_404(DeliveryPlan,pk=pk)
    if not (is_admin(request.user) or role_name(request.user) in {"bd_manager","management"}): raise PermissionDenied
    form=BDMReviewForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        decision=form.cleaned_data["decision"]; plan.status=decision; plan.bdm_notes=form.cleaned_data["notes"]; plan.approved_by=request.user if decision=="approved" else None; plan.approved_at=timezone.now() if decision=="approved" else None; plan.save(update_fields=["status","bdm_notes","approved_by","approved_at","updated_at"]); messages.success(request, "Plan approved and released to delivery." if decision=="approved" else "Changes requested from BDE.")
    return redirect("delivery_calendar_plan_edit",pk=pk)

@login_required
def package_manager(request):
    if not (is_admin(request.user) or role_name(request.user) in {"management","bd_manager","bd_executive","bd_team_lead"}): raise PermissionDenied
    packages=DeliveryPackage.objects.prefetch_related("task_templates")
    return render(request,"Delivery/packages.html",{"packages":packages,"form":PackageForm()})

@login_required
def package_create(request):
    if not (is_admin(request.user) or role_name(request.user) in {"management","bd_manager","bd_executive","bd_team_lead"}): raise PermissionDenied
    if request.method=="POST":
        form=PackageForm(request.POST)
        if form.is_valid(): p=form.save(commit=False); p.created_by=request.user; p.save(); messages.success(request,"Package created.")
    return redirect("delivery_packages")

@login_required
def package_task_create(request, package_id):
    if not (is_admin(request.user) or role_name(request.user) in {"management","bd_manager","bd_executive","bd_team_lead"}): raise PermissionDenied
    p=get_object_or_404(DeliveryPackage,pk=package_id)
    if request.method=="POST":
        form=PackageTaskTemplateForm(request.POST)
        if form.is_valid(): t=form.save(commit=False); t.package=p; t.save(); messages.success(request,"Package task added.")
    return redirect("delivery_packages")


def upcoming_reminders(user):
    """Return tasks with unsent reminders due today or earlier, visible to the user."""
    plans = visible_plans(user)
    today = timezone.localdate()
    tasks = DeliveryCalendarTask.objects.filter(
        plan__in=plans, reminder_enabled=True, reminder_sent=False,
        start_date__gt=today,
    ).select_related("plan", "plan__lead")
    due = [t for t in tasks if t.reminder_date and t.reminder_date <= today]
    return due


@login_required
def date_view(request, date_str):
    if not can_view_calendar(request.user): raise PermissionDenied
    try:
        view_date = date.fromisoformat(date_str)
    except ValueError:
        view_date = timezone.localdate()
    next_day = view_date + timedelta(days=1)
    prev_day = view_date - timedelta(days=1)
    tasks = DeliveryCalendarTask.objects.filter(
        plan__in=visible_plans(request.user),
        start_date=view_date,
    ).select_related("plan", "plan__lead", "plan__package", "plan__bde", "assigned_to")
    can_edit_any = any(
        is_admin(request.user) or request.user == t.plan.bde or role_name(request.user) in {"bd_manager","management"}
        for t in tasks
    )
    return render(request, "Delivery/calendar_date.html", {
        "view_date": view_date, "next_day": next_day, "prev_day": prev_day,
        "tasks": tasks, "reminders": upcoming_reminders(request.user),
        "can_edit_any": can_edit_any,
    })


@login_required
def quick_add_task(request, date_str):
    if not can_view_calendar(request.user): raise PermissionDenied
    try:
        start_date = date.fromisoformat(date_str)
    except ValueError:
        start_date = timezone.localdate()
    form = QuickTaskForm(request.POST or None, user=request.user, initial={"start_date": start_date, "reminder_enabled": True, "reminder_days_before": 1})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task added to the calendar.")
        return redirect("delivery_calendar_date", date_str=date_str)
    return render(request, "Delivery/calendar_task_quick.html", {
        "form": form, "start_date": start_date,
        "action_url": reverse("delivery_calendar_task_quick", args=[date_str]),
    })

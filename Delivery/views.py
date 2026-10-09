from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from Control.permissions import role_name, is_admin
from .models import WorkItem, WorkAssignment, WorkEvent
from .forms import BDMForm, PMForm, TeamAssignmentForm, AssignmentUpdateForm

TEAM_ROLES = {"developer","digital_marketing","graphic_designer","videographer","video_editor"}

def employee_role(user):
    return role_name(user)

def can_access(user):
    return getattr(user, "is_superuser", False) or bool(getattr(user, "profile", None))

def can_view_work(user, work):
    if is_admin(user) or role_name(user) in {"management","hr","project_manager","bd_manager"}:
        return True
    return user in {work.bde, work.bdm, work.project_manager} or work.assignments.filter(employee=user).exists()

def can_assign_pm(user, work):
    return is_admin(user) or role_name(user) in {"management","bd_manager","project_manager"} and user == work.bdm or role_name(user) in {"management","project_manager"}

def can_assign_team(user, work):
    return is_admin(user) or role_name(user) in {"management","project_manager"} and user == work.project_manager or role_name(user) == "project_manager"

def dashboard(request):
    if not can_access(request.user):
        raise PermissionDenied
    qs = WorkItem.objects.select_related("lead","bde","bdm","project_manager","department","service")
    if not (is_admin(request.user) or role_name(request.user) in {"management","hr","project_manager","bd_manager"}):
        qs = qs.filter(Q(bde=request.user)|Q(bdm=request.user)|Q(project_manager=request.user)|Q(assignments__employee=request.user)).distinct()
    status = request.GET.get("status","")
    if status:
        qs = qs.filter(status=status)
    context = {
        "works": qs[:100],
        "total": qs.count(),
        "pending_bdm": qs.filter(status="awaiting_bdm").count(),
        "pending_pm": qs.filter(status="awaiting_pm").count(),
        "active": qs.filter(status__in=["assigned","in_progress","review","blocked"]).count(),
        "completed": qs.filter(status="completed").count(),
        "overdue": qs.filter(due_date__lt=timezone.localdate()).exclude(status__in=["completed","cancelled"]).count(),
        "statuses": WorkItem.STATUS,
        "role": role_name(request.user),
    }
    return render(request, "Delivery/dashboard.html", context)

@login_required
def detail(request, pk):
    work = get_object_or_404(WorkItem.objects.select_related("lead","bde","bdm","project_manager","department","service"), pk=pk)
    if not can_view_work(request.user, work):
        raise PermissionDenied
    return render(request, "Delivery/detail.html", {
        "work": work,
        "bdm_form": BDMForm(initial={"bdm": work.bdm_id}),
        "pm_form": PMForm(initial={"project_manager": work.project_manager_id}),
        "team_form": TeamAssignmentForm(initial={"due_date": work.due_date}),
        "assignment_form": AssignmentUpdateForm(),
        "can_bdm": is_admin(request.user) or request.user == work.bdm or role_name(request.user) in {"management","bd_manager"},
        "can_route_bdm": is_admin(request.user) or request.user == work.bde or role_name(request.user) in {"management","bd_manager"},
        "can_pm": can_assign_team(request.user, work),
    })


@login_required
def assign_bdm(request, pk):
    work = get_object_or_404(WorkItem, pk=pk)
    if not (is_admin(request.user) or request.user == work.bde or role_name(request.user) in {"management","bd_manager"}):
        raise PermissionDenied
    if request.method != "POST":
        return redirect("delivery_detail", pk=pk)
    form = BDMForm(request.POST)
    if form.is_valid():
        work.bdm = form.cleaned_data["bdm"]
        work.save(update_fields=["bdm","updated_at"])
        WorkEvent.objects.create(work=work, actor=request.user, event_type="bdm_assigned", to_status=work.status, message=f"BDM assigned: {work.bdm.get_full_name() or work.bdm.username}.")
        messages.success(request, "Work routed to the BDM.")
    else:
        messages.error(request, "Select a valid BDM.")
    return redirect("delivery_detail", pk=pk)

@login_required
def accept_bdm(request, pk):
    work = get_object_or_404(WorkItem, pk=pk)
    if not (is_admin(request.user) or request.user == work.bdm or role_name(request.user) in {"management","bd_manager"}):
        raise PermissionDenied
    if request.method != "POST": return redirect("delivery_detail", pk=pk)
    work.status = "awaiting_pm"
    work.bdm_accepted_at = timezone.now()
    work.save(update_fields=["status","bdm_accepted_at","updated_at"])
    WorkEvent.objects.create(work=work, actor=request.user, event_type="bdm_accept", from_status="awaiting_bdm", to_status="awaiting_pm", message="BDM accepted the work and routed it to Project Manager.")
    messages.success(request, "Work accepted by BDM and moved to Project Manager.")
    return redirect("delivery_detail", pk=pk)

@login_required
def assign_pm(request, pk):
    work = get_object_or_404(WorkItem, pk=pk)
    if not (is_admin(request.user) or role_name(request.user) in {"management","bd_manager"} or request.user == work.bdm):
        raise PermissionDenied
    if request.method != "POST": return redirect("delivery_detail", pk=pk)
    form = PMForm(request.POST)
    if form.is_valid():
        old=work.status
        work.project_manager=form.cleaned_data["project_manager"]
        work.status="assigned"
        work.pm_accepted_at=None
        work.save(update_fields=["project_manager","status","pm_accepted_at","updated_at"])
        WorkEvent.objects.create(work=work, actor=request.user, event_type="pm_assigned", from_status=old, to_status="assigned", message=f"Project Manager assigned: {work.project_manager.get_full_name() or work.project_manager.username}.")
        messages.success(request, "Project Manager assigned.")
    else:
        messages.error(request, "Select a valid Project Manager.")
    return redirect("delivery_detail", pk=pk)

@login_required
def assign_team(request, pk):
    work = get_object_or_404(WorkItem, pk=pk)
    if not can_assign_team(request.user, work):
        raise PermissionDenied
    if request.method != "POST": return redirect("delivery_detail", pk=pk)
    form=TeamAssignmentForm(request.POST)
    if form.is_valid():
        a=form.save(commit=False)
        a.work=work
        a.assigned_by=request.user
        a.save()
        if work.status in ("assigned","awaiting_pm"):
            work.status="assigned"
            work.save(update_fields=["status","updated_at"])
        WorkEvent.objects.create(work=work, actor=request.user, event_type="team_assigned", to_status=work.status, message=f"Assigned {a.title} to {a.employee.get_full_name() or a.employee.username}.")
        messages.success(request, "Team member assigned.")
    else:
        messages.error(request, "Please correct the team assignment.")
    return redirect("delivery_detail", pk=pk)

@login_required
def update_assignment(request, pk):
    assignment=get_object_or_404(WorkAssignment.objects.select_related("work"), pk=pk)
    work=assignment.work
    if not (request.user == assignment.employee or can_assign_team(request.user, work) or is_admin(request.user)):
        raise PermissionDenied
    if request.method=="POST":
        old=assignment.status
        form=AssignmentUpdateForm(request.POST, instance=assignment)
        if form.is_valid():
            a=form.save(commit=False)
            if a.status=="completed" and not a.completed_at:
                a.completed_at=timezone.now()
                a.progress=100
            elif a.status=="accepted" and not a.accepted_at:
                a.accepted_at=timezone.now()
            a.save()
            if a.status=="in_progress":
                work.status="in_progress"
            elif a.status=="review":
                work.status="review"
            elif a.status=="completed":
                remaining=work.assignments.exclude(status="completed").exists()
                if not remaining:
                    work.status="completed"; work.progress=100; work.completed_at=timezone.now()
            work.save(update_fields=["status","progress","completed_at","updated_at"])
            WorkEvent.objects.create(work=work, actor=request.user, event_type="assignment_update", from_status=old, to_status=a.status, message=f"{a.title}: {old} → {a.status}")
            messages.success(request, "Assignment updated.")
    return redirect("delivery_detail", pk=work.pk)

@login_required
def complete_work(request, pk):
    work=get_object_or_404(WorkItem, pk=pk)
    if not (can_assign_team(request.user, work) or is_admin(request.user)):
        raise PermissionDenied
    if request.method=="POST":
        work.status="completed"; work.progress=100; work.completed_at=timezone.now()
        work.save(update_fields=["status","progress","completed_at","updated_at"])
        work.assignments.exclude(status="completed").update(status="completed", progress=100, completed_at=timezone.now())
        WorkEvent.objects.create(work=work, actor=request.user, event_type="work_completed", to_status="completed", message="Project marked completed.")
        messages.success(request, "Project marked completed.")
    return redirect("delivery_detail", pk=pk)

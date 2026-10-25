from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, F, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Control.permissions import admin_required, hr_required, is_hr

from . import services
from .forms import CustomTaskForm, DepartmentForm, DocumentForm, EmployeeForm, NewEmployeeForm, PhotoForm
from .forms import WorkflowForm, WorkflowTaskFormSet
from .models import Employee, OnboardingTask, OnboardingTemplate


def _can_view(user, employee):
    if is_hr(user):
        return True
    own = getattr(user, "employee", None)
    return bool(own and (own.pk == employee.pk or employee.manager_id == own.pk))


@admin_required
def department_list(request, pk=None):
    from LeadManager.models import Department

    instance = get_object_or_404(Department, pk=pk) if pk else None
    form = DepartmentForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"{saved.name} department {'updated' if instance else 'created'}.")
        return redirect("hr_departments")
    departments = Department.objects.select_related("head").annotate(employee_total=Count("employees"))
    return render(request, "HR/departments.html", {"departments": departments, "form": form, "editing": instance})


@hr_required
def employee_list(request):
    qs = Employee.objects.select_related("user__profile", "department", "manager__user")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    department = request.GET.get("department", "")
    if q:
        qs = qs.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q) | Q(employee_code__icontains=q) | Q(designation__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if department:
        qs = qs.filter(department_id=department)
    from LeadManager.models import Department

    return render(request, "HR/employee_list.html", {
        "employees": qs, "q": q, "status": status, "department": department,
        "statuses": Employee.STATUSES, "departments": Department.objects.all(),
    })


@hr_required
def employee_create(request):
    if request.method == "POST":
        form = NewEmployeeForm(request.POST, request.FILES, actor=request.user)
        if form.is_valid():
            data = form.cleaned_data
            role = data["role"]
            fields = {k: v for k, v in data.items() if k in form._meta.fields}
            employee, password = services.create_employee(
                username=data["username"], first_name=data["first_name"], last_name=data["last_name"],
                email=data["email"], role_name=role.name if role else "developer",
                photo=data.get("photo"), **fields,
            )
            return render(request, "HR/employee_created.html", {"employee": employee, "password": password})
    else:
        form = NewEmployeeForm(actor=request.user)
    return render(request, "HR/employee_form.html", {"form": form, "title": "Add employee", "creating": True})


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee.objects.select_related("user__profile", "department", "manager__user"), pk=pk)
    if not _can_view(request.user, employee):
        raise PermissionDenied
    from Attendance.models import AttendanceRecord, FaceTemplate

    return render(request, "HR/employee_detail.html", {
        "emp": employee,
        "progress": employee.onboarding_progress(),
        "tasks": [_with_approval(t, request.user) for t in employee.onboarding_tasks.select_related("employee__manager")],
        "documents": employee.documents.all() if is_hr(request.user) else [],
        "doc_form": DocumentForm(),
        "task_form": CustomTaskForm(),
        "face_enrolled": FaceTemplate.objects.filter(employee=employee).exists(),
        "recent_attendance": AttendanceRecord.objects.filter(employee=employee)[:10],
        "reports": employee.reports.select_related("user"),
        "hr": is_hr(request.user),
    })


@hr_required
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == "POST":
        form = EmployeeForm(request.POST, request.FILES, instance=employee, actor=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Employee updated.")
            return redirect("hr_employee_detail", pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee, actor=request.user)
    return render(request, "HR/employee_form.html", {"form": form, "title": f"Edit {employee.full_name}", "emp": employee})


@hr_required
@require_POST
def employee_document_add(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    form = DocumentForm(request.POST, request.FILES)
    if form.is_valid():
        doc = form.save(commit=False)
        doc.employee = employee
        doc.uploaded_by = request.user
        doc.save()
        messages.success(request, "Document uploaded.")
    else:
        messages.error(request, "Could not upload document: " + "; ".join(sum(form.errors.values(), [])))
    return redirect("hr_employee_detail", pk=pk)


@hr_required
@require_POST
def employee_task_add(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    form = CustomTaskForm(request.POST)
    if form.is_valid():
        task = form.save(commit=False)
        task.employee = employee
        task.order = 100
        task.save()
        if employee.status != "onboarding" and task.required:
            messages.info(request, "Task added. Employee status was left unchanged.")
        else:
            messages.success(request, "Task added.")
    else:
        messages.error(request, "Please fill the task title.")
    return redirect("hr_employee_detail", pk=pk)


@hr_required
@require_POST
def employee_regenerate_checklist(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    created = services.generate_onboarding(employee)
    messages.success(request, f"{created} onboarding tasks generated." if created else "Checklist already exists.")
    return redirect("hr_employee_detail", pk=pk)


@hr_required
def onboarding_board(request):
    employees = Employee.objects.filter(status="onboarding").select_related("user__profile", "department")
    rows = [{"emp": e, "progress": e.onboarding_progress(),
             "review": e.onboarding_tasks.filter(status__in=["submitted", "verified"]).count(),
             "overdue": sum(1 for t in e.onboarding_tasks.filter(status="pending") if t.is_overdue)}
            for e in employees]
    return render(request, "HR/onboarding_board.html", {"rows": rows})


@login_required
def my_onboarding(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied
    services.sync_auto_tasks(employee)
    return render(request, "HR/my_onboarding.html", {
        "emp": employee, "progress": employee.onboarding_progress(),
        "tasks": employee.onboarding_tasks.all(),
    })


def _with_approval(task, user):
    """Annotate a task with what `user` may do to it (drives the buttons on the profile page)."""
    stage = task.review_stage
    task.user_can_verify = stage == "verify" and task.can_verify(user)
    task.user_can_approve = (
        (stage == "approve" and task.can_approve(user))
        or (stage == "verify" and not task.verifier and task.can_approve(user))
    )
    task.user_can_reject = task.can_review_now(user)
    return task


@login_required
@require_POST
def task_update(request, task_id):
    task = get_object_or_404(OnboardingTask.objects.select_related("employee__manager", "employee__user"), pk=task_id)
    user = request.user
    hr = is_hr(user)
    own = getattr(user, "employee", None)
    is_owner = bool(own and own.pk == task.employee_id and task.responsible == "employee")
    reviewer = task.can_review_now(user)
    if not (hr or is_owner or reviewer):
        raise PermissionDenied
    action = request.POST.get("action", "done")
    if action == "verify":
        if task.review_stage != "verify" or not task.can_verify(user):
            raise PermissionDenied
        outcome = task.verify(user)
        messages.success(request, "Verified. Waiting for confirmation." if outcome == "verified" else "Verified and completed.")
    elif action == "approve":
        if not task.review_stage or not reviewer:
            raise PermissionDenied
        task.approved_by = user
        if not task.verified_by_id:
            task.verified_by = user
            task.verified_at = timezone.now()
            task.save(update_fields=["approved_by", "verified_by", "verified_at"])
        else:
            task.save(update_fields=["approved_by"])
        task.mark_done(task.completed_by or user)
        messages.success(request, "Task confirmed.")
    elif action == "reject":
        if not task.review_stage or not reviewer:
            raise PermissionDenied
        task.status = "pending"
        task.completed_at = None
        task.verified_by = None
        task.verified_at = None
        task.save(update_fields=["status", "completed_at", "verified_by", "verified_at"])
        messages.info(request, "Task sent back for rework.")
    elif action == "skip_self":
        if not (is_owner and task.skippable and task.status == "pending"):
            raise PermissionDenied
        task.mark_skipped(user)
        messages.success(request, "Step skipped.")
    elif task.auto_key and not hr:
        messages.info(request, "This task completes automatically.")
    elif action == "done" and (hr or is_owner):
        if is_owner and not hr and task.employee_locked:
            messages.error(request, "You can only submit this task once. Contact HR to reset your submission.")
        else:
            upload = request.FILES.get("attachment")
            if upload:
                task.attachment = upload
                task.save(update_fields=["attachment"])
            if task.requires_upload and not task.attachment:
                messages.error(request, "Please attach the required file first.")
            elif task.status != "pending":
                messages.info(request, "This task is already finished or awaiting review.")
            elif task.complete(user) == "submitted":
                if is_owner and not hr:
                    task.submission_count = F("submission_count") + 1
                    task.save(update_fields=["submission_count"])
                messages.success(request, "Submitted for verification." if task.verifier else "Submitted for approval.")
            else:
                if is_owner and not hr:
                    task.submission_count = F("submission_count") + 1
                    task.save(update_fields=["submission_count"])
                messages.success(request, "Task completed.")
    elif action == "skip" and hr and (not task.required or task.skippable):
        task.mark_skipped(user)
    elif action == "reopen" and hr:
        task.status = "pending"
        task.completed_at = None
        task.completed_by = None
        task.approved_by = None
        task.verified_by = None
        task.verified_at = None
        task.submission_count = 0
        task.save(update_fields=["status", "completed_at", "completed_by", "approved_by",
                                 "verified_by", "verified_at", "submission_count"])
    services.refresh_status(task.employee)
    if is_owner and not hr and not reviewer:
        return redirect("my_onboarding")
    return redirect("hr_employee_detail", pk=task.employee_id)


@hr_required
@require_POST
def employee_photo(request, pk):
    """Quick photo upload from the employee list / onboarding board / profile."""
    employee = get_object_or_404(Employee.objects.select_related("user"), pk=pk)
    photo = request.FILES.get("photo")
    form = PhotoForm(request.POST, request.FILES)
    if photo and form.is_valid():
        services.save_photo(employee.user, form.cleaned_data["photo"])
        messages.success(request, f"Photo updated for {employee.full_name}.")
    else:
        messages.error(request, "Choose a valid image file (JPG or PNG).")
    target = request.POST.get("next", "")
    from django.utils.http import url_has_allowed_host_and_scheme

    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return redirect(target)
    return redirect("hr_employee_detail", pk=employee.pk)


@admin_required
def workflows(request):
    rows = OnboardingTemplate.objects.select_related("role", "department").annotate(task_count=Count("tasks"))
    return render(request, "HR/workflows.html", {"workflows": rows})


@admin_required
def workflow_edit(request, pk=None):
    template = get_object_or_404(OnboardingTemplate, pk=pk) if pk else None
    form = WorkflowForm(request.POST or None, instance=template)
    formset = WorkflowTaskFormSet(request.POST or None, instance=template or OnboardingTemplate())
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        formset = WorkflowTaskFormSet(request.POST, instance=saved)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Workflow saved.")
            return redirect("hr_workflow_edit", pk=saved.pk)
        if not template:
            messages.error(request, "Workflow created, but some steps are invalid.")
            return redirect("hr_workflow_edit", pk=saved.pk)
    return render(request, "HR/workflow_form.html", {"form": form, "formset": formset, "workflow": template})


@admin_required
@require_POST
def workflow_delete(request, pk):
    template = get_object_or_404(OnboardingTemplate, pk=pk)
    template.delete()
    messages.success(request, "Workflow deleted. Existing employee checklists are unchanged.")
    return redirect("hr_workflows")

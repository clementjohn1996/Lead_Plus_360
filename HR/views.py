from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, F, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from Control.permissions import admin_required, hr_required, is_hr

from . import services
from .forms import CustomTaskForm, DocumentForm, EmployeeForm, NewEmployeeForm
from .forms import WorkflowForm, WorkflowTaskFormSet
from .models import Employee, OnboardingTask, OnboardingTemplate


def _can_view(user, employee):
    if is_hr(user):
        return True
    own = getattr(user, "employee", None)
    return bool(own and (own.pk == employee.pk or employee.manager_id == own.pk))


@admin_required
def department_list(request):
    from LeadManager.models import Department
    departments = Department.objects.prefetch_related("services").select_related("head")
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        if not name:
            messages.error(request, "Department name is required.")
        elif Department.objects.filter(name__iexact=name).exists():
            messages.error(request, "That department already exists.")
        else:
            Department.objects.create(name=name, description=description)
            messages.success(request, f"{name} department created.")
            return redirect("hr_departments")
    return render(request, "HR/departments.html", {"departments": departments})


@hr_required
def employee_list(request):
    qs = Employee.objects.select_related("user", "department", "manager__user")
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
        form = NewEmployeeForm(request.POST, actor=request.user)
        if form.is_valid():
            data = form.cleaned_data
            role = data["role"]
            fields = {k: v for k, v in data.items() if k in form._meta.fields}
            employee, password = services.create_employee(
                username=data["username"], first_name=data["first_name"], last_name=data["last_name"],
                email=data["email"], role_name=role.name if role else "developer", **fields,
            )
            return render(request, "HR/employee_created.html", {"employee": employee, "password": password})
    else:
        form = NewEmployeeForm(actor=request.user)
    return render(request, "HR/employee_form.html", {"form": form, "title": "Add employee", "creating": True})


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee.objects.select_related("user", "department", "manager__user"), pk=pk)
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
        form = EmployeeForm(request.POST, instance=employee, actor=request.user)
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
    employees = Employee.objects.filter(status="onboarding").select_related("user", "department")
    rows = [{"emp": e, "progress": e.onboarding_progress(),
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
    task.user_can_approve = task.status == "submitted" and task.can_approve(user)
    return task


@login_required
@require_POST
def task_update(request, task_id):
    task = get_object_or_404(OnboardingTask.objects.select_related("employee__manager"), pk=task_id)
    user = request.user
    hr = is_hr(user)
    own = getattr(user, "employee", None)
    is_owner = bool(own and own.pk == task.employee_id and task.responsible == "employee")
    approver = task.can_approve(user)
    if not (hr or is_owner or approver):
        raise PermissionDenied
    action = request.POST.get("action", "done")
    if action in ("approve", "reject"):
        if task.status != "submitted" or not approver:
            raise PermissionDenied
        if action == "approve":
            task.approved_by = user
            task.save(update_fields=["approved_by"])
            task.mark_done(task.completed_by or user)
            messages.success(request, "Task approved.")
        else:
            task.status = "pending"
            task.completed_at = None
            task.save(update_fields=["status", "completed_at"])
            messages.info(request, "Task sent back for rework.")
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
                messages.info(request, "This task is already finished or awaiting approval.")
            elif task.complete(user) == "submitted":
                if is_owner and not hr:
                    task.submission_count = F("submission_count") + 1
                    task.save(update_fields=["submission_count"])
                messages.success(request, "Submitted for approval.")
            else:
                if is_owner and not hr:
                    task.submission_count = F("submission_count") + 1
                    task.save(update_fields=["submission_count"])
                messages.success(request, "Task completed.")
    elif action == "skip" and hr and not task.required:
        task.status = "skipped"
        task.save(update_fields=["status"])
    elif action == "reopen" and hr:
        task.status = "pending"
        task.completed_at = None
        task.completed_by = None
        task.approved_by = None
        task.submission_count = 0
        task.save(update_fields=["status", "completed_at", "completed_by", "approved_by", "submission_count"])
    if is_owner and not hr and not approver:
        return redirect("my_onboarding")
    return redirect("hr_employee_detail", pk=task.employee_id)


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

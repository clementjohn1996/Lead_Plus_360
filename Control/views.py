from django.contrib import messages
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from django.db.models import Count
from django.views.decorators.http import require_POST

from .forms import RoleForm, StyledPasswordChangeForm, UserForm, UserProfileForm
from .models import Role, UserProfile
from .permissions import admin_required, can_manage_team, can_use_crm, is_hr


def safe_next(request, default="home"):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return default


def login_view(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request))

    error = ""
    identifier = ""
    next_url = request.POST.get("next", "") or request.GET.get("next", "")

    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Accept either the normal username or the user's email address.
        username = identifier
        if identifier and "@" in identifier:
            from django.contrib.auth.models import User
            account = User.objects.filter(email__iexact=identifier).first()
            if account:
                username = account.get_username()

        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active:
            login(request, user)
            return redirect(safe_next(request))

        error = "Invalid username/email or password. If this is a fresh installation, create an account first."

    return render(request, "Control/login.html", {
        "error": error,
        "next": next_url,
        "identifier": identifier,
    })


@login_required
def home(request):
    from Attendance.models import AttendanceRecord
    from HR.models import Employee
    from Performance import services as perf

    today = timezone.localdate()
    user = request.user
    ctx = {"today": today}

    employee = getattr(user, "employee", None)
    if employee:
        ctx["employee"] = employee
        ctx["my_attendance"] = AttendanceRecord.objects.filter(employee=employee, date=today).first()
        ctx["my_score"] = perf.employee_score(employee, today.replace(day=1))
        ctx["my_onboarding"] = employee.onboarding_progress() if employee.status == "onboarding" else None

    if is_hr(user):
        active = Employee.objects.filter(status__in=["active", "probation", "onboarding"])
        present = AttendanceRecord.objects.filter(date=today, employee__in=active)
        ctx["hr_stats"] = {
            "headcount": active.count(),
            "present": present.count(),
            "late": present.filter(status="late").count(),
            "onboarding": Employee.objects.filter(status="onboarding").count(),
        }
    if can_manage_team(user):
        ctx["top_performers"] = perf.leaderboard(today.replace(day=1))[:3]
    if can_use_crm(user):
        from LeadManager.models import Task
        from LeadManager.views import scoped_leads

        leads = scoped_leads(user)
        closed = ["won", "lost", "disqualified"]
        ctx["crm"] = {
            "open": leads.exclude(stage__in=closed).count(),
            "due": leads.filter(next_follow_up__date__lte=today).exclude(stage__in=closed).count(),
            "tasks": Task.objects.filter(assigned_to=user).exclude(status="done").count(),
        }
    return render(request, "Control/home.html", ctx)


@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    user_form = UserForm(instance=request.user)
    profile_form = UserProfileForm(instance=profile_obj)
    pw_form = StyledPasswordChangeForm(request.user)
    if request.method == "POST":
        if "change_password" in request.POST:
            pw_form = StyledPasswordChangeForm(request.user, request.POST)
            if pw_form.is_valid():
                user = pw_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed.")
                return redirect("profile")
        else:
            user_form = UserForm(request.POST, instance=request.user)
            profile_form = UserProfileForm(request.POST, request.FILES, instance=profile_obj)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, "Profile updated.")
                return redirect("profile")
    from .permissions import can_manage_team, can_use_crm, is_admin, is_hr, sees_all_leads
    access = [
        ("Full system control (roles, workflows, KPIs, TV displays)", is_admin(request.user)),
        ("HR: employees, onboarding, attendance reports", is_hr(request.user)),
        ("Manage team members", can_manage_team(request.user)),
        ("CRM / leads", can_use_crm(request.user)),
        ("See all leads", sees_all_leads(request.user)),
    ]
    return render(request, "Control/profile.html", {
        "user_form": user_form, "profile_form": profile_form, "pw_form": pw_form,
        "access": access, "is_admin": is_admin(request.user),
        "employee": getattr(request.user, "employee", None),
    })


@login_required
def guide(request):
    return render(request, "Control/guide.html")


@admin_required
def roles(request):
    rows = Role.objects.annotate(user_count=Count("users")).order_by("level", "label")
    return render(request, "Control/roles.html", {"roles": rows})


@admin_required
def role_edit(request, pk=None):
    role = get_object_or_404(Role, pk=pk) if pk else None
    form = RoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Role saved.")
        return redirect("roles")
    return render(request, "Control/role_form.html", {"form": form, "role": role})


@admin_required
def role_detail(request, pk):
    role = get_object_or_404(Role, pk=pk)
    members = UserProfile.objects.filter(role=role).select_related("user")
    others = Role.objects.filter(is_active=True).exclude(pk=role.pk).order_by("level", "label")
    return render(request, "Control/role_detail.html", {"role": role, "members": members, "others": others})


@admin_required
@require_POST
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if role.is_super_admin:
        messages.error(request, "The Super Admin role cannot be deleted.")
        return redirect("roles")
    members = UserProfile.objects.filter(role=role)
    if members.exists():
        target = Role.objects.filter(pk=request.POST.get("reassign_to"), is_active=True).exclude(pk=role.pk).first()
        if not target:
            messages.error(request, "Choose a role to move the existing users to before deleting.")
            return redirect("role_detail", pk=role.pk)
        for profile in members:
            profile.role = target
            profile.save()
    role.delete()
    messages.success(request, f"Role '{role.label}' deleted.")
    return redirect("roles")


@admin_required
def control_center(request):
    from django.contrib.auth.models import User
    from Attendance.models import OfficeLocation

    users = User.objects.select_related("profile__role", "employee").order_by("-is_active", "username")
    return render(request, "Control/control_center.html", {
        "users": users, "roles": Role.objects.filter(is_active=True).order_by("level", "label"),
        "offices": OfficeLocation.objects.count(), "role_count": Role.objects.count(),
    })


@admin_required
@require_POST
def user_action(request, pk):
    from django.contrib.auth.models import User

    target = get_object_or_404(User, pk=pk)
    action = request.POST.get("action")
    is_self = target.pk == request.user.pk
    if action == "toggle_active":
        if is_self:
            messages.error(request, "You cannot deactivate your own account.")
        else:
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            messages.success(request, f"{target.username} is now {'active' if target.is_active else 'deactivated'}.")
    elif action == "set_role":
        role = Role.objects.filter(pk=request.POST.get("role"), is_active=True).first()
        if is_self:
            messages.error(request, "You cannot change your own role.")
        elif not role:
            messages.error(request, "Choose a valid role.")
        else:
            profile, _ = UserProfile.objects.get_or_create(user=target)
            profile.role = role
            profile.save()
            messages.success(request, f"{target.username} is now {role.label}.")
    elif action == "set_password":
        pw = request.POST.get("password", "")
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(pw, target)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            target.set_password(pw)
            target.save()
            if is_self:
                update_session_auth_hash(request, target)
            messages.success(request, f"Password updated for {target.username}.")
    return redirect("control_center")

from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from openpyxl import Workbook
from openpyxl.styles import Font

from Control.permissions import crm_required, sees_all_leads, sees_team_leads

from .forms import ActivityForm, LeadForm, QuickLeadForm, TaskForm
from .models import Activity, Lead, LeadSource, Service, Task

CLOSED_STAGES = ["won", "lost", "disqualified"]

LEAD_FORM_GROUPS = [
    ("Contact", ["name", "company", "designation", "industry", "email", "phone", "alternate_phone", "website"]),
    ("Location & social", ["country", "state", "city", "linkedin", "facebook", "instagram"]),
    ("Qualification", ["source", "service", "services", "stage", "temperature", "priority",
                       "estimated_value", "budget_tier", "billing_type", "probability",
                       "expected_close_date", "next_follow_up", "tags"]),
    ("Assignment", ["owner", "manager"]),
    ("Context & consent", ["notes", "lost_reason", "consent_to_contact"]),
]


def scoped_leads(user):
    """Leads the user may see: everything for managers/admins, own leads for executives."""
    qs = Lead.objects.all()
    if sees_all_leads(user):
        return qs
    scope = Q(owner=user) | Q(manager=user)
    if sees_team_leads(user):
        scope |= Q(owner__employee__manager__user=user) | Q(manager__employee__manager__user=user)
    return qs.filter(scope).distinct()


def scoped_tasks(user):
    qs = Task.objects.select_related("lead", "assigned_to")
    if sees_all_leads(user):
        return qs
    return qs.filter(Q(assigned_to=user) | Q(lead__in=scoped_leads(user)))


def _lead_or_404(user, lead_id):
    return get_object_or_404(scoped_leads(user), pk=lead_id)


def _safe_redirect(request, default):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return redirect(target)
    return redirect(default)


def _lead_form(request, instance=None):
    initial = {} if instance else {"owner": request.user}
    form = LeadForm(request.POST or None, instance=instance, initial=initial)
    if not sees_all_leads(request.user):
        # Executives cannot hand leads to others from the form.
        for name in ("owner", "manager"):
            form.fields[name].disabled = True
    return form


def _groups(form):
    return [(title, [form[n] for n in names if n in form.fields]) for title, names in LEAD_FORM_GROUPS]


@crm_required
def dashboard(request):
    today = timezone.localdate()
    leads = scoped_leads(request.user)
    open_leads = leads.exclude(stage__in=CLOSED_STAGES)
    weighted = ExpressionWrapper(
        F("estimated_value") * F("probability") / 100,
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    counts = dict(leads.values_list("stage").annotate(c=Count("id")))
    context = {
        "total_leads": leads.count(),
        "new_leads": counts.get("new", 0),
        "active_leads": open_leads.count(),
        "won": counts.get("won", 0),
        "lost": counts.get("lost", 0),
        "pipeline_value": open_leads.aggregate(v=Sum("estimated_value"))["v"] or Decimal("0"),
        "weighted_pipeline": open_leads.aggregate(v=Sum(weighted))["v"] or Decimal("0"),
        "won_value": leads.filter(stage="won").aggregate(v=Sum("estimated_value"))["v"] or Decimal("0"),
        "followups": open_leads.filter(next_follow_up__date__lte=today).select_related("owner").order_by("next_follow_up")[:8],
        "stage_counts": [{"key": k, "label": l, "count": counts.get(k, 0)} for k, l in Lead.STAGES],
        "source_counts": leads.values("source__name").annotate(total=Count("id")).order_by("-total")[:8],
        "quick_form": QuickLeadForm(),
    }
    return render(request, "leads/dashboard.html", context)


@crm_required
def lead_list(request):
    qs = scoped_leads(request.user).select_related("owner", "source", "service").prefetch_related("services")
    q = request.GET.get("q", "").strip()
    stage = request.GET.get("stage", "")
    source = request.GET.get("source", "")
    service = request.GET.get("service", "")
    owner = request.GET.get("owner", "")
    temp = request.GET.get("temperature", "")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(company__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    if stage:
        qs = qs.filter(stage=stage)
    if source.isdigit():
        qs = qs.filter(source_id=source)
    if service.isdigit():
        qs = qs.filter(Q(service_id=service) | Q(services=service)).distinct()
    if owner.isdigit():
        qs = qs.filter(owner_id=owner)
    if temp:
        qs = qs.filter(temperature=temp)
    return render(request, "leads/lead_list.html", {
        "leads": qs, "q": q, "stage": stage, "source": source, "service": service, "owner": owner, "temp": temp,
        "stages": Lead.STAGES, "sources": LeadSource.objects.filter(is_active=True),
        "services": Service.objects.filter(is_active=True),
    })


@crm_required
def lead_create(request):
    form = _lead_form(request)
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        if not sees_all_leads(request.user):
            lead.owner = request.user
        lead.save()
        form.save_m2m()
        Activity.objects.create(lead=lead, activity_type="status", subject="Lead created",
                                body="Lead added to LeadPlus-360.", created_by=request.user)
        messages.success(request, "Lead created successfully.")
        return redirect("lead_detail", lead_id=lead.id)
    return render(request, "leads/lead_form.html", {"form": form, "groups": _groups(form), "title": "Add Lead"})


@crm_required
def lead_edit(request, lead_id):
    lead = _lead_or_404(request.user, lead_id)
    old_stage = lead.stage
    form = _lead_form(request, lead)
    if request.method == "POST" and form.is_valid():
        lead = form.save()
        if old_stage != lead.stage:
            Activity.objects.create(lead=lead, activity_type="status",
                                    subject=f"Stage changed to {lead.get_stage_display()}",
                                    body="Pipeline stage updated.", created_by=request.user)
        messages.success(request, "Lead updated.")
        if old_stage != "won" and lead.stage == "won":
            return redirect("delivery_calendar_plan_create", lead_id=lead.id)
        return redirect("lead_detail", lead_id=lead.id)
    return render(request, "leads/lead_form.html", {"form": form, "groups": _groups(form), "title": "Edit Lead", "lead": lead})


@crm_required
def lead_detail(request, lead_id):
    lead = get_object_or_404(
        scoped_leads(request.user).select_related("owner", "source", "service").prefetch_related("services"),
        pk=lead_id,
    )
    return render(request, "leads/lead_detail.html", {
        "lead": lead, "activity_form": ActivityForm(), "task_form": TaskForm(initial={"lead": lead}),
    })


@crm_required
def pipeline(request):
    leads = (
        scoped_leads(request.user).exclude(stage__in=["lost", "disqualified"])
        .select_related("service").prefetch_related("services")
    )
    by_stage = {}
    for lead in leads:
        by_stage.setdefault(lead.stage, []).append(lead)
    columns = [
        {"key": k, "label": l, "leads": by_stage.get(k, []), "count": len(by_stage.get(k, []))}
        for k, l in Lead.STAGES if k not in ("lost", "disqualified")
    ]
    return render(request, "leads/pipeline.html", {"columns": columns})


@crm_required
@require_POST
def add_activity(request, lead_id):
    lead = _lead_or_404(request.user, lead_id)
    form = ActivityForm(request.POST)
    if form.is_valid():
        a = form.save(commit=False)
        a.lead = lead
        a.created_by = request.user
        a.save()
        if a.activity_type in ("call", "email", "whatsapp", "meeting"):
            lead.last_contacted = timezone.now()
            lead.save(update_fields=["last_contacted", "updated_at"])
        messages.success(request, "Activity added.")
    else:
        messages.error(request, "Please correct the activity form.")
    return redirect("lead_detail", lead_id=lead.id)


@crm_required
@require_POST
def add_task(request):
    form = TaskForm(request.POST)
    if form.is_valid():
        t = form.save(commit=False)
        if t.lead_id and not scoped_leads(request.user).filter(pk=t.lead_id).exists():
            messages.error(request, "You cannot add tasks to that lead.")
            return redirect("tasks")
        if not t.assigned_to:
            t.assigned_to = request.user
        t.save()
        messages.success(request, "Task created.")
        return redirect("lead_detail", lead_id=t.lead_id) if t.lead_id else redirect("tasks")
    messages.error(request, "Please correct the task form.")
    return redirect("tasks")


@crm_required
def tasks(request):
    qs = scoped_tasks(request.user)
    status = request.GET.get("status", "open")
    if status in ("open", "in_progress", "done"):
        qs = qs.filter(status=status)
    return render(request, "leads/tasks.html", {
        "tasks": qs, "status": status, "task_form": TaskForm(initial={"assigned_to": request.user}),
    })


@crm_required
@require_POST
def task_complete(request, task_id):
    task = get_object_or_404(scoped_tasks(request.user), pk=task_id)
    task.status = "done"
    task.save(update_fields=["status", "updated_at"])
    messages.success(request, "Task completed.")
    return _safe_redirect(request, "tasks")


@crm_required
def quick_lead(request):
    """Dedicated quick-lead capture page.

    GET renders the page (the sidebar links here directly); POST creates the
    lead and returns to the page with validation errors when necessary.
    """
    if request.method == "POST":
        form = QuickLeadForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.owner = request.user
            lead.save()
            form.save_m2m()
            Activity.objects.create(
                lead=lead,
                activity_type="status",
                subject="Quick lead created",
                created_by=request.user,
            )
            messages.success(request, "Lead added successfully.")
            return _safe_redirect(request, "leadplus_dashboard")
        messages.error(request, "Please correct the errors below.")
    else:
        form = QuickLeadForm()

    return render(request, "leads/quick_lead.html", {"form": form})


def _spreadsheet_safe(value):
    """Neutralise spreadsheet formula injection in exported text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@crm_required
def export_leads(request):
    qs = scoped_leads(request.user).select_related("owner", "source", "service").prefetch_related("services")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(company__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    wb = Workbook()
    ws = wb.active
    ws.title = "LeadPlus-360 Leads"
    ws.append(["ID", "Name", "Company", "Email", "Phone", "Website", "Country", "City", "Source", "Services", "Stage",
               "Temperature", "Priority", "Owner", "Estimated Value", "Probability %", "Next Follow-up",
               "Last Contacted", "Tags", "Notes"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for l in qs:
        services = ", ".join(s.name for s in l.services.all()) or (l.service.name if l.service else "")
        next_fu = timezone.localtime(l.next_follow_up).replace(tzinfo=None) if l.next_follow_up else None
        last = timezone.localtime(l.last_contacted).replace(tzinfo=None) if l.last_contacted else None
        row = [l.id, l.name, l.company, l.email, l.phone, l.website, l.country, l.city,
               l.source.name if l.source else "", services, l.get_stage_display(), l.get_temperature_display(),
               l.get_priority_display(), l.owner.username if l.owner else "", float(l.estimated_value),
               l.probability, next_fu, last, l.tags, l.notes]
        ws.append([_spreadsheet_safe(v) for v in row])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(max(max(len(str(c.value or "")) for c in col) + 2, 10), 40)
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="leadplus-360-leads.xlsx"'
    wb.save(response)
    return response

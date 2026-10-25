import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Control.permissions import (
    can_download_prospects, can_manage_team, can_use_outreach, is_admin, permission_required,
)

from . import importer, profiler, services
from . import signals as sig
from .forms import CampaignForm, ImportForm, PitchTemplateForm, ProspectForm, SettingsForm
from .models import Campaign, OutboxMessage, OutreachSettings, PitchTemplate, Prospect, ProspectEvent

outreach_required = permission_required(can_use_outreach)
SCAN_BATCH = 15
BULK_PITCH_LIMIT = 200


def _prospect_or_404(user, pk):
    return get_object_or_404(services.scoped_prospects(user), pk=pk)


def _scoped_messages(user):
    qs = OutboxMessage.objects.select_related("prospect", "campaign")
    if is_admin(user) or can_manage_team(user):
        return qs
    return qs.filter(prospect__owner=user)


# ---------------- dashboard ----------------
@outreach_required
def dashboard(request):
    prospects = services.scoped_prospects(request.user)
    by_status = dict(prospects.values_list("status").annotate(n=Count("id")))
    msgs = _scoped_messages(request.user)
    cfg = OutreachSettings.get_solo()
    sent = msgs.filter(status="sent").count()
    replies = ProspectEvent.objects.filter(kind="reply", prospect__in=prospects).count()
    signal_counts = {}
    for keys in prospects.exclude(signal_keys="").values_list("signal_keys", flat=True):
        for key in keys.split(","):
            if key:
                signal_counts[key] = signal_counts.get(key, 0) + 1
    top_signals = sorted(((sig.label(k), n) for k, n in signal_counts.items()), key=lambda x: -x[1])[:6]
    funnel = [(label, by_status.get(key, 0)) for key, label in Prospect.STATUSES
              if key not in ("disqualified", "unsubscribed")]
    campaigns = Campaign.objects.annotate(
        drafts=Count("messages", filter=Q(messages__status="draft")),
        sent_total=Count("messages", filter=Q(messages__status="sent")),
    )[:8]
    context = {
        "total": prospects.count(), "funnel": funnel, "sent": sent, "replies": replies,
        "reply_rate": round(100 * replies / sent) if sent else 0,
        "awaiting": msgs.filter(status="draft").count(), "approved": msgs.filter(status="approved").count(),
        "sent_today": services.sent_today(), "cap": cfg.daily_cap, "paused": cfg.sending_paused,
        "top_signals": top_signals, "campaigns": campaigns,
        "unscanned": prospects.filter(last_scanned__isnull=True).count(),
        "converted": by_status.get("converted", 0), "no_signals_confirmed": not cfg.confirmed_signals,
    }
    return render(request, "Outreach/dashboard.html", context)


# ---------------- prospects ----------------
@outreach_required
def prospect_list(request, forced_status=""):
    qs = services.scoped_prospects(request.user)
    q = request.GET.get("q", "").strip()
    status = forced_status or request.GET.get("status", "")
    if q:
        qs = qs.filter(Q(company__icontains=q) | Q(contact_name__icontains=q) | Q(email__icontains=q) | Q(city__icontains=q))
    if status:
        qs = qs.filter(status=status)
    industry = request.GET.get("industry", "").strip()
    if industry:
        qs = qs.filter(industry__iexact=industry)
    if request.GET.get("min_score"):
        try:
            qs = qs.filter(score__gte=int(request.GET["min_score"]))
        except ValueError:
            pass
    if request.method == "POST" and request.POST.get("action") == "scan":
        ids = request.POST.getlist("ids")[:SCAN_BATCH]
        confirmed = OutreachSettings.get_solo().confirmed_signals
        done = 0
        for prospect in services.scoped_prospects(request.user).filter(pk__in=ids):
            profiler.scan_prospect(prospect, confirmed, request.user)
            done += 1
        messages.success(request, f"Scanned {done} prospect(s). (Up to {SCAN_BATCH} are scanned per click.)")
        return redirect(request.get_full_path())
    elif request.method == "POST" and request.POST.get("action") == "pitch":
        ids = list(dict.fromkeys(request.POST.getlist("ids")))[:BULK_PITCH_LIMIT]
        template = get_object_or_404(_visible_pitch_templates(request.user), pk=request.POST.get("template"))
        selected = list(services.scoped_prospects(request.user).filter(pk__in=ids).order_by("pk"))
        if template.business_type:
            selected = [p for p in selected if p.industry.casefold() == template.business_type.casefold()]
        already_queued = set(OutboxMessage.objects.filter(
            prospect_id__in=[p.pk for p in selected], status__in=["draft", "approved", "sent"],
        ).values_list("prospect_id", flat=True))
        eligible = [p for p in selected if p.can_email and p.email_status != "invalid" and not p.last_contacted
                    and p.pk not in already_queued and p.status in ("new", "profiled", "qualified", "queued")]
        if not eligible:
            messages.warning(request, "No selected prospects are eligible. Check their email, business type, and contact status.")
            return redirect("outreach_prospects")
        cfg = OutreachSettings.get_solo()
        campaign = Campaign.objects.create(
            name=f"{template.name} · {timezone.localtime():%Y-%m-%d %H:%M}",
            offer="Personalized client pitch", status="active", created_by=request.user,
            filters={"industries": [template.business_type] if template.business_type else []},
        )
        pending_ids = []
        for prospect in eligible:
            subject, body = services.render_pitch(template, prospect, cfg)
            message = OutboxMessage.objects.create(
                prospect=prospect, campaign=campaign, step=1, subject=subject, body=body,
                status="approved", approved_by=request.user, approved_at=timezone.now(),
            )
            pending_ids.append(message.pk)
        sent, reason = services.send_due(limit=len(pending_ids), message_ids=pending_ids)
        detail = f"Sent {sent} of {len(pending_ids)} selected pitch emails."
        waiting = OutboxMessage.objects.filter(pk__in=pending_ids, status="approved").count()
        failed = OutboxMessage.objects.filter(pk__in=pending_ids, status="failed").count()
        if waiting:
            detail += f" {waiting} remain approved for the next scheduled send (daily cap or sending pause)."
        if failed:
            detail += f" {failed} failed; review them in the approval desk."
        if reason:
            detail += f" {reason}"
        messages.success(request, detail)
        return redirect("outreach_outbox")
    page = Paginator(qs, BULK_PITCH_LIMIT).get_page(request.GET.get("page"))
    return render(request, "Outreach/prospect_list.html", {
        "page": page, "q": q, "status": status, "statuses": Prospect.STATUSES, "batch": SCAN_BATCH,
        "labels": sig.SIGNALS, "industry": industry,
        "industries": list(services.scoped_prospects(request.user).exclude(industry="").order_by("industry")
                            .values_list("industry", flat=True).distinct()),
        "templates": _visible_pitch_templates(request.user).filter(is_active=True),
        "can_download": can_download_prospects(request.user), "bulk_limit": BULK_PITCH_LIMIT,
        "contacted_only": forced_status == "contacted",
    })


def contacted_prospects(request):
    return prospect_list(request, forced_status="contacted")


def _visible_pitch_templates(user):
    qs = PitchTemplate.objects.all()
    if is_admin(user) or can_manage_team(user):
        return qs
    return qs.filter(created_by=user)


@outreach_required
def pitch_templates(request, pk=None):
    current = get_object_or_404(_visible_pitch_templates(request.user), pk=pk) if pk else None
    form = PitchTemplateForm(request.POST or None, instance=current)
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "delete" and current:
            current.delete()
            messages.success(request, "Pitch template deleted.")
            return redirect("outreach_templates")
        if form.is_valid():
            template = form.save(commit=False)
            if not template.pk:
                template.created_by = request.user
            template.save()
            messages.success(request, "Pitch template saved.")
            return redirect("outreach_templates")
    return render(request, "Outreach/templates.html", {
        "form": form, "current": current, "templates": _visible_pitch_templates(request.user),
        "placeholders": ["{{first_name}}", "{{contact_name}}", "{{company}}", "{{industry}}",
                         "{{sender_name}}", "{{company_address}}"],
    })


@outreach_required
def prospect_new(request):
    form = ProspectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        prospect = form.save(commit=False)
        prospect.owner = services.ProspectAllocator(request.user).next_owner()
        prospect.source = "manual"
        prospect.save()
        messages.success(request, "Prospect added. Use Scan website to collect signals.")
        return redirect("outreach_prospect_detail", pk=prospect.pk)
    return render(request, "Outreach/prospect_form.html", {"form": form, "title": "Add prospect"})


@outreach_required
def prospect_detail(request, pk):
    prospect = _prospect_or_404(request.user, pk)
    if request.method == "POST":
        return _prospect_action(request, prospect)
    return render(request, "Outreach/prospect_detail.html", {
        "p": prospect, "events": prospect.events.select_related("created_by")[:40],
        "messages_list": prospect.messages.select_related("campaign"),
        "signal_rows": [(k, sig.label(k)) for k in prospect.signals],
        "tech": prospect.signal_data.get("tech", []),
        "form": ProspectForm(instance=prospect),
    })


def _prospect_action(request, prospect):
    action = request.POST.get("action", "")
    user = request.user
    if action == "scan":
        confirmed = OutreachSettings.get_solo().confirmed_signals
        if not confirmed:
            messages.warning(request, "Confirm at least one signal under Signals & settings first.")
        else:
            messages.info(request, profiler.scan_prospect(prospect, confirmed, user))
    elif action == "reply":
        text = request.POST.get("reply_text", "").strip()
        if text:
            intent = services.log_reply(prospect, text, user)
            messages.success(request, f"Reply logged as: {intent.replace('_', ' ')}.")
    elif action == "convert":
        lead, created = services.convert_to_lead(prospect, user)
        messages.success(request, "Converted to a CRM lead." if created else "Linked to the existing CRM lead.")
        return redirect("lead_detail", pk=lead.pk) if lead else redirect("outreach_prospect_detail", pk=prospect.pk)
    elif action == "note":
        text = request.POST.get("note_text", "").strip()
        if text:
            ProspectEvent.objects.create(prospect=prospect, kind="note", body=text[:2000], created_by=user)
    elif action == "unsubscribe":
        prospect.unsubscribed = True
        prospect.status = "unsubscribed"
        prospect.save()
        OutboxMessage.objects.filter(prospect=prospect, status__in=["draft", "approved"]).update(status="cancelled")
        messages.info(request, "Marked as do-not-contact; queued emails cancelled.")
    elif action == "disqualify":
        prospect.status = "disqualified"
        prospect.save(update_fields=["status", "updated_at"])
        OutboxMessage.objects.filter(prospect=prospect, status__in=["draft", "approved"]).update(status="cancelled")
    elif action == "email_status":
        value = request.POST.get("email_status", "")
        if value in dict(Prospect.EMAIL_STATUSES):
            prospect.email_status = value
            prospect.save(update_fields=["email_status", "updated_at"])
    elif action == "save":
        form = ProspectForm(request.POST, instance=prospect)
        if form.is_valid():
            form.save()
            messages.success(request, "Prospect updated.")
        else:
            messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("outreach_prospect_detail", pk=prospect.pk)


@permission_required(can_download_prospects)
def prospect_export(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="prospects.csv"'
    writer = csv.writer(response)
    writer.writerow(["Company", "Contact", "Title", "Email", "Phone", "Website", "City", "Status", "Score", "Signals"])
    for p in services.scoped_prospects(request.user):
        writer.writerow([p.company, p.contact_name, p.contact_title, p.email, p.phone, p.website, p.city,
                         p.get_status_display(), p.score if p.score is not None else "",
                         "; ".join(sig.label(k) for k in p.signals)])
    return response


# ---------------- import ----------------
@outreach_required
def import_leads(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    summary = None
    if request.method == "POST" and form.is_valid():
        try:
            rows = importer.read_rows(form.cleaned_data["file"])
            summary = importer.import_prospects(rows, request.user)
            if summary["created"]:
                messages.success(request, f"Imported {summary['created']} prospect(s).")
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "That file could not be read. Save it as .xlsx or .csv and try again.")
    return render(request, "Outreach/import.html", {"form": form, "summary": summary})


# ---------------- cohorts & campaigns ----------------
@outreach_required
def cohorts(request):
    filters = services.parse_filters(request.GET) if request.GET else {
        "must": [], "exclude": [], "min_score": 0, "city": "", "status": "", "with_email": True}
    qs = services.cohort(request.user, filters)
    return render(request, "Outreach/cohorts.html", {
        "filters": filters, "count": qs.count(), "rows": qs[:25],
        "signal_choices": [(k, v[0]) for k, v in sig.SIGNALS.items()], "statuses": Prospect.STATUSES,
        "industries": list(services.scoped_prospects(request.user).exclude(industry="").order_by("industry")
                            .values_list("industry", flat=True).distinct()),
        "query": request.GET.urlencode(),
    })


@outreach_required
def campaigns(request):
    rows = Campaign.objects.annotate(
        drafts=Count("messages", filter=Q(messages__status="draft")),
        approved=Count("messages", filter=Q(messages__status="approved")),
        sent_total=Count("messages", filter=Q(messages__status="sent")),
    )
    return render(request, "Outreach/campaigns.html", {"campaigns": rows})


@outreach_required
def campaign_new(request):
    source = request.POST if request.method == "POST" else request.GET
    filters = services.parse_filters(source)
    form = CampaignForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        campaign = form.save(commit=False)
        campaign.filters = filters
        campaign.created_by = request.user
        campaign.save()
        messages.success(request, "Campaign created. Review the cohort, then generate drafts.")
        return redirect("outreach_campaign_detail", pk=campaign.pk)
    return render(request, "Outreach/campaign_form.html", {
        "form": form, "filters": filters, "count": services.cohort(request.user, filters).count(),
        "signal_labels": [sig.label(k) for k in filters["must"]],
    })


@outreach_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "draft":
            created, skipped = services.draft_campaign(campaign, request.user)
            messages.success(request, f"{created} draft email(s) created and waiting on the Approval desk. {skipped} skipped (no usable email).")
        elif action == "activate":
            campaign.status = "active"
            campaign.save(update_fields=["status"])
            messages.success(request, "Campaign is active. Approved emails will now be sent.")
        elif action == "pause":
            campaign.status = "paused"
            campaign.save(update_fields=["status"])
            messages.info(request, "Campaign paused.")
        return redirect("outreach_campaign_detail", pk=pk)
    counts = dict(campaign.messages.values_list("status").annotate(n=Count("id")))
    return render(request, "Outreach/campaign_detail.html", {
        "c": campaign, "counts": counts, "cohort_size": services.cohort(request.user, campaign.filters).count(),
        "labels": [sig.label(k) for k in campaign.filters.get("must", [])],
        "excluded": [sig.label(k) for k in campaign.filters.get("exclude", [])],
        "statuses": OutboxMessage.STATUSES,
    })


# ---------------- approval desk ----------------
@outreach_required
def outbox(request):
    qs = _scoped_messages(request.user)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "send_now":
            sent, reason = services.send_due()
            messages.success(request, f"Sent {sent} email(s)." + (f" {reason}" if reason else ""))
            return redirect("outreach_outbox")
        message = get_object_or_404(qs, pk=request.POST.get("id"))
        if message.status == "draft" and action in ("approve", "reject"):
            subject = request.POST.get("subject", "").strip()
            body = request.POST.get("body", "").strip()
            if action == "approve":
                if subject:
                    message.subject = subject[:200]
                if body:
                    message.body = body
                message.status = "approved"
                message.approved_by = request.user
                message.approved_at = timezone.now()
                message.save()
            else:
                message.status = "rejected"
                message.save(update_fields=["status"])
        return redirect("outreach_outbox")
    drafts = list(qs.filter(status="draft").order_by("created_at", "step")[:200])
    current = None
    wanted = request.GET.get("m")
    if wanted and str(wanted).isdigit():
        current = next((d for d in drafts if d.pk == int(wanted)), None)
    current = current or (drafts[0] if drafts else None)
    from . import writer

    return render(request, "Outreach/outbox.html", {
        "drafts": drafts, "m": current, "approved": qs.filter(status="approved").count(),
        "sent_today": services.sent_today(), "cap": OutreachSettings.get_solo().daily_cap,
        "recent": qs.filter(status__in=["sent", "failed"]).order_by("-created_at")[:10],
        "issues": writer.violations((current.subject + " " + current.body)) if current else [],
        "word_count": writer.words(current.body) if current else 0,
        "word_limit": writer.WORD_LIMITS.get(current.step, 75) if current else 75,
    })


# ---------------- settings ----------------
@outreach_required
def settings_view(request):
    cfg = OutreachSettings.get_solo()
    can_edit = is_admin(request.user) or can_manage_team(request.user)
    form = SettingsForm(request.POST or None, instance=cfg)
    if request.method == "POST":
        if not can_edit:
            raise Http404
        if form.is_valid():
            obj = form.save(commit=False)
            obj.confirmed_signals = [k for k in request.POST.getlist("signals") if k in sig.SIGNALS]
            obj.save()
            messages.success(request, "Settings saved.")
            return redirect("outreach_settings")
    return render(request, "Outreach/settings.html", {
        "form": form, "can_edit": can_edit, "signal_rows": [(k, v[0], v[1]) for k, v in sig.SIGNALS.items()],
        "confirmed": set(cfg.confirmed_signals),
    })


# ---------------- public unsubscribe ----------------
def unsubscribe(request, token):
    prospect = get_object_or_404(Prospect, unsubscribe_token=token)
    if request.method == "POST":
        prospect.unsubscribed = True
        prospect.status = "unsubscribed"
        prospect.save()
        OutboxMessage.objects.filter(prospect=prospect, status__in=["draft", "approved"]).update(status="cancelled")
        ProspectEvent.objects.create(prospect=prospect, kind="status", body="Unsubscribed via email link.")
        return render(request, "Outreach/unsubscribed.html", {"done": True})
    return render(request, "Outreach/unsubscribed.html", {"done": prospect.unsubscribed, "p": prospect})

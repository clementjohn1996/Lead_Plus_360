import re
from datetime import timedelta

from django.conf import settings as dj_settings
from django.core.mail import EmailMessage
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from Control.models import OrganizationSettings
from Control.permissions import can_manage_team, is_admin, sees_all_leads

from . import writer
from .models import Campaign, OutboxMessage, OutreachSettings, Prospect, ProspectEvent


def scoped_prospects(user):
    qs = Prospect.objects.select_related("owner")
    if is_admin(user) or can_manage_team(user) or sees_all_leads(user):
        return qs
    return qs.filter(owner=user)


# ---------- cohorts ----------
def cohort(user, filters):
    """Prospects matching {must:[..], exclude:[..], min_score:int, city:str, status:str}."""
    qs = scoped_prospects(user).exclude(status__in=["unsubscribed", "disqualified", "converted"]).exclude(unsubscribed=True)
    for key in filters.get("must", []):
        qs = qs.filter(signal_keys__contains=f",{key},")
    for key in filters.get("exclude", []):
        qs = qs.exclude(signal_keys__contains=f",{key},")
    if filters.get("min_score"):
        qs = qs.filter(score__gte=int(filters["min_score"]))
    if filters.get("city"):
        qs = qs.filter(city__icontains=filters["city"])
    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    if filters.get("with_email"):
        qs = qs.exclude(email="").exclude(email_status="invalid")
    return qs


def parse_filters(data):
    """Normalise filters from a QueryDict / dict."""
    getlist = data.getlist if hasattr(data, "getlist") else (lambda k: data.get(k, []))
    get = data.get
    try:
        min_score = int(get("min_score") or 0)
    except (TypeError, ValueError):
        min_score = 0
    return {
        "must": [k for k in getlist("must") if k],
        "exclude": [k for k in getlist("exclude") if k],
        "min_score": min_score,
        "city": (get("city") or "").strip(),
        "status": (get("status") or "").strip(),
        "with_email": bool(get("with_email")),
    }


# ---------- drafting ----------
def draft_campaign(campaign, user):
    """Create draft emails (3 steps) for everyone in the campaign's cohort. Idempotent."""
    cfg = OutreachSettings.get_solo()
    created = skipped = 0
    for prospect in cohort(user, campaign.filters).filter(~Q(email="")):
        if not prospect.can_email:
            skipped += 1
            continue
        for step, subject, body in writer.build_sequence(prospect, campaign, cfg):
            _, was_created = OutboxMessage.objects.get_or_create(
                prospect=prospect, campaign=campaign, step=step, defaults={"subject": subject, "body": body},
            )
            created += 1 if was_created else 0
        if prospect.status in ("new", "profiled", "qualified"):
            prospect.status = "queued"
            prospect.save(update_fields=["status", "updated_at"])
    return created, skipped


# ---------- sending ----------
def _address(cfg):
    return (cfg.company_address or OrganizationSettings.get_solo().address or "").strip()


def site_url():
    return getattr(dj_settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def compose(message, cfg):
    unsub = site_url() + reverse("outreach_unsubscribe", args=[message.prospect.unsubscribe_token])
    footer = f"\n\n--\nNot relevant? Unsubscribe: {unsub}"
    address = _address(cfg)
    if address:
        footer += f"\n{address}"
    return message.body + footer, unsub


def sent_today():
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return OutboxMessage.objects.filter(status="sent", sent_at__gte=start).count()


def is_due(message, now=None):
    now = now or timezone.now()
    if message.step == 1:
        return True
    previous = OutboxMessage.objects.filter(
        prospect=message.prospect, campaign=message.campaign, step=message.step - 1
    ).first()
    if not previous or previous.status != "sent" or not previous.sent_at:
        return False
    days = message.campaign.followup_days_2 if message.step == 2 else message.campaign.followup_days_3
    return previous.sent_at + timedelta(days=days) <= now


def send_due(limit=None):
    """Send approved emails that are due, within the daily cap. Returns (sent, blocked_reason)."""
    cfg = OutreachSettings.get_solo()
    if cfg.sending_paused:
        return 0, "Sending is paused."
    remaining = cfg.daily_cap - sent_today()
    if remaining <= 0:
        return 0, "Daily cap reached."
    if limit:
        remaining = min(remaining, limit)
    sent = 0
    queue = OutboxMessage.objects.filter(status="approved", campaign__status="active").select_related(
        "prospect", "campaign").order_by("approved_at")
    for message in queue:
        if sent >= remaining:
            break
        prospect = message.prospect
        if not prospect.can_email or prospect.status in ("replied", "meeting"):
            message.status = "cancelled"
            message.error = "Prospect no longer eligible."
            message.save(update_fields=["status", "error"])
            continue
        if not is_due(message):
            continue
        body, unsub = compose(message, cfg)
        try:
            mail = EmailMessage(
                subject=message.subject, body=body, to=[prospect.email],
                headers={"List-Unsubscribe": f"<{unsub}>"},
            )
            mail.send(fail_silently=False)
        except Exception as exc:  # network / SMTP problems must not stop the batch
            message.status = "failed"
            message.error = str(exc)[:290]
            message.save(update_fields=["status", "error"])
            continue
        now = timezone.now()
        message.status = "sent"
        message.sent_at = now
        message.save(update_fields=["status", "sent_at"])
        prospect.last_contacted = now
        if prospect.status in ("new", "profiled", "qualified", "queued"):
            prospect.status = "contacted"
        prospect.save(update_fields=["last_contacted", "status", "updated_at"])
        ProspectEvent.objects.create(prospect=prospect, kind="sent", body=f"Step {message.step}: {message.subject}")
        sent += 1
    return sent, ""


# ---------- replies ----------
INTENT_RULES = [
    ("unsubscribe", r"unsubscribe|remove me|stop (emailing|sending|contacting)|take me off|do not contact"),
    ("bounce", r"delivery (has )?failed|undeliverable|mailer-daemon|address not found|mailbox (full|unavailable)"),
    ("out_of_office", r"out of (the )?office|auto-?reply|on (annual )?leave|automatic reply"),
    ("not_interested", r"not interested|no thanks|no thank you|not a fit|not looking|already (have|work)|don'?t need"),
    ("interested", r"interested|tell me more|send (me )?(details|info|pricing|a quote)|pricing|quote|demo|call me|schedule|meeting|let'?s talk|sounds good|yes"),
]


def classify_reply(text):
    low = text.lower()
    for intent, pattern in INTENT_RULES:
        if re.search(pattern, low):
            return intent
    return "neutral"


def log_reply(prospect, text, user):
    intent = classify_reply(text)
    ProspectEvent.objects.create(prospect=prospect, kind="reply", intent=intent, body=text[:2000], created_by=user)
    if intent == "out_of_office":
        return intent
    OutboxMessage.objects.filter(prospect=prospect, status__in=["draft", "approved"]).update(status="cancelled")
    if intent == "unsubscribe":
        prospect.unsubscribed = True
        prospect.status = "unsubscribed"
    elif intent == "bounce":
        prospect.email_status = "invalid"
    elif intent == "not_interested":
        prospect.status = "disqualified"
    else:
        prospect.status = "replied"
    prospect.save()
    return intent


# ---------- conversion ----------
def convert_to_lead(prospect, user):
    """Create (or link) a CRM lead. Returns (lead, created)."""
    from LeadManager.models import Lead, LeadSource

    if prospect.converted_lead_id:
        return prospect.converted_lead, False
    existing = Lead.objects.filter(email__iexact=prospect.email).first() if prospect.email else None
    if existing:
        prospect.converted_lead = existing
        prospect.status = "converted"
        prospect.save(update_fields=["converted_lead", "status", "updated_at"])
        return existing, False
    source, _ = LeadSource.objects.get_or_create(name="Outreach", defaults={"icon": "bi bi-envelope"})
    from . import signals as sig

    notes = [f"Created from Growth engine prospect '{prospect.company}'."]
    if prospect.signals:
        notes.append("Signals: " + ", ".join(sig.label(k) for k in prospect.signals))
    if prospect.score is not None:
        notes.append(f"Fit score {prospect.score}/10. {prospect.score_reason}")
    last_reply = prospect.events.filter(kind="reply").first()
    if last_reply:
        notes.append(f"Last reply ({last_reply.intent}): {last_reply.body[:300]}")
    lead = Lead.objects.create(
        name=prospect.contact_name or prospect.company, company=prospect.company,
        designation=prospect.contact_title, industry=prospect.industry, email=prospect.email,
        phone=prospect.phone, website=prospect.website if prospect.website.startswith("http") else "",
        city=prospect.city, country=prospect.country, source=source, owner=user, notes="\n".join(notes),
    )
    prospect.converted_lead = lead
    prospect.status = "converted"
    prospect.save(update_fields=["converted_lead", "status", "updated_at"])
    OutboxMessage.objects.filter(prospect=prospect, status__in=["draft", "approved"]).update(status="cancelled")
    ProspectEvent.objects.create(prospect=prospect, kind="status", body=f"Converted to CRM lead #{lead.pk}.", created_by=user)
    return lead, True

"""
Signal handlers for LeadManager.

- create_status_history_on_stage_change: audit-trail LeadStatusHistory on every stage transition.
- auto_assign_new_lead: auto-assigns newly created leads to a BDS manager.
- create_handover_on_win: generates ServiceHandover records when a lead is won.
- schedule_followup_reminder: creates a FollowUpSchedule when next_follow_up is set.
- notify_overdue_followups: management-command helper — marks overdue follow-ups.
"""

from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    Lead,
    LeadStatusHistory,
    FollowUpSchedule,
    ServiceHandover,
    LostReasonLog,
    Reminder,
    Deal,
)


# ============================================================
# LEAD STATUS HISTORY — audit trail of stage transitions
# ============================================================

@receiver(pre_save, sender=Lead)
def create_status_history_on_stage_change(sender, instance, **kwargs):
    """
    Records a LeadStatusHistory entry whenever a Lead's stage changes.
    Runs in pre_save so we can compare against the DB value efficiently.
    """
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.stage != instance.stage:
        LeadStatusHistory.objects.create(
            lead=instance,
            from_stage=old.stage,
            to_stage=instance.stage,
            changed_by=getattr(instance, "_changed_by", None),
            reason=getattr(instance, "_status_change_reason", ""),
        )

    # Clear temp attrs so they don't leak into subsequent saves
    for attr in ("_changed_by", "_status_change_reason"):
        if hasattr(instance, attr):
            delattr(instance, attr)


# ============================================================
# AUTO-ASSIGN NEW LEADS
# ============================================================

@receiver(post_save, sender=Lead)
def auto_assign_new_lead(sender, instance, created, **kwargs):
    """
    When a new lead is created without an owner, attempts to assign it
    to a BDS Manager (via round-robin or the first available manager).
    """
    if not created:
        return

    if instance.owner_id is not None:
        return

    from django.contrib.auth import get_user_model

    User = get_user_model()
    managers = User.objects.filter(
        profile__role__name="director",
    ) | User.objects.filter(
        profile__role__name="bds_manager",
    )
    managers = managers.distinct()

    if managers.exists():
        manager = managers.first()
        instance.owner = manager
        instance.manager = manager
        instance.assigned_at = timezone.now()
        instance._status_change_reason = "Auto-assigned on creation"
        instance.save(update_fields=["owner", "manager", "assigned_at"])


# ============================================================
# SERVICE HANDOVER — auto-generate on "Won"
# ============================================================

@receiver(post_save, sender=Lead)
def create_handover_on_win(sender, instance, created, **kwargs):
    """
    When a lead transitions to 'won', automatically generates a
    ServiceHandover for each service tagged on the lead, routing
    it to the responsible Department.
    """
    if created:
        return

    if instance.stage != "won":
        return

    from .models import Department

    services = instance.services.all()
    if not services:
        return

    for service in services:
        department = Department.objects.filter(services=service).first()
        if not department:
            continue

        ServiceHandover.objects.get_or_create(
            lead=instance,
            service=service,
            department=department,
            defaults={
                "target_deliverable": f"Scope for {service.name}",
                "target_delivery_date": timezone.now().date(),
                "approved_quote": instance.estimated_value,
                "billing_type": instance.billing_type or "onetime",
                "scope_notes": instance.notes or "",
            },
        )


# ============================================================
# FOLLOW-UP SCHEDULE — auto-create when next_follow_up is set
# ============================================================

@receiver(post_save, sender=Lead)
def schedule_followup_reminder(sender, instance, created, **kwargs):
    """
    Creates a FollowUpSchedule entry when a lead's next_follow_up is set
    and no pending follow-up already exists for that date.
    """
    if not instance.next_follow_up:
        return

    existing = FollowUpSchedule.objects.filter(
        lead=instance,
        due_at=instance.next_follow_up,
        status="pending",
    )
    if existing.exists():
        return

    FollowUpSchedule.objects.create(
        lead=instance,
        title=f"Follow-up: {instance.name}",
        description=f"Scheduled follow-up with {instance.name} ({instance.company}).",
        due_at=instance.next_follow_up,
        assigned_to=instance.owner,
        created_by=instance.owner,
    )


# ============================================================
# LOST REASON LOG — auto-log when stage becomes "lost"
# ============================================================

@receiver(post_save, sender=Lead)
def log_lost_reason(sender, instance, created, **kwargs):
    """
    When a lead transitions to 'lost', automatically creates a
    LostReasonLog entry if one does not already exist for this lead.
    """
    if created:
        return

    if instance.stage != "lost":
        return

    if instance.lost_reason:
        LostReasonLog.objects.get_or_create(
            lead=instance,
            reason=instance.lost_reason,
            defaults={
                "notes": instance.notes or "",
            },
        )


# ============================================================
# CONTRACT RENEWAL REMINDER
# ============================================================

@receiver(post_save, sender=Deal)
def schedule_renewal_reminder(sender, instance, created, **kwargs):
    """
    When a Deal has a renewal_date, create a Reminder
    renewal_reminder_days before the renewal date.
    """
    if not instance.renewal_date:
        return

    from datetime import timedelta, time, datetime

    reminder_date = instance.renewal_date - timedelta(days=instance.renewal_reminder_days)
    due_at = timezone.make_aware(datetime.combine(reminder_date, time(9, 0)))

    # Avoid duplicate reminders for the same deal + renewal date
    existing = Reminder.objects.filter(
        related_lead=instance.lead,
        reminder_type="renewal",
    )
    if existing.exists():
        return

    Reminder.objects.create(
        title=f"Contract renewal: {instance.lead.name}",
        description=f"Renewal date is {instance.renewal_date}. Reminder {instance.renewal_reminder_days} day(s) prior.",
        reminder_type="renewal",
        due_at=due_at,
        assigned_to=instance.lead.owner,
        created_by=instance.lead.manager,
        related_lead=instance.lead,
    )

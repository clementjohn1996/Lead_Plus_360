from django.contrib import admin

from .models import Campaign, OutboxMessage, OutreachSettings, Prospect, ProspectEvent

admin.site.register(OutreachSettings)
admin.site.register(Campaign)


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    list_display = ("company", "email", "status", "score", "owner", "created_at")
    list_filter = ("status", "source")
    search_fields = ("company", "email", "domain")


@admin.register(OutboxMessage)
class OutboxAdmin(admin.ModelAdmin):
    list_display = ("prospect", "campaign", "step", "status", "sent_at")
    list_filter = ("status",)


admin.site.register(ProspectEvent)

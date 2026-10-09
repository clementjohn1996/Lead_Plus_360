from django.contrib import admin
from .models import Role, UserProfile


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "label", "is_active", "user_count")
    list_filter = ("is_active",)
    search_fields = ("name", "label")

    @admin.display(description="Users")
    def user_count(self, obj):
        return obj.users.count()

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "phone")
    autocomplete_fields = ("user", "team")
    list_select_related = ("user", "role")
    raw_id_fields = ("team",)

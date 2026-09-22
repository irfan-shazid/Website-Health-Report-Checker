from django.contrib import admin

from scanner.models import LoginAttempt


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Failed sign-ins. Delete rows here to lift a pause early."""

    list_display = ["created_at", "username", "client"]
    list_filter = ["created_at"]
    search_fields = ["username", "client"]
    readonly_fields = ["created_at", "username", "client"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

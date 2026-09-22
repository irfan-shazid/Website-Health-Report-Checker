from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reports"

    def ready(self):
        from config import checks  # noqa: F401  (registers the setup checks)
        from reports import signin  # noqa: F401  (connects the sign-in signal receivers)

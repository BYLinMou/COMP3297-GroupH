from django.apps import AppConfig


class DefectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "defects"

    def ready(self):
        # Register signal handlers (e.g., post_migrate seed setup).
        from . import signals  # noqa: F401

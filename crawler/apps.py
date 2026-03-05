from django.apps import AppConfig


class CrawlerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crawler"

    def ready(self) -> None:
        # Register signals (no-op for now, but keeps future hooks centralized).
        from . import signals  # noqa: F401

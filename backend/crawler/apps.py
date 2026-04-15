from django.apps import AppConfig


class CrawlerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crawler"

    def ready(self) -> None:
        from . import signals  # noqa: F401  # post_save: auto-derive competitor keywords

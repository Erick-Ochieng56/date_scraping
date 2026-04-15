from django.core.management.base import BaseCommand

from crawler.models import WebsiteProfile
from crawler.services.competitor_filter import is_likely_competitor


class Command(BaseCommand):
    help = "Retroactively flag competitor LSP domains in WebsiteProfile"

    def handle(self, *args, **kwargs):
        flagged = 0
        profiles = WebsiteProfile.objects.filter(is_competitor=False).select_related(
            "domain"
        )

        for profile in profiles:
            domain = profile.domain.domain
            services = profile.detected_services or []
            org_types = profile.detected_org_types or []
            pseudo_text = [
                profile.org_name or "",
                " ".join(str(x) for x in services),
                " ".join(str(x) for x in org_types),
            ]
            is_comp, reason = is_likely_competitor(domain, pseudo_text)
            if is_comp:
                profile.is_competitor = True
                profile.is_competitor_reason = reason[:500]
                profile.translation_need_score = 0
                profile.gemini_translation_need_score = None
                profile.save(
                    update_fields=[
                        "is_competitor",
                        "is_competitor_reason",
                        "translation_need_score",
                        "gemini_translation_need_score",
                        "analyzed_at",
                    ]
                )
                flagged += 1
                self.stdout.write(f"  Flagged: {domain} — {reason}")

        self.stdout.write(self.style.SUCCESS(f"\nDone. Flagged {flagged} competitors."))

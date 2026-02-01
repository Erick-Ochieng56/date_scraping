from __future__ import annotations

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from scraper.models import ScrapeTarget, ScrapeTargetType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync ScrapeTargets from a JSON/YAML config file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="targets.json",
            help="Path to targets config file (JSON or YAML)",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing targets (by name) instead of skipping",
        )
        parser.add_argument(
            "--disable-missing",
            action="store_true",
            help="Disable targets that exist in DB but not in config file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"Config file not found: {file_path}")

        # Load config
        try:
            if file_path.suffix.lower() in (".json", ".json5"):
                with open(file_path, encoding="utf-8") as f:
                    targets_data = json.load(f)
            elif file_path.suffix.lower() in (".yaml", ".yml"):
                try:
                    import yaml  # type: ignore[reportMissingModuleSource]
                    with open(file_path, encoding="utf-8") as f:
                        targets_data = yaml.safe_load(f)
                except ImportError:
                    raise CommandError(
                        "YAML support requires PyYAML: pip install pyyaml"
                    )
            else:
                # Try JSON first, then YAML
                try:
                    with open(file_path, encoding="utf-8") as f:
                        targets_data = json.load(f)
                except json.JSONDecodeError:
                    try:
                        import yaml  # type: ignore[reportMissingModuleSource]
                        with open(file_path, encoding="utf-8") as f:
                            targets_data = yaml.safe_load(f)
                    except ImportError:
                        raise CommandError(
                            "Could not parse file. Install PyYAML for YAML support: pip install pyyaml"
                        )
        except Exception as e:
            raise CommandError(f"Failed to load config file: {e}")

        if not isinstance(targets_data, list):
            raise CommandError("Config file must contain a list of targets")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        # Track which targets we've processed
        processed_names = set()
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for target_data in targets_data:
            name = target_data.get("name")
            if not name:
                self.stdout.write(
                    self.style.WARNING("Skipping target without 'name' field")
                )
                continue

            processed_names.add(name)

            # Validate required fields
            if not target_data.get("start_url"):
                self.stdout.write(
                    self.style.WARNING(f"Skipping '{name}': missing 'start_url'")
                )
                continue

            # Get target type
            target_type_str = target_data.get("target_type", "html")
            try:
                target_type = ScrapeTargetType(target_type_str)
            except ValueError:
                self.stdout.write(
                    self.style.WARNING(
                        f"Invalid target_type '{target_type_str}' for '{name}', using 'html'"
                    )
                )
                target_type = ScrapeTargetType.HTML

            # Prepare defaults
            defaults = {
                "start_url": target_data.get("start_url", ""),
                "enabled": target_data.get("enabled", True),
                "target_type": target_type,
                "run_every_minutes": target_data.get("run_every_minutes", 60),
                "config": target_data.get("config", {}),
            }

            if options["dry_run"]:
                existing = ScrapeTarget.objects.filter(name=name).first()
                if existing:
                    self.stdout.write(
                        self.style.WARNING(f"[DRY RUN] Would update target: {name}")
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"[DRY RUN] Would create target: {name}")
                    )
                continue

            # Get or create target
            target, created = ScrapeTarget.objects.get_or_create(
                name=name,
                defaults=defaults,
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created target: {name}")
                )
            elif options["update"]:
                # Update existing target
                target.start_url = defaults["start_url"]
                target.enabled = defaults["enabled"]
                target.target_type = defaults["target_type"]
                target.run_every_minutes = defaults["run_every_minutes"]
                target.config = defaults["config"]
                target.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Updated target: {name}")
                )
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"⊘ Skipping existing target: {name} (use --update to modify)"
                    )
                )

        # Optionally disable targets not in config
        if options["disable_missing"]:
            missing = ScrapeTarget.objects.exclude(name__in=processed_names)
            count = missing.count()
            if count > 0:
                if options["dry_run"]:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[DRY RUN] Would disable {count} targets not in config file"
                        )
                    )
                else:
                    missing.update(enabled=False)
                    self.stdout.write(
                        self.style.WARNING(f"⊘ Disabled {count} targets not in config file")
                    )

        # Summary
        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[DRY RUN] Would process {len(processed_names)} targets"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Summary: {created_count} created, {updated_count} updated, "
                    f"{skipped_count} skipped, {len(processed_names)} total processed"
                )
            )


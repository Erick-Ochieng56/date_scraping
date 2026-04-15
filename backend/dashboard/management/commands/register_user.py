"""
Lower-level user registration (optional). Prefer:

  - ``createsuperuser`` — **admin** (Django admin + template dashboard)
  - ``create_staff_user`` — **staff** (React app; same prompts as createsuperuser)

Examples:

  python manage.py register_user jane --role scraper
  python manage.py register_user admin2 --role staff --superuser --email admin@example.com

``--role scraper``: portal group, not Django staff (React **staff** login).
``--role staff``: Django ``is_staff`` (template **admin** dashboard); optional ``--superuser``.
"""
from __future__ import annotations

import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dashboard.permissions import scraper_group_name


class Command(BaseCommand):
    help = "Register a user: portal group (React staff) or Django staff (template admin)."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Login username.")
        parser.add_argument(
            "--email",
            default="",
            help="Email address (optional).",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Password. If omitted, you will be prompted (unless --no-input).",
        )
        parser.add_argument(
            "--role",
            choices=("scraper", "staff"),
            default="scraper",
            help="scraper = React portal + API; staff = admin dashboard + /admin/.",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="With --role staff, also grant superuser (full Django admin).",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Do not prompt for password; --password is required for new users.",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="If the user exists, update password/flags instead of failing.",
        )

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        if not username:
            raise CommandError("Username is required.")

        email = (options.get("email") or "").strip()
        role = options["role"]
        password = options.get("password")
        no_input = options["no_input"]
        update = options["update"]
        superuser = options["superuser"]

        if superuser and role != "staff":
            raise CommandError("--superuser is only valid with --role staff.")

        User = get_user_model()

        if password is None and not no_input:
            p1 = getpass.getpass("Password: ")
            p2 = getpass.getpass("Password (again): ")
            if p1 != p2:
                raise CommandError("Passwords do not match.")
            password = p1
        if not password and not no_input:
            raise CommandError("Password cannot be empty.")
        if no_input and not password:
            # Updating existing user without new password is ok
            pass

        exists = User.objects.filter(username=username).exists()
        if exists and not update:
            raise CommandError(
                f'User "{username}" already exists. Use --update to change password/role.'
            )

        gname = scraper_group_name()
        group, _ = Group.objects.get_or_create(name=gname)

        with transaction.atomic():
            if not exists:
                if not password:
                    raise CommandError("New user requires a password (use --password or prompt).")
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )
                self.stdout.write(self.style.SUCCESS(f'Created user "{username}".'))
            else:
                user = User.objects.get(username=username)
                if password:
                    user.set_password(password)
                    self.stdout.write(self.style.SUCCESS(f'Updated password for "{username}".'))
                if email:
                    user.email = email

            if role == "scraper":
                user.is_staff = False
                user.is_superuser = False
                user.groups.add(group)
                self.stdout.write(f'Role: portal staff / React (group "{gname}", not Django staff).')
            else:
                user.is_staff = True
                if superuser:
                    user.is_superuser = True
                else:
                    user.is_superuser = False
                user.groups.remove(group)
                self.stdout.write(
                    "Role: staff"
                    + (" + superuser" if superuser else "")
                    + " (use /admin/login/ or template dashboard)."
                )

            user.save()

        self.stdout.write(self.style.SUCCESS("Done."))

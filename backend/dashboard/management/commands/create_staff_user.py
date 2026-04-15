"""
Create a **staff** user for the React dashboard.

Interactive and non-interactive behavior matches ``manage.py createsuperuser``:
same prompts (username, email, password ×2) and the same ``--noinput`` rules,
including ``DJANGO_SUPERUSER_PASSWORD`` and ``DJANGO_SUPERUSER_<USERNAME_FIELD>`` /
``DJANGO_SUPERUSER_EMAIL`` env vars for automation.

This does **not** create an **admin** (use ``createsuperuser`` for that).
Staff users are normal accounts in the scraper portal group, not Django admin.
"""
from __future__ import annotations

from contextlib import contextmanager

from django.contrib.auth.management.commands.createsuperuser import (
    Command as CreatesuperuserCommand,
)
from django.contrib.auth.models import Group

from dashboard.permissions import scraper_group_name


@contextmanager
def _patch_manager_create_staff_portal_user(UserModel, database: str):
    """Turn create_superuser() into create_user() + portal group for this command only."""
    db_mgr = UserModel._default_manager.db_manager(database)
    manager_cls = db_mgr.__class__
    original = manager_cls.create_superuser
    gname = scraper_group_name()

    def create_staff_portal_user(self, **user_data):
        password = user_data.pop("password")
        user = self.create_user(password=password, **user_data)
        group, _ = Group.objects.get_or_create(name=gname)
        user.groups.add(group)
        return user

    manager_cls.create_superuser = create_staff_portal_user
    try:
        yield
    finally:
        manager_cls.create_superuser = original


class Command(CreatesuperuserCommand):
    help = (
        "Creates a staff user for the React dashboard. "
        "Same prompts and flags as createsuperuser; does not grant Django admin / superuser."
    )

    def handle(self, *args, **options):
        database = options["database"]
        stdout_write = self.stdout.write

        def write(msg="", *args, **kwargs):
            if isinstance(msg, str) and msg.rstrip() == "Superuser created successfully.":
                msg = (
                    "Staff user created successfully "
                    f'(group "{scraper_group_name()}"; sign in from the React app).'
                )
            return stdout_write(msg, *args, **kwargs)

        self.stdout.write = write
        try:
            with _patch_manager_create_staff_portal_user(self.UserModel, database):
                return super().handle(*args, **options)
        finally:
            self.stdout.write = stdout_write

"""Vercel's build step: refuse to ship a broken or insecure build, then migrate.

Runs from `[tool.vercel.scripts] build` in pyproject.toml. Any failure stops the
deployment, so the previous one keeps serving.
"""

import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

STYLESHEET = settings.BASE_DIR / "static" / "css" / "site.css"


class Command(BaseCommand):
    help = "Check the deployment settings and apply migrations. Used as Vercel's build command."
    requires_system_checks = []  # handle() runs the stricter deploy check itself

    def handle(self, *args, **options):
        if not STYLESHEET.is_file():
            raise CommandError(
                "static/css/site.css is missing. Run `python manage.py tailwind build` and commit the file."
            )

        self.stdout.write("Checking deployment settings…")
        # Warnings fail the build too: DEBUG on, missing HTTPS settings, a swapped
        # Neon URL or a missing scanner contact URL should never reach users.
        call_command("check", deploy=True, fail_level="WARNING")

        if os.environ.get("VERCEL_ENV") == "preview" and os.environ.get("MIGRATE_PREVIEWS") != "1":
            self.stdout.write(
                "Preview deployment: migrations skipped. Set MIGRATE_PREVIEWS=1 once previews "
                "get their own database branch (Neon's Vercel integration does this)."
            )
            return

        self.stdout.write("Applying migrations…")
        call_command("migrate", interactive=False)
        self.stdout.write(self.style.SUCCESS("Ready to deploy."))

"""Build the site stylesheet with the standalone Tailwind CSS binary (no Node.js)."""

import pytailwindcss
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

TAILWIND_VERSION = "v4.3.3"
INPUT = settings.BASE_DIR / "assets" / "css" / "site.css"
OUTPUT = settings.BASE_DIR / "static" / "css" / "site.css"


class Command(BaseCommand):
    help = "Build (minified) or watch static/css/site.css. Downloads the Tailwind binary on first run."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["build", "watch"])

    def handle(self, *args, action, **options):
        cli_args = ["--input", str(INPUT), "--output", str(OUTPUT)]
        cli_args.append("--minify" if action == "build" else "--watch")
        result = pytailwindcss.run(
            cli_args,
            cwd=settings.BASE_DIR,
            live_output=True,
            auto_install=True,
            version=TAILWIND_VERSION,
        )
        if result.returncode != 0:
            raise CommandError(f"Tailwind exited with status {result.returncode}.")

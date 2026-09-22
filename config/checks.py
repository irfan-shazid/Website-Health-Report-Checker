"""Setup checks that catch the easy-to-make mistakes in .env.

They run with runserver, migrate and `manage.py check`, so a bad value shows up
as a plain warning instead of a confusing failure later.
"""

import os
from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Warning, register


def _host(url):
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


@register("config")
def check_neon_urls(app_configs, **kwargs):
    pooled_host = _host(os.environ.get("DATABASE_URL", ""))
    direct_host = _host(os.environ.get("DATABASE_URL_DIRECT", ""))
    issues = []
    if pooled_host.endswith(".neon.tech") and "-pooler" not in pooled_host:
        issues.append(
            Warning(
                "DATABASE_URL points at Neon's direct endpoint, not the pooled one.",
                hint="In Neon, copy the connection string with connection pooling switched on "
                "(its host contains '-pooler') into DATABASE_URL.",
                id="config.W001",
            )
        )
    if "-pooler" in direct_host:
        issues.append(
            Warning(
                "DATABASE_URL_DIRECT points at Neon's pooled endpoint.",
                hint="Migrations and tests need the direct connection string: switch connection "
                "pooling off in Neon and copy that string (no '-pooler' in the host).",
                id="config.W002",
            )
        )
    return issues


@register("config")
def check_scanner_contact_url(app_configs, **kwargs):
    parts = urlsplit(settings.SCANNER_CONTACT_URL)
    if parts.scheme in ("http", "https") and parts.netloc:
        return []
    return [
        Warning(
            "SCANNER_CONTACT_URL is not set to a web address.",
            hint="Set it in .env to a public page about this scanner, e.g. https://example.com/scanner. "
            "Site owners see it in the User-Agent of every request the scanner makes.",
            id="config.W003",
        )
    ]

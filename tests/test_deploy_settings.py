"""Production mode (DEBUG off) can't be imported into the test process, so run it in a subprocess."""

import json
import os
import secrets
import subprocess
import sys

from django.conf import settings

PRODUCTION_ENV = {
    "DEBUG": "False",
    "SECRET_KEY": secrets.token_urlsafe(50),
    "ALLOWED_HOSTS": "reports.example.com",
    "DATABASE_URL": "postgresql://app:pw@ep-x-pooler.example.neon.tech/neondb?sslmode=require",
    "DATABASE_URL_DIRECT": "postgresql://app:pw@ep-x.example.neon.tech/neondb?sslmode=require",
    "TRUSTED_PROXY_HOPS": "0",
    "SECURE_HSTS_PRELOAD": "False",
}


def manage(*args, **env):
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=settings.BASE_DIR,
        env={**os.environ, **PRODUCTION_ENV, **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def production_setting(names, **env):
    code = f"from django.conf import settings as s; import json; print(json.dumps({{n: getattr(s, n, None) for n in {names!r}}}))"
    result = manage("shell", "-c", code, **env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_check_deploy_passes_with_no_warnings():
    result = manage("check", "--deploy", "--fail-level", "WARNING")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no issues" in result.stdout


def test_production_turns_on_https_hsts_and_secure_cookies():
    values = production_setting(
        [
            "SECURE_SSL_REDIRECT",
            "SECURE_HSTS_SECONDS",
            "SECURE_HSTS_INCLUDE_SUBDOMAINS",
            "SECURE_HSTS_PRELOAD",
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SESSION_COOKIE_NAME",
            "CSRF_COOKIE_NAME",
            "SECURE_PROXY_SSL_HEADER",
            "SCANNER_ALLOW_PRIVATE_HOSTS",
        ]
    )

    assert values == {
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        "SECURE_HSTS_PRELOAD": False,
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "SESSION_COOKIE_NAME": "__Host-sessionid",
        "CSRF_COOKIE_NAME": "__Host-csrftoken",
        "SECURE_PROXY_SSL_HEADER": None,
        "SCANNER_ALLOW_PRIVATE_HOSTS": False,
    }


def test_behind_a_proxy_the_forwarded_scheme_is_trusted():
    values = production_setting(["SECURE_PROXY_SSL_HEADER"], TRUSTED_PROXY_HOPS="1")

    assert values["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]


def test_missing_secret_key_stops_startup_with_a_clear_message():
    result = manage("check", SECRET_KEY="")

    assert result.returncode != 0
    assert "SECRET_KEY is not set" in result.stderr

import re
from pathlib import Path

import pytest
from django.conf import settings as django_settings

pytestmark = pytest.mark.django_db

TEMPLATES = Path(django_settings.BASE_DIR) / "templates"
SCRIPTS = Path(django_settings.BASE_DIR) / "static" / "js"


@pytest.mark.parametrize("path", ["/sign-in/", "/robots.txt", "/no-such-page/"])
def test_every_response_carries_the_security_headers(client, path):
    headers = client.get(path).headers

    assert headers["Content-Security-Policy"] == (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert headers["Permissions-Policy"] == "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    assert headers["X-Robots-Tag"] == "noindex, nofollow"


def test_csp_never_allows_inline_or_eval(client):
    policy = client.get("/sign-in/").headers["Content-Security-Policy"]

    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy


def test_signed_in_pages_are_never_cached(signed_in_client):
    cache_control = signed_in_client.get("/").headers["Cache-Control"]

    assert "no-store" in cache_control
    assert "private" in cache_control


def test_session_and_csrf_cookies_are_locked_down(client, operator):
    from tests.conftest import PASSWORD

    client.get("/sign-in/")
    client.post("/sign-in/", {"username": "operator", "password": PASSWORD})

    session = client.cookies[django_settings.SESSION_COOKIE_NAME]
    csrf = client.cookies[django_settings.CSRF_COOKIE_NAME]
    assert session["httponly"] and session["samesite"] == "Lax"
    assert csrf["httponly"] and csrf["samesite"] == "Lax"
    assert session["max-age"] == 12 * 60 * 60


def test_session_id_changes_on_sign_in(client, operator):
    from tests.conftest import PASSWORD

    client.get("/sign-in/")
    client.session.save()
    before = client.session.session_key

    client.post("/sign-in/", {"username": "operator", "password": PASSWORD})

    assert client.session.session_key != before


def test_robots_txt_asks_every_crawler_to_stay_out(client):
    response = client.get("/robots.txt")

    assert response["Content-Type"].startswith("text/plain")
    assert response.content.decode() == "User-agent: *\nDisallow: /\n"


def test_styleguide_is_not_routed_when_debug_is_off(signed_in_client):
    assert signed_in_client.get("/styleguide/").status_code == 404


def test_admin_requires_staff(signed_in_client):
    response = signed_in_client.get("/admin/")

    assert response.status_code == 302
    assert response["Location"].startswith("/admin/login/")


# The CSP forbids inline code, so templates and scripts must never depend on it.

def all_templates():
    return sorted(TEMPLATES.rglob("*.html")) + sorted(TEMPLATES.rglob("*.svg"))


@pytest.mark.parametrize("template", all_templates(), ids=lambda p: p.relative_to(TEMPLATES).as_posix())
def test_templates_have_no_inline_scripts_styles_or_handlers(template):
    html = template.read_text(encoding="utf-8")

    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "inline <script>"
    assert not re.search(r"<style\b", html), "<style> block"
    assert not re.search(r"\sstyle=", html), "style attribute"
    assert not re.search(r"\son[a-z]+=", html), "inline event handler"


@pytest.mark.parametrize("script", sorted(SCRIPTS.glob("*.js")), ids=lambda p: p.name)
def test_scripts_avoid_eval_and_html_injection(script):
    source = script.read_text(encoding="utf-8")

    for pattern in (r"\beval\(", r"new Function\(", r"\.innerHTML\s*=", r"\.outerHTML\s*=", r"insertAdjacentHTML", r"document\.write"):
        assert not re.search(pattern, source), pattern

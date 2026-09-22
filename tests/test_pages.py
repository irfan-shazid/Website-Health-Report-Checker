import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory

from reports.views import styleguide

pytestmark = pytest.mark.django_db


def test_dashboard_renders_for_a_signed_in_user(signed_in_client):
    response = signed_in_client.get("/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "<title>Scans · Site Health Report</title>" in html
    assert '<h1 class="text-h1 font-bold tracking-tight">Inspect a website</h1>' in html
    assert 'aria-current="page">Scans</a>' in html
    assert "No scans yet" in html
    assert "Signed in as" in html and "operator" in html


def test_layout_has_landmarks_and_a_skip_link(signed_in_client):
    html = signed_in_client.get("/").content.decode()

    assert '<a class="skip-link" href="#main">Skip to main content</a>' in html
    assert '<main id="main"' in html
    assert '<nav aria-label="Main">' in html
    assert "<header" in html and "<footer" in html


def test_sign_out_is_a_form_with_csrf_protection(signed_in_client):
    html = signed_in_client.get("/").content.decode()

    assert 'action="/sign-out/"' in html
    assert "csrfmiddlewaretoken" in html


def test_theme_switch_is_hidden_until_javascript_runs(signed_in_client):
    html = signed_in_client.get("/").content.decode()

    assert '<fieldset class="theme-switch" data-theme-switch hidden>' in html
    assert '<legend class="sr-only">Color theme</legend>' in html


def test_admin_link_only_for_staff(signed_in_client, operator):
    assert "Administration" not in signed_in_client.get("/").content.decode()

    operator.is_staff = True
    operator.save()

    assert "Administration" in signed_in_client.get("/").content.decode()


def test_missing_pages_get_the_designed_404(client):
    response = client.get("/no-such-page/")

    assert response.status_code == 404
    assert "We can't find that page" in response.content.decode()


@pytest.mark.parametrize(
    ("template", "heading"),
    [
        ("400.html", "Something about that request wasn"),
        ("403.html", "You don"),
        ("403_csrf.html", "That form has expired"),
        ("429.html", "Too many requests, please slow down"),
        ("500.html", "Something went wrong on our side"),
    ],
)
def test_error_pages_render_without_a_request(template, heading):
    # Django renders 500.html with no context at all, so none of them may depend on one.
    html = render_to_string(template)

    assert heading in html
    assert "Go to your scans" in html or template == "429.html"


def test_styleguide_template_renders(operator):
    request = RequestFactory().get("/styleguide/")
    request.user = operator

    response = styleguide(request)

    assert response.status_code == 200
    assert "Style reference" in response.content.decode()


def test_static_assets_are_served_with_the_page(client):
    for path in ("/static/css/site.css", "/static/js/app.js", "/static/js/theme-init.js", "/static/img/favicon.svg"):
        assert client.get(path).status_code == 200, path


def test_favicon_ico_points_at_the_svg_icon(client):
    response = client.get("/favicon.ico")

    assert response.status_code == 302
    assert response["Location"] == "/static/img/favicon.svg"

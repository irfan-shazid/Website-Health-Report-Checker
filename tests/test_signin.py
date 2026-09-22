from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from scanner.models import LoginAttempt
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

SIGN_IN = "/sign-in/"


def sign_in(client, username="operator", password="wrong password", ip="203.0.113.10", path=SIGN_IN, **extra):
    return client.post(path, {"username": username, "password": password, **extra}, REMOTE_ADDR=ip)


def is_signed_in(client):
    return "_auth_user_id" in client.session


def test_dashboard_requires_sign_in(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"] == "/sign-in/?next=/"


def test_sign_in_page_renders_an_accessible_form(client):
    response = client.get(SIGN_IN)
    html = response.content.decode()

    assert response.status_code == 200
    assert '<label class="label" for="id_username">Username</label>' in html
    assert 'autocomplete="username"' in html
    assert 'autocomplete="current-password"' in html
    assert '<main id="main"' in html
    assert '<meta name="robots" content="noindex, nofollow">' in html


def test_signed_in_users_skip_the_sign_in_page(signed_in_client):
    response = signed_in_client.get(SIGN_IN)

    assert response.status_code == 302
    assert response["Location"] == "/"


def test_correct_credentials_sign_in_and_go_to_the_dashboard(client, operator):
    response = sign_in(client, password=PASSWORD)

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert is_signed_in(client)


def test_next_takes_you_back_to_the_page_you_wanted(client, operator):
    response = sign_in(client, password=PASSWORD, next="/?page=2")

    assert response["Location"] == "/?page=2"


def test_next_cannot_send_you_to_another_site(client, operator):
    response = sign_in(client, password=PASSWORD, next="https://evil.example/phish")

    assert response["Location"] == "/"


def test_wrong_password_explains_without_revealing_which_part_was_wrong(client, operator):
    response = sign_in(client)
    html = response.content.decode()

    assert response.status_code == 200
    assert not is_signed_in(client)
    assert "That username and password don&#x27;t match." in html
    assert 'value="operator"' in html  # username is kept
    assert "wrong password" not in html  # password is never echoed back


def test_unknown_username_gets_the_same_message(client, operator):
    html = sign_in(client, username="nobody").content.decode()

    assert "That username and password don&#x27;t match." in html


def test_empty_form_points_at_each_missing_field(client):
    html = sign_in(client, username="", password="").content.decode()

    assert "Enter your username." in html
    assert "Enter your password." in html
    assert 'aria-invalid="true" aria-describedby="id_username_error"' in html


def test_warns_when_two_tries_are_left(client, operator):
    for _ in range(3):
        response = sign_in(client)

    assert "2 more tries before sign-in is paused for 15 minutes." in response.content.decode()


def test_fifth_failure_pauses_sign_in_and_says_so(client, operator):
    for _ in range(5):
        response = sign_in(client)

    assert "Sign-in is paused after too many attempts. Try again in 15 minutes." in response.content.decode()


def test_paused_sign_in_refuses_even_the_correct_password(client, operator):
    for _ in range(5):
        sign_in(client)

    response = sign_in(client, password=PASSWORD)

    assert response.status_code == 429
    assert 0 < int(response["Retry-After"]) <= 15 * 60
    assert "Sign-in is paused after too many attempts" in response.content.decode()
    assert not is_signed_in(client)


def test_attempts_during_a_pause_are_not_stored(client, operator):
    for _ in range(12):
        sign_in(client)

    assert LoginAttempt.objects.count() == 5


def test_pause_is_shown_when_the_page_is_reloaded(client, operator):
    for _ in range(5):
        sign_in(client)

    html = client.get(SIGN_IN, REMOTE_ADDR="203.0.113.10").content.decode()

    assert "Sign-in is paused after too many attempts" in html


def test_pause_does_not_affect_other_clients(client, operator):
    for _ in range(5):
        sign_in(client, ip="203.0.113.10")

    response = sign_in(Client(), password=PASSWORD, ip="198.51.100.7")

    assert response.status_code == 302


def test_guessing_one_username_from_many_addresses_pauses_that_username(client, operator):
    for n in range(10):
        sign_in(Client(), ip=f"198.51.100.{n}")

    response = sign_in(client, password=PASSWORD, ip="192.0.2.99")

    assert response.status_code == 429
    assert not is_signed_in(client)


def test_ipv6_clients_are_grouped_by_their_64_block(client, operator):
    for n in range(1, 6):
        sign_in(Client(), ip=f"2001:db8:1:2::{n}")

    response = sign_in(client, password=PASSWORD, ip="2001:db8:1:2:ffff::1")

    assert response.status_code == 429


def test_pause_lifts_once_the_failures_are_old_enough(client, operator):
    for _ in range(5):
        sign_in(client)
    LoginAttempt.objects.update(created_at=timezone.now() - timedelta(minutes=16))

    response = sign_in(client, password=PASSWORD)

    assert response.status_code == 302


def test_signing_in_clears_earlier_failures(client, operator):
    for _ in range(3):
        sign_in(client)

    sign_in(client, password=PASSWORD)

    assert LoginAttempt.objects.count() == 0


def test_failures_older_than_a_day_are_deleted(client, operator):
    sign_in(client)
    LoginAttempt.objects.update(created_at=timezone.now() - timedelta(days=2))

    sign_in(client, ip="198.51.100.1")

    assert LoginAttempt.objects.count() == 1


def test_admin_login_shares_the_same_limit(client, operator):
    operator.is_staff = True
    operator.save()
    for _ in range(5):
        sign_in(client, path="/admin/login/")

    sign_in(client, password=PASSWORD, path="/admin/login/")

    assert not is_signed_in(client)


def test_sign_out_needs_a_post(signed_in_client):
    assert signed_in_client.get("/sign-out/").status_code == 405
    assert is_signed_in(signed_in_client)


def test_sign_out_ends_the_session_and_confirms(signed_in_client):
    response = signed_in_client.post("/sign-out/", follow=True)

    assert not is_signed_in(signed_in_client)
    assert response.redirect_chain[-1][0] == "/sign-in/"
    assert "You&#x27;ve signed out." in response.content.decode()


def test_sign_in_form_is_protected_against_cross_site_posts(operator):
    client = Client(enforce_csrf_checks=True)

    response = sign_in(client, password=PASSWORD)

    assert response.status_code == 403
    assert "That form has expired" in response.content.decode()
    assert not is_signed_in(client)


def test_being_sent_to_sign_in_explains_why(client):
    html = client.get("/sign-in/?next=/styleguide/").content.decode()

    assert "Sign in to continue to that page." in html


def test_plain_visit_to_sign_in_has_the_usual_intro(client):
    html = client.get("/sign-in/").content.decode()

    assert "Sign in to run scans and read reports." in html


def test_sign_ins_and_sign_outs_are_logged(client, operator, caplog):
    caplog.set_level("INFO", logger="reports.signin")

    sign_in(client, password=PASSWORD, ip="198.51.100.9")
    client.post("/sign-out/", REMOTE_ADDR="198.51.100.9")

    assert "Signed in: 'operator' from 198.51.100.9" in caplog.text
    assert "Signed out: 'operator' from 198.51.100.9" in caplog.text


def test_lockouts_are_logged(client, operator, caplog):
    caplog.set_level("WARNING", logger="reports.signin")

    for _ in range(5):
        sign_in(client)

    assert "Sign-in paused for client 203.0.113.10, username 'operator'" in caplog.text

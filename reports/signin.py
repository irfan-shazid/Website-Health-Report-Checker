"""Pause sign-in after repeated failures, per client and per username.

Enforced in the authentication backend, so the admin login is covered too.
Failures are stored in the database so every web process sees the same count.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.dispatch import receiver
from django.utils import timezone

from reports.ratelimit import client_key
from scanner.models import LoginAttempt

logger = logging.getLogger(__name__)

KEEP_FAILURES_FOR = timedelta(days=1)


def normalize_username(username):
    return (username or "").strip().lower()[:150]


def _checks(request, username):
    yield LoginAttempt.objects.filter(client=client_key(request)), settings.SIGN_IN_LIMIT_PER_CLIENT
    username = normalize_username(username)
    if username:
        yield LoginAttempt.objects.filter(username=username), settings.SIGN_IN_LIMIT_PER_USERNAME


def _recent(attempts, window, now):
    return list(
        attempts.filter(created_at__gte=now - timedelta(seconds=window))
        .order_by("created_at")
        .values_list("created_at", flat=True)
    )


def paused_until(request, username=""):
    """When sign-in reopens for this client and username, or None if it isn't paused."""
    now = timezone.now()
    reopen_times = []
    for attempts, (limit, window) in _checks(request, username):
        recent = _recent(attempts, window, now)
        if len(recent) >= limit:
            # Sign-in reopens once enough of these failures have aged out of the window.
            reopen_times.append(recent[len(recent) - limit] + timedelta(seconds=window))
    return max(reopen_times, default=None)


def attempts_left(request, username=""):
    now = timezone.now()
    return min(limit - len(_recent(attempts, window, now)) for attempts, (limit, window) in _checks(request, username))


class ThrottledModelBackend(ModelBackend):
    """Django's ModelBackend, but it won't check passwords while sign-in is paused."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if request is not None and paused_until(request, username):
            raise PermissionDenied
        return super().authenticate(request, username=username, password=password, **kwargs)


@receiver(user_login_failed)
def record_failed_sign_in(sender, credentials, request=None, **kwargs):
    if request is None:
        return
    username = credentials.get("username", "")
    # While paused, attempts aren't stored: the pause can't be stretched forever and a
    # flood of guesses can't fill the database.
    if paused_until(request, username):
        return

    LoginAttempt.objects.create(client=client_key(request), username=normalize_username(username))
    LoginAttempt.objects.filter(created_at__lt=timezone.now() - KEEP_FAILURES_FOR).delete()
    if paused_until(request, username):
        logger.warning("Sign-in paused for client %s, username %r", client_key(request), username)


@receiver(user_logged_in)
def clear_failed_sign_ins(sender, request, user, **kwargs):
    if request is None:
        return
    LoginAttempt.objects.filter(
        Q(client=client_key(request)) | Q(username=normalize_username(user.get_username()))
    ).delete()

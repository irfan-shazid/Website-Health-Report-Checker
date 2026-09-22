import math

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from reports.signin import paused_until


def minutes_until(moment):
    minutes = max(1, math.ceil((moment - timezone.now()).total_seconds() / 60))
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


class SignInForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "That username and password don't match. Both are case-sensitive.",
        "paused": "Sign-in is paused after too many attempts. Try again in %(wait)s.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].error_messages["required"] = "Enter your username."
        self.fields["password"].error_messages["required"] = "Enter your password."
        self.paused_until = None

    def clean(self):
        self.paused_until = paused_until(self.request, self.data.get("username", ""))
        if self.paused_until:
            raise forms.ValidationError(
                self.error_messages["paused"],
                code="paused",
                params={"wait": minutes_until(self.paused_until)},
            )
        return super().clean()

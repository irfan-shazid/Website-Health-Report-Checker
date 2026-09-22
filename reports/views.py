from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.http import require_GET

from reports.forms import SignInForm, minutes_until
from reports.signin import attempts_left, paused_until

# Warn about the coming pause when this many tries (or fewer) remain.
WARN_WHEN_ATTEMPTS_LEFT = 2


class SignInView(LoginView):
    form_class = SignInForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        context["pause_length"] = settings.SIGN_IN_LIMIT_PER_CLIENT[1] // 60

        if not form.is_bound:
            until = paused_until(self.request)
            if until:
                context["paused_for"] = minutes_until(until)
        elif form.errors and not form.paused_until:
            username = form.data.get("username", "")
            until = paused_until(self.request, username)
            if until:
                context["paused_for"] = minutes_until(until)
            else:
                left = attempts_left(self.request, username)
                if 0 < left <= WARN_WHEN_ATTEMPTS_LEFT:
                    context["attempts_left"] = left
        return context

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if form.paused_until:
            response.status_code = 429
            wait = (form.paused_until - timezone.now()).total_seconds()
            response["Retry-After"] = str(max(1, int(wait)))
        return response


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You've signed out.")
        return response


@login_required
def dashboard(request):
    return render(request, "reports/dashboard.html")


@require_GET
def robots_txt(request):
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


@require_GET
def favicon(request):
    # Temporary redirect: the target's hashed name changes whenever the icon does.
    return redirect(static("img/favicon.svg"))


@login_required
def styleguide(request):
    """Design tokens and components in both themes. Only routed when DEBUG is on."""
    return render(request, "reports/styleguide.html")

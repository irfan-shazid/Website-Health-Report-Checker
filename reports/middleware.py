from django.conf import settings
from django.shortcuts import render
from django.utils.cache import patch_cache_control

from reports.ratelimit import client_key, hit

# No inline scripts or styles anywhere, so nothing needs 'unsafe-inline' or 'unsafe-eval'.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

PERMISSIONS_POLICY = "camera=(), geolocation=(), microphone=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    """Headers Django doesn't set itself. Sits near the top so every response gets them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        # Nothing in this app belongs in search results.
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and "Cache-Control" not in response.headers:
            # Keep signed-in pages out of shared caches and the back/forward cache after sign-out.
            patch_cache_control(response, private=True, no_store=True)
        return response


class RateLimitMiddleware:
    """Coarse per-client request limits. Needs AuthenticationMiddleware before it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            key = f"user:{request.user.pk}"
            limit, window = settings.RATE_LIMIT_SIGNED_IN
        else:
            key = f"client:{client_key(request)}"
            limit, window = settings.RATE_LIMIT_ANONYMOUS

        retry_after = hit(key, limit, window)
        if retry_after:
            return too_many_requests(request, retry_after)
        return self.get_response(request)


def too_many_requests(request, retry_after):
    response = render(request, "429.html", {"retry_after": retry_after}, status=429)
    response["Retry-After"] = str(retry_after)
    return response

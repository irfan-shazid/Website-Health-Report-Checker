"""Identify clients and count their requests in fixed time windows."""

import ipaddress
import time

from django.conf import settings
from django.core.cache import caches


def client_ip(request):
    """The client's IP address, trusting X-Forwarded-For only as far as TRUSTED_PROXY_HOPS."""
    hops = settings.TRUSTED_PROXY_HOPS
    if hops:
        forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")]
        forwarded = [part for part in forwarded if part]
        if len(forwarded) >= hops:
            try:
                return str(ipaddress.ip_address(forwarded[-hops]))
            except ValueError:
                pass
    return request.META.get("REMOTE_ADDR", "")


def client_key(request):
    """A rate-limit identity for the client.

    IPv6 addresses are grouped by /64, because a single connection usually
    controls a whole /64 and could otherwise rotate addresses to reset limits.
    """
    raw = client_ip(request)
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return raw or "unknown"
    if address.version == 6:
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def hit(key, limit, window):
    """Count one request against `key`. Returns 0 if allowed, else seconds until the window resets."""
    cache = caches["ratelimit"]
    now = time.time()
    bucket = int(now // window)
    cache_key = f"{key}:{window}:{bucket}"
    cache.add(cache_key, 0, timeout=window + 1)
    try:
        count = cache.incr(cache_key)
    except ValueError:
        # The entry expired between add() and incr().
        cache.set(cache_key, 1, timeout=window + 1)
        count = 1
    if count <= limit:
        return 0
    return max(1, int((bucket + 1) * window - now) + 1)

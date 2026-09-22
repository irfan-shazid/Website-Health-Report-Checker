import pytest
from django.test import RequestFactory

from reports.ratelimit import client_ip, client_key, hit


def request_from(remote="203.0.113.10", forwarded=None):
    extra = {"REMOTE_ADDR": remote}
    if forwarded is not None:
        extra["HTTP_X_FORWARDED_FOR"] = forwarded
    return RequestFactory().get("/", **extra)


class TestClientIp:
    def test_forwarded_header_is_ignored_without_trusted_proxies(self, settings):
        settings.TRUSTED_PROXY_HOPS = 0

        assert client_ip(request_from(forwarded="1.2.3.4")) == "203.0.113.10"

    def test_one_proxy_takes_the_address_it_appended(self, settings):
        settings.TRUSTED_PROXY_HOPS = 1

        assert client_ip(request_from(forwarded="6.6.6.6, 198.51.100.4")) == "198.51.100.4"

    def test_two_proxies_skip_the_inner_proxy(self, settings):
        settings.TRUSTED_PROXY_HOPS = 2

        request = request_from(forwarded="6.6.6.6, 198.51.100.4, 10.0.0.2")

        assert client_ip(request) == "198.51.100.4"

    def test_spoofed_entries_left_of_the_trusted_ones_are_ignored(self, settings):
        settings.TRUSTED_PROXY_HOPS = 1

        request = request_from(forwarded="127.0.0.1, 10.0.0.1, 198.51.100.4")

        assert client_ip(request) == "198.51.100.4"

    def test_garbage_header_falls_back_to_the_connection_address(self, settings):
        settings.TRUSTED_PROXY_HOPS = 1

        assert client_ip(request_from(forwarded="not-an-ip")) == "203.0.113.10"

    def test_missing_header_falls_back_to_the_connection_address(self, settings):
        settings.TRUSTED_PROXY_HOPS = 1

        assert client_ip(request_from()) == "203.0.113.10"


class TestClientKey:
    def test_ipv4_is_used_as_is(self):
        assert client_key(request_from("198.51.100.4")) == "198.51.100.4"

    def test_ipv6_is_grouped_by_64(self):
        assert client_key(request_from("2001:db8:1:2:3:4:5:6")) == "2001:db8:1:2::/64"

    def test_ipv4_mapped_ipv6_counts_as_the_ipv4_address(self):
        assert client_key(request_from("::ffff:198.51.100.4")) == "198.51.100.4"


class TestHit:
    def test_allows_up_to_the_limit_then_asks_to_wait(self):
        results = [hit("test:a", limit=3, window=60) for _ in range(4)]

        assert results[:3] == [0, 0, 0]
        assert 1 <= results[3] <= 61

    def test_keys_are_counted_separately(self):
        for _ in range(3):
            hit("test:a", limit=3, window=60)

        assert hit("test:b", limit=3, window=60) == 0


@pytest.mark.django_db
class TestMiddleware:
    def test_anonymous_clients_are_limited_per_address(self, client, settings):
        settings.RATE_LIMIT_ANONYMOUS = (3, 60)
        for _ in range(3):
            assert client.get("/robots.txt", REMOTE_ADDR="198.51.100.4").status_code == 200

        response = client.get("/robots.txt", REMOTE_ADDR="198.51.100.4")

        assert response.status_code == 429
        assert int(response["Retry-After"]) >= 1
        assert "Too many requests, please slow down" in response.content.decode()
        assert client.get("/robots.txt", REMOTE_ADDR="198.51.100.5").status_code == 200

    def test_limited_responses_still_carry_security_headers(self, client, settings):
        settings.RATE_LIMIT_ANONYMOUS = (1, 60)
        client.get("/robots.txt")

        response = client.get("/robots.txt")

        assert response.status_code == 429
        assert "Content-Security-Policy" in response.headers

    def test_signed_in_users_are_counted_per_account_with_a_higher_limit(self, signed_in_client, settings):
        settings.RATE_LIMIT_ANONYMOUS = (1, 60)
        settings.RATE_LIMIT_SIGNED_IN = (3, 60)

        statuses = [signed_in_client.get("/", REMOTE_ADDR=f"198.51.100.{n}").status_code for n in range(4)]

        assert statuses == [200, 200, 200, 429]

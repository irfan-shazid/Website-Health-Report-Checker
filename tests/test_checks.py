import pytest

from config.checks import check_neon_urls, check_scanner_contact_url

POOLED = "postgresql://app:pw@ep-cool-123-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"
DIRECT = "postgresql://app:pw@ep-cool-123.eu-central-1.aws.neon.tech/neondb?sslmode=require"


def ids(issues):
    return [issue.id for issue in issues]


@pytest.fixture
def neon_env(monkeypatch):
    def use(pooled, direct):
        monkeypatch.setenv("DATABASE_URL", pooled)
        monkeypatch.setenv("DATABASE_URL_DIRECT", direct)

    return use


def test_correct_neon_urls_pass(neon_env):
    neon_env(POOLED, DIRECT)

    assert check_neon_urls(None) == []


def test_swapped_neon_urls_are_both_flagged(neon_env):
    neon_env(DIRECT, POOLED)

    assert ids(check_neon_urls(None)) == ["config.W001", "config.W002"]


def test_direct_url_used_for_both_is_flagged(neon_env):
    neon_env(DIRECT, DIRECT)

    assert ids(check_neon_urls(None)) == ["config.W001"]


def test_non_neon_databases_are_left_alone(neon_env):
    neon_env("postgresql://postgres@localhost:5432/app", "postgresql://postgres@localhost:5432/app")

    assert check_neon_urls(None) == []


@pytest.mark.parametrize("value", ["", "example.com", "mailto:me@example.com", "https://"])
def test_missing_or_invalid_contact_url_is_flagged(settings, value):
    settings.SCANNER_CONTACT_URL = value

    assert ids(check_scanner_contact_url(None)) == ["config.W003"]


def test_contact_url_passes(settings):
    settings.SCANNER_CONTACT_URL = "https://example.com/scanner"

    assert check_scanner_contact_url(None) == []

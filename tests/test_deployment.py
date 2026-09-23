"""Everything Vercel relies on: dependency files, vercel.json, the build step and Vercel-mode settings."""

import json
import tomllib
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from tests.test_deploy_settings import manage, production_setting

ROOT = Path(settings.BASE_DIR)

# What Vercel sets on a production deployment (see its system environment variables).
VERCEL_ENV = {
    "VERCEL": "1",
    "VERCEL_ENV": "production",
    "VERCEL_URL": "site-health-report-abc123.vercel.app",
    "VERCEL_BRANCH_URL": "site-health-report-git-main-acme.vercel.app",
    "VERCEL_PROJECT_PRODUCTION_URL": "reports.example.com",
}
# Variables a developer's shell or .env might have that Vercel would not.
NOT_ON_VERCEL = ("DEBUG", "ALLOWED_HOSTS", "TRUSTED_PROXY_HOPS", "DATABASE_URL_DIRECT")


def requirement_lines(path):
    lines = (line.strip() for line in (ROOT / path).read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith(("#", "-r"))]


class TestDependencyFiles:
    def test_pyproject_and_requirements_list_the_same_runtime_packages(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        assert sorted(pyproject["project"]["dependencies"]) == sorted(requirement_lines("requirements.txt"))

    def test_test_and_build_tools_stay_out_of_the_deployment(self):
        runtime = " ".join(requirement_lines("requirements.txt")).lower()

        for tool in ("pytest", "respx", "pytailwindcss"):
            assert tool not in runtime

    def test_dev_requirements_include_the_runtime_ones(self):
        assert "-r requirements.txt" in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

    def test_python_version_is_pinned_for_vercel(self):
        assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


class TestVercelConfig:
    def test_function_settings_point_at_the_real_wsgi_entrypoint(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        entrypoint = settings.WSGI_APPLICATION.rsplit(".", 1)[0].replace(".", "/") + ".py"

        assert list(config["functions"]) == [entrypoint]
        assert (ROOT / entrypoint).is_file()

    def test_build_step_is_predeploy(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        assert pyproject["tool"]["vercel"]["scripts"]["build"] == "python manage.py predeploy"

    def test_local_secrets_are_never_uploaded(self):
        ignored = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()

        assert ".env" in ignored and ".env.*" in ignored and ".venv/" in ignored

    def test_committed_stylesheet_matches_the_templates(self, tmp_path):
        """Vercel serves the committed CSS as-is, so it must be rebuilt after template changes."""
        pytailwindcss = pytest.importorskip("pytailwindcss")
        from pytailwindcss.utils import get_bin_path

        from reports.management.commands.tailwind import INPUT, OUTPUT, TAILWIND_VERSION

        if not get_bin_path(TAILWIND_VERSION).exists():
            pytest.skip("Tailwind binary not downloaded yet; run `python manage.py tailwind build` once.")
        fresh = tmp_path / "site.css"
        pytailwindcss.run(
            ["--input", str(INPUT), "--output", str(fresh), "--minify"], cwd=ROOT, version=TAILWIND_VERSION
        )

        assert fresh.read_text(encoding="utf-8").strip() == OUTPUT.read_text(encoding="utf-8").strip(), (
            "static/css/site.css is out of date: run `python manage.py tailwind build` and commit it."
        )


class TestPredeploy:
    def run(self, monkeypatch, **env):
        for name in ("VERCEL_ENV", "MIGRATE_PREVIEWS"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        with mock.patch("reports.management.commands.predeploy.call_command") as called:
            call_command("predeploy")
        return [c.args[0] for c in called.call_args_list], called

    def test_production_build_checks_then_migrates(self, monkeypatch):
        commands, called = self.run(monkeypatch, VERCEL_ENV="production")

        assert commands == ["check", "migrate"]
        assert called.call_args_list[0].kwargs == {"deploy": True, "fail_level": "WARNING"}

    def test_preview_build_does_not_touch_the_database_by_default(self, monkeypatch):
        commands, _ = self.run(monkeypatch, VERCEL_ENV="preview")

        assert commands == ["check"]

    def test_preview_build_migrates_its_own_database_branch_when_asked(self, monkeypatch):
        commands, _ = self.run(monkeypatch, VERCEL_ENV="preview", MIGRATE_PREVIEWS="1")

        assert commands == ["check", "migrate"]

    def test_missing_stylesheet_stops_the_build(self, monkeypatch, tmp_path):
        monkeypatch.setattr("reports.management.commands.predeploy.STYLESHEET", tmp_path / "missing.css")

        with pytest.raises(CommandError, match="site.css is missing"):
            call_command("predeploy")

    def test_insecure_settings_stop_the_build(self):
        result = manage("predeploy", DEBUG="True")

        assert result.returncode != 0
        assert "security.W018" in result.stderr  # DEBUG must be off in deployment


class TestVercelSettings:
    def test_vercel_hosts_proxy_and_https_are_configured_automatically(self):
        values = production_setting(
            ["DEBUG", "ALLOWED_HOSTS", "TRUSTED_PROXY_HOPS", "SECURE_PROXY_SSL_HEADER", "SECURE_SSL_REDIRECT"],
            drop=NOT_ON_VERCEL,
            **VERCEL_ENV,
        )

        assert values == {
            "DEBUG": False,  # even though a local .env may say otherwise
            "ALLOWED_HOSTS": [
                "site-health-report-abc123.vercel.app",
                "site-health-report-git-main-acme.vercel.app",
                "reports.example.com",
            ],
            "TRUSTED_PROXY_HOPS": 1,
            "SECURE_PROXY_SSL_HEADER": ["HTTP_X_FORWARDED_PROTO", "https"],
            "SECURE_SSL_REDIRECT": True,
        }

    def test_extra_custom_domains_can_be_added(self):
        values = production_setting(
            ["ALLOWED_HOSTS"], drop=NOT_ON_VERCEL, ALLOWED_HOSTS="www.reports.example.com", **VERCEL_ENV
        )

        assert values["ALLOWED_HOSTS"][0] == "www.reports.example.com"
        assert "reports.example.com" in values["ALLOWED_HOSTS"]

    def test_neon_integration_variables_are_enough(self):
        result = manage(
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
            drop=NOT_ON_VERCEL,
            DATABASE_URL_UNPOOLED="postgresql://app:pw@ep-x.example.neon.tech/neondb?sslmode=require",
            **VERCEL_ENV,
        )

        assert result.returncode == 0, result.stdout + result.stderr

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.database import database_config, use_direct_connection

POOLED = "postgresql://app:pw@ep-cool-123-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"
DIRECT = "postgresql://app:pw@ep-cool-123.eu-central-1.aws.neon.tech/neondb?sslmode=require"
ENV = {"DATABASE_URL": POOLED, "DATABASE_URL_DIRECT": DIRECT}


@pytest.mark.parametrize("command", ["runserver", "qcluster", "shell", "createsuperuser"])
def test_everyday_commands_use_the_pooled_endpoint(command):
    config = database_config(["manage.py", command], ENV)

    assert config["HOST"] == "ep-cool-123-pooler.eu-central-1.aws.neon.tech"
    assert config["DISABLE_SERVER_SIDE_CURSORS"] is True
    assert config["CONN_MAX_AGE"] == 0


@pytest.mark.parametrize("command", ["migrate", "makemigrations", "showmigrations", "sqlmigrate"])
def test_migration_commands_use_the_direct_endpoint(command):
    config = database_config(["manage.py", command, "scanner"], ENV)

    assert config["HOST"] == "ep-cool-123.eu-central-1.aws.neon.tech"
    assert config["DISABLE_SERVER_SIDE_CURSORS"] is False


def test_web_server_under_gunicorn_uses_the_pooled_endpoint():
    config = database_config(["gunicorn", "config.wsgi"], ENV)

    assert "-pooler" in config["HOST"]


def test_use_direct_db_flag_forces_the_direct_endpoint():
    config = database_config(["manage.py", "runserver"], {**ENV, "USE_DIRECT_DB": "1"})

    assert "-pooler" not in config["HOST"]


def test_test_runs_use_the_direct_endpoint():
    assert use_direct_connection(["pytest"], ENV, running_tests=True)


def test_no_subcommand_uses_the_pooled_endpoint():
    assert not use_direct_connection(["manage.py"], ENV)


def test_missing_url_explains_what_to_set():
    with pytest.raises(ImproperlyConfigured, match=r"DATABASE_URL_DIRECT \(or DATABASE_URL_UNPOOLED\) is not set"):
        database_config(["manage.py", "migrate"], {"DATABASE_URL": POOLED})


def test_sslmode_defaults_to_require_when_the_url_omits_it():
    env = {"DATABASE_URL": POOLED.split("?")[0]}

    assert database_config(["manage.py", "runserver"], env)["OPTIONS"]["sslmode"] == "require"


def test_stricter_sslmode_is_kept():
    env = {"DATABASE_URL": POOLED.replace("sslmode=require", "sslmode=verify-full")}

    assert database_config(["manage.py", "runserver"], env)["OPTIONS"]["sslmode"] == "verify-full"


@pytest.mark.parametrize("mode", ["disable", "allow", "prefer"])
def test_weak_sslmode_is_rejected(mode):
    env = {"DATABASE_URL": POOLED.replace("sslmode=require", f"sslmode={mode}")}

    with pytest.raises(ImproperlyConfigured, match=f"sslmode={mode}"):
        database_config(["manage.py", "runserver"], env)


def test_neon_channel_binding_option_is_passed_through():
    env = {"DATABASE_URL": POOLED + "&channel_binding=require"}

    assert database_config(["manage.py", "runserver"], env)["OPTIONS"]["channel_binding"] == "require"


def test_neon_vercel_integration_name_for_the_direct_url_is_accepted():
    env = {"DATABASE_URL": POOLED, "DATABASE_URL_UNPOOLED": DIRECT}

    config = database_config(["manage.py", "migrate"], env)

    assert config["HOST"] == "ep-cool-123.eu-central-1.aws.neon.tech"


def test_explicit_direct_url_wins_over_the_integration_name():
    env = {**ENV, "DATABASE_URL_UNPOOLED": "postgresql://x:y@other.neon.tech/db?sslmode=require"}

    assert database_config(["manage.py", "migrate"], env)["HOST"] == "ep-cool-123.eu-central-1.aws.neon.tech"


def test_predeploy_uses_the_direct_endpoint():
    assert database_config(["manage.py", "predeploy"], ENV)["HOST"] == "ep-cool-123.eu-central-1.aws.neon.tech"

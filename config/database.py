"""Choose between Neon's pooled and direct connection strings.

The pooled endpoint runs PgBouncer in transaction mode. That suits the web app
and the worker, but not migrations (DDL and advisory locks want a real session)
or creating the test database, so those use the direct endpoint instead.
"""

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Commands that need a session-level connection to the database.
DIRECT_COMMANDS = frozenset(
    {
        "makemigrations",
        "migrate",
        "optimizemigration",
        "predeploy",
        "showmigrations",
        "sqlmigrate",
        "squashmigrations",
        "test",
    }
)

SECURE_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})


def use_direct_connection(argv, environ, running_tests=False):
    if environ.get("USE_DIRECT_DB") == "1" or running_tests:
        return True
    return len(argv) > 1 and argv[1] in DIRECT_COMMANDS


def database_config(argv, environ, running_tests=False):
    direct = use_direct_connection(argv, environ, running_tests)
    if direct:
        # Neon's Vercel integration names the direct string DATABASE_URL_UNPOOLED.
        var = "DATABASE_URL_DIRECT" if environ.get("DATABASE_URL_DIRECT") else "DATABASE_URL_UNPOOLED"
    else:
        var = "DATABASE_URL"
    url = environ.get(var)
    if not url:
        name = "DATABASE_URL_DIRECT (or DATABASE_URL_UNPOOLED)" if direct else var
        raise ImproperlyConfigured(
            f"{name} is not set. Add your Neon connection strings to .env locally, "
            "or to the project's environment variables on Vercel (see .env.example)."
        )

    config = dj_database_url.parse(
        url,
        conn_max_age=0,
        # PgBouncer in transaction mode can't keep a cursor open across transactions.
        disable_server_side_cursors=not direct,
    )
    options = config.setdefault("OPTIONS", {})
    sslmode = options.setdefault("sslmode", "require")
    if sslmode not in SECURE_SSLMODES:
        raise ImproperlyConfigured(
            f"{var} uses sslmode={sslmode}. Neon connections must use sslmode=require or stricter."
        )
    return config

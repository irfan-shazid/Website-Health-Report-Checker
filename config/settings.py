"""Django settings for Site Health Report.

Every secret and environment-specific value comes from `.env` (see `.env.example`).
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from config.database import database_config

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 at build time and at runtime.
ON_VERCEL = bool(os.environ.get("VERCEL"))

# A local .env must never leak into a deployment (it usually has DEBUG=True),
# so on Vercel only the project's environment variables count.
if not ON_VERCEL:
    load_dotenv(BASE_DIR / ".env")

RUNNING_TESTS = "pytest" in sys.modules


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY is not set. Copy .env.example to .env and fill it in.")

DEBUG = env_bool("DEBUG", default=False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if ON_VERCEL:
    # This deployment's own URLs: the unique deployment URL, the branch URL and
    # the production domain. Other custom domains go in ALLOWED_HOSTS.
    for name in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        host = os.environ.get(name)
        if host and host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# How many reverse proxies (load balancer, CDN) sit in front of the app and
# append to X-Forwarded-For. 0 means clients connect directly; the header is
# then ignored so nobody can spoof their address to dodge rate limits.
# Vercel's edge is one hop, and it overwrites X-Forwarded-For so it can't be spoofed.
TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS") or (1 if ON_VERCEL else 0))


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "scanner",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "reports.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "reports.middleware.RateLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database: Neon. The pooled endpoint serves the app and worker; migrations and
# tests use the direct endpoint. See config/database.py.

DATABASES = {"default": database_config(sys.argv, os.environ, running_tests=RUNNING_TESTS)}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Authentication. There is no signup: the operator account comes from createsuperuser.

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = ["reports.signin.ThrottledModelBackend"]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Failed sign-ins allowed before sign-in is paused: (attempts, window in seconds).
# Applies to the sign-in page and the admin login alike.
SIGN_IN_LIMIT_PER_CLIENT = (5, 15 * 60)
SIGN_IN_LIMIT_PER_USERNAME = (10, 15 * 60)


# Request rate limits: (requests, window in seconds). Anonymous visitors are
# counted per client address, signed-in users per account. Static files are
# served before this runs and don't count.

RATE_LIMIT_ANONYMOUS = (60, 60)
RATE_LIMIT_SIGNED_IN = (600, 60)

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "default"},
    "ratelimit": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ratelimit",
        "OPTIONS": {"MAX_ENTRIES": 10_000},
    },
}


# Security. Our own pages should pass every check this app runs on other sites.

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 365 * 24 * 60 * 60
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Opt-in only: once a domain is on browsers' preload list it is hard to remove.
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=False)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # The __Host- prefix makes browsers refuse these cookies unless they are
    # Secure, host-only and scoped to "/".
    SESSION_COOKIE_NAME = "__Host-sessionid"
    CSRF_COOKIE_NAME = "__Host-csrftoken"
    if not SECURE_HSTS_PRELOAD:
        SILENCED_SYSTEM_CHECKS = ["security.W021"]

if TRUSTED_PROXY_HOPS:
    # The proxy terminates TLS and tells us the original scheme.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Internationalization

LANGUAGE_CODE = "en-us"
# Times are stored in UTC and shown in this zone, e.g. "Europe/London" or "Asia/Dhaka".
TIME_ZONE = os.environ.get("TIME_ZONE") or "UTC"
USE_I18N = True
USE_TZ = True


# Static files. On Vercel, collectstatic runs automatically during the build and
# the CDN serves the results; WhiteNoise serves them everywhere else.
# static/css/site.css is built by `python manage.py tailwind build` and committed.

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# If a fingerprinted name is ever missing from the manifest, link the plain file
# (collectstatic keeps both) instead of failing every page with a 500.
WHITENOISE_MANIFEST_STRICT = False


# Scanner

SCANNER_CONTACT_URL = os.environ.get("SCANNER_CONTACT_URL", "")
SCANNER_USER_AGENT = f"SiteHealthReport/1.0 (+{SCANNER_CONTACT_URL})"

# Lets the test suite reach a fixture server on localhost. Never read from the
# environment: tests switch it on with override_settings, and nothing else may.
SCANNER_ALLOW_PRIVATE_HOSTS = False


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django.security": {"level": "WARNING"},
        "reports": {"level": "INFO"},
        "scanner": {"level": "INFO"},
    },
}


if RUNNING_TESTS:
    # Tests don't run collectstatic: skip the manifest and serve files straight from static/.
    STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
    WHITENOISE_AUTOREFRESH = True
    WHITENOISE_USE_FINDERS = True
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # The test client speaks plain HTTP; production-mode security is covered by
    # a `check --deploy` test that runs in a subprocess.
    SECURE_SSL_REDIRECT = False

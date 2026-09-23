# Site Health Report

Enter a website address and get a plain-English health report: security headers,
certificate, cookies, broken links, mixed content, server response time, search
basics and disclosure, with an A–F grade and how to fix each problem.

The scanner is passive only: it reads public pages the way a visitor's browser does.

> Build status: phase 1 of 8 (project skeleton, sign-in, layout, security baseline).
> Scanning arrives in phases 2–5.

## Requirements

- Python 3.12
- A [Neon](https://neon.tech) Postgres project (the free tier is fine)

## Set up

```sh
python3.12 -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt    # the app plus test and build tools
```

Fill in `.env` (copy `.env.example` if you don't have one). You need at least
`SECRET_KEY`, `DATABASE_URL` (Neon's **pooled** string, host contains `-pooler`)
and `DATABASE_URL_DIRECT` (Neon's **direct** string). Both must end in
`?sslmode=require`. Every setting is explained in `.env.example`.

```sh
python manage.py migrate            # runs on Neon's direct endpoint automatically
python manage.py createsuperuser    # the operator account; there is no public sign-up
python manage.py runserver
```

Open http://127.0.0.1:8000 and sign in.

The stylesheet `static/css/site.css` is built by Tailwind and committed. After
changing templates or `assets/css/site.css`, run `python manage.py tailwind build`
(or `tailwind watch` while you work) and commit the result. A test fails if you forget.

With `DEBUG=True`, a style reference of every colour and component is at `/styleguide/`.

Neon suspends idle databases, so the first request after a quiet spell can take a few seconds.

## Tests

```sh
pytest
```

Tests use `DATABASE_URL_DIRECT` and create (then drop) a `test_<database>` database
next to yours.

## Security

- **Sign-in throttling.** 5 failed sign-ins from one client (or 10 for one username
  from anywhere) pause sign-in for 15 minutes. This also covers `/admin/`. To lift
  a pause early, delete the rows under *Login attempts* in the admin, or run:
  `python manage.py shell -c "from scanner.models import LoginAttempt; LoginAttempt.objects.all().delete()"`
- **Request rate limits.** 60 requests a minute per client when signed out, 600 per
  account when signed in. Static files don't count. The counters live in each web
  process's memory, so put your host's or CDN's rate limiting in front as well.
- **Headers.** A strict Content-Security-Policy (no inline scripts or styles, no
  eval), `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`,
  `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy` and
  `Cross-Origin-Resource-Policy` on every response. Nothing is indexed by search engines.
- **Production mode** (`DEBUG=False`): HTTPS redirect, HSTS for one year, `Secure`
  cookies with the `__Host-` prefix, 12-hour sessions.

## Deploying to Vercel

Vercel runs Django with zero configuration: it finds `manage.py`, serves the app
from `config/wsgi.py` as a Vercel Function, runs `collectstatic` and serves static
files from its CDN. This repo adds the rest:

- `pyproject.toml` lists the runtime packages (Vercel installs from it) and sets
  the build step, `python manage.py predeploy`. That runs `check --deploy` and
  **fails the deployment on any warning** (for example `DEBUG` left on or a missing
  setting), then applies migrations. A failed build never replaces the live site.
- `vercel.json` sets the function timeout and caches fingerprinted static files for a year.
- `.vercelignore` keeps `.env`, `.venv` and tests out of uploads.
- On Vercel the app ignores any `.env` file, trusts Vercel's `X-Forwarded-For` and
  `X-Forwarded-Proto` headers (Vercel overwrites them, so they can't be spoofed),
  and adds the deployment's own `*.vercel.app` URLs and production domain to
  `ALLOWED_HOSTS`.

### First deployment

1. **Database.** Create the Neon project in the same region as your Vercel
   functions, since every page makes several database round trips. Vercel runs in
   Washington, D.C. (`iad1`) unless you change it under *Settings → Functions*, so
   pick Neon's AWS US East (N. Virginia) region, or move both closer to your users
   (for example Vercel `sin1` with Neon AWS Asia Pacific (Singapore)).
2. **Import the repository** in Vercel (*Add New → Project*). The Django preset is
   detected automatically; leave the build settings empty.
3. **Environment variables** (*Settings → Environment Variables*, for Production and Preview):

   | Variable | Value |
   |---|---|
   | `SECRET_KEY` | A new random value: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `DATABASE_URL` | Neon's pooled connection string |
   | `DATABASE_URL_DIRECT` | Neon's direct connection string |
   | `SCANNER_CONTACT_URL` | A public page about this scanner |
   | `TIME_ZONE` | Optional, e.g. `Asia/Dhaka` |
   | `ALLOWED_HOSTS` | Optional: extra custom domains, e.g. `www.example.com` |

   Don't set `DEBUG`. If you connect Neon through Vercel's Marketplace integration,
   it sets `DATABASE_URL` and `DATABASE_URL_UNPOOLED` for you (the app accepts either
   name for the direct string) and gives each preview deployment its own database
   branch. In that case also set `MIGRATE_PREVIEWS=1` for the Preview environment.
   Without it, preview builds skip migrations so they can never change your
   production database.
4. **Deploy.** Every push to `main` deploys to production; other branches get preview URLs.
5. **Create the operator account** from your own machine, with the same Neon
   connection strings in your local `.env`: `python manage.py createsuperuser`.

### Good to know

- Rate limits: the sign-in pause is stored in the database, so it holds across all
  function instances. The per-visitor request limit is kept in each instance's
  memory, which makes it a first line of defence only; Vercel's built-in DDoS
  protection and its Firewall rate-limit rules sit in front of it.
- Neon suspends idle databases and Vercel starts functions on demand, so the first
  request after a quiet spell can take a few seconds.
- Change the function timeout in `vercel.json` (`maxDuration`, up to 300 seconds on
  the Hobby plan).

## Deploying elsewhere

1. Set `DEBUG=False`, `ALLOWED_HOSTS`, and a fresh `SECRET_KEY`.
2. Behind a load balancer or CDN, set `TRUSTED_PROXY_HOPS` (usually `1`) so client
   addresses and HTTPS are detected correctly. Leave it at `0` if clients connect directly.
3. `python manage.py predeploy` (checks the settings, then migrates).
4. `python manage.py collectstatic --noinput`, and serve the app with a WSGI server.

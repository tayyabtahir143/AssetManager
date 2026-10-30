# Workspace design refresh

## Run the redesigned local version

From the repository root, with `SECRET_KEY` and `DB_PASSWORD` already set in `.env`:

```sh
docker compose -p assetmanager-design -f compose.design.yml up -d --build --wait
```

Open http://127.0.0.1:5000. The application is bound to loopback only; PostgreSQL is not published to the host.

This is a **separate installation**, not an upgrade or migration of an existing database. A fresh database uses the application's existing `admin` / `admin` initial account. Change its password before using the preview for real inventory or exposing it beyond localhost.

The project uses two named volumes:

- `assetmanager-design_design-db-data`: PostgreSQL 16 data
- `assetmanager-design_design-app-data`: logs, branding and asset images

No existing bind-mounted `data` directory is mounted. Do not attach an existing PostgreSQL directory to this preview or change an existing installation's `SECRET_KEY`: it also encrypts stored integration credentials.

Normal rebuilds, restarts and `docker compose ... down` retain the named volumes. **Do not use `down -v`** if you want to keep preview data. Use the existing Backups page to export data before a deployment change.

Check or stop only this installation:

```sh
docker compose -p assetmanager-design -f compose.design.yml ps
docker compose -p assetmanager-design -f compose.design.yml logs --tail 100 web
docker compose -p assetmanager-design -f compose.design.yml stop
```

## Design and interaction changes

- Restrained slate-and-teal workspace, consistent typography, navigation, tables, forms, status badges and settings surfaces.
- Responsive dashboard with real inventory counts, category search, charts, department utilisation and recent activity. No sample inventory is inserted.
- Quick navigation: use the search control or Ctrl+K / Cmd+K. Search, move with arrow keys, Enter to open, Escape to close. Destinations come from links already rendered for the current user's permissions; it is navigation search, not a global database search.
- Compact/comfortable tables, persisted in this browser only.
- Full-width inventory uses wrapping columns on desktop and labelled record grids on narrow screens, without horizontal scrolling.
- Inventory column preferences saved separately for each built-in asset type, reset controls, keyboard sorting and recoverable incremental loading.
- Two-column asset editors on wide screens, a single column on phones, explicit save actions, and a browser warning when leaving unsaved changes. Form contents are not cached or autosaved.
- Clean sign-in and password recovery pages; existing authentication, CSRF and password rules remain in place.
- Theme preferences retained; keyboard focus, skip navigation, mobile drawer handling and reduced-motion support improved.
- Security response headers on every page (CSP scoped to local assets, nosniff, frame denial, same-origin referrer, restricted permissions) and a SameSite=Lax HttpOnly session cookie.
- Versioned static assets with Cache-Control: short-lived during development, one day in built releases.
- Update check backs off to hourly retries when the registry is unreachable instead of retrying every five minutes.
- Pull-request CI runs the full test suite, including Chromium interaction tests.

The database models, API contracts, database initialization routines, migrations and encryption logic are unchanged. Existing import/export, backups, permissions and integration forms remain in use.

## Verification

Use a virtual environment outside the Docker image:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest
```

Tests use an in-memory SQLite database, never the Compose database. Browser tests use isolated fixtures and do not write to an existing deployment. Browser-dependent tests require Playwright and Chromium; install both for the full UI checks.

The Dockerfile now uses one shared Python 3.14 base for both dependency build and runtime stages. This avoids loading Python 3.14 native extensions into an independently updated Python 3.15 runtime. The runtime still runs as UID/GID 65532.

# AssetManager

![Postgres](https://img.shields.io/badge/Database-PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Runtime-Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/App-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

A production-ready IT asset inventory management system built with Python/Flask. Track laptops, computers, peripherals, and any custom asset types across your organisation with full assignment history, LDAP/AD integration, automated email notifications, reporting, and scheduled backups.

---

## Table of Contents

1. [What's New](#whats-new)
2. [Features](#features)
3. [Quick Start](#quick-start)
4. [Environment Variables](#environment-variables)
5. [Deployment Guide](#deployment-guide)
   - [Fresh Installation (PostgreSQL)](#fresh-installation-postgresql)
   - [Lightweight Installation (SQLite)](#lightweight-installation-sqlite)
   - [Build from Source](#build-from-source)
   - [Kubernetes](#kubernetes)
6. [Upgrading an Existing Installation](#upgrading-an-existing-installation)
7. [Migration Guide (Old Server → New Server)](#migration-guide-old-server--new-server)
8. [Backup and Restore](#backup-and-restore)
9. [LDAP / Active Directory Integration](#ldap--active-directory-integration)
10. [SMTP / Email Notifications](#smtp--email-notifications)
11. [API Reference](#api-reference)
12. [Running Tests](#running-tests)
13. [Security Hardening Checklist](#security-hardening-checklist)
14. [Troubleshooting](#troubleshooting)

---

## What's New

This major release brings significant UI improvements, new features, and important fixes. If you are upgrading from a previous version, follow the [Upgrading](#upgrading-an-existing-installation) section.

### New Features

- **Generation field for Laptops** — track the hardware generation (e.g. Intel 12th Gen) on every laptop. Fully supported in Excel import and export.
- **LDAP Auto-Sync Schedule** — configure automated LDAP user/group sync on a daily, weekly, or monthly schedule directly from the UI (Settings → LDAP). Requires LDAP to be configured before the schedule can be enabled.
- **Interactive dashboard charts** — doughnut and bar charts now navigate to filtered reports on click (e.g. clicking "Assigned" takes you directly to the assigned assets report).
- **SMTP per-event recipients** — add multiple email recipients and choose exactly which events each address receives (create, update, delete, bulk delete, monthly report, low stock).
- **Forgot password / password reset** — built-in email-based password reset flow (requires SMTP configured).
- **Asset comments** — leave notes on any individual asset from its detail view.
- **Asset copy** — duplicate an existing asset with one click.
- **Audit log export** — export the full audit log to Excel.
- **Bulk delete for users and groups** — select multiple users or groups and delete them in one action.
- **Edit available assets inline** — edit button per item in the Available Assets section.
- **Branding** — set a custom company name and logo (shown on the login screen and throughout the app).
- **Departments** — manage departments from Settings → Departments.

### UI / UX Improvements

- **SMTP settings redesign** — clean two-column layout with toggle switches for enable/disable, skip-auth, assignment emails, monthly reports, and low-stock alerts.
- **Audit log diff view** — changes are shown as a structured before/after diff (field name, old value → new value) instead of raw text.
- **Inline page-header buttons** — search box and action buttons are always on one line on the Users, Groups, and all asset list pages.
- **Autocomplete dropdown** — user search autocomplete is rendered at the document root level so it always appears above all other elements regardless of page structure.
- **Mobile responsive** — the entire app adapts to small screens; tables scroll horizontally and the layout stacks cleanly on phones and tablets.
- **Login page** — added GitHub repository link and app version at the bottom of the login form.
- **Print report** — fixed a bug where the printed report was completely blank; all data now renders correctly on paper.

### Fixes

- Docker health check now works correctly with the distroless Chainguard container image (uses `CMD` instead of `CMD-SHELL` — distroless has no `/bin/sh`).
- LDAP sync schedule cannot be saved or enabled until LDAP server and Base DN are configured; the UI shows a clear error if you try.
- Report print was fully blank — the animation class was incorrectly hiding all data cards in print media; fixed.
- User autocomplete second result and beyond were hidden behind other page elements — fixed with body-level dropdown positioning.

---

## Features

- **Asset tracking** — 7 built-in types (Laptops, Computers, Screens, Keyboards, Mice, Headsets, RAM) plus unlimited custom asset types
- **Laptop Generation field** — track hardware generation; included in Excel import/export and reports
- **Assignment history** — full audit trail of who had what and when
- **LDAP / Active Directory** — user sync, group-based roles, auto-provisioning on login, scheduled auto-sync
- **Role-based access control** — granular per-asset-type permissions
- **Email notifications** — SMTP with TLS/SSL, per-event per-recipient subscriptions, monthly reports, low-stock alerts
- **Excel import/export** — bulk import with header validation; export any view
- **Scheduled backups** — config-only or full database, delivered via email
- **LDAP auto-sync schedule** — automatic user/group sync on a configurable daily/weekly/monthly schedule
- **Audit log** — every create/update/delete action recorded with user, IP, and structured diff view
- **Audit log export** — export audit log to Excel
- **Asset comments** — per-asset notes visible in the detail view
- **Asset copy** — duplicate an existing asset
- **REST API** — JWT-authenticated, versioned (`/api/v1/`)
- **CSRF protection** — all web forms protected with CSRF tokens
- **Rate limiting** — brute-force protection on login (20 req/min per IP)
- **Credential encryption** — LDAP bind password and SMTP password encrypted at rest using Fernet symmetric encryption
- **Branding** — custom company name and logo
- **Departments** — manageable from Settings
- **Forgot password** — email-based password reset (requires SMTP)
- **Structured JSON logging** — machine-parseable logs for easy aggregation
- **Mobile responsive** — works on phones and tablets
- **Kubernetes-ready** — manifests included

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/tayyabtahir143/AssetManager.git
cd AssetManager

# 2. Generate strong random secrets (creates .env automatically)
./generate_secrets.sh

# 3. (Optional) Edit .env to set timezone, etc.
nano .env

# 4. Start
docker compose up -d

# 5. Open in browser
open http://localhost:5000
```

**Default credentials: `admin` / `admin` — change immediately after first login.**

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | 64-char hex string. Used for session signing AND credential encryption. Run `./generate_secrets.sh` to generate. |
| `DB_PASSWORD` | **Yes** (PostgreSQL) | — | PostgreSQL database password |
| `DATABASE_URL` | No | `sqlite:////data/inventory.db` | Full database connection string |
| `TZ` | No | `UTC` | Server timezone (e.g. `Australia/Brisbane`, `America/New_York`) |
| `MAX_UPLOAD_MB` | No | `16` | Maximum file upload size in megabytes |
| `DB_POOL_SIZE` | No | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | No | `20` | SQLAlchemy max overflow connections |
| `LOG_DIR` | No | `/data/logs` | Directory for application log files |
| `LOG_FILE` | No | `app.log` | Log filename (JSON structured format) |
| `APP_VERSION` | No | `1.0.0` | Application version tag (shown on login page) |

> **Security:** Never commit `.env` to version control. Add it to `.gitignore`.

---

## Deployment Guide

### Prerequisites

- Docker >= 24 and Docker Compose >= 2.20
- At least 512 MB RAM, 2 GB disk space

### Fresh Installation (PostgreSQL)

PostgreSQL is recommended for production — it supports concurrent connections, proper indexing, and reliable backups.

```bash
# 1. Clone
git clone https://github.com/tayyabtahir143/AssetManager.git
cd AssetManager

# 2. Generate secrets (creates .env automatically)
./generate_secrets.sh

# 3. Edit timezone and any other settings
nano .env

# 4. Create data directory and start
mkdir -p data
docker compose up -d

# 5. Check health
docker compose ps
docker compose logs web --tail=50
```

The database schema is initialised automatically on first start. No manual setup needed.

### Lightweight Installation (SQLite)

For small teams or testing (no PostgreSQL required):

```bash
./generate_secrets.sh
docker compose -f docker-compose-sqlite.yml up -d
```

> SQLite does not support multiple concurrent writers. Use PostgreSQL for production.

### Build from Source

```bash
# Build the image locally
docker compose -f docker-compose-build.yml build

# Run the locally-built image
docker compose -f docker-compose-build.yml up -d
```

### Kubernetes

```bash
kubectl apply -f kubernetes/
```

Edit `kubernetes/deployment.yaml` to set `SECRET_KEY` and database credentials as Kubernetes Secrets before applying.

---

## Upgrading an Existing Installation

### Minor / Patch Upgrade

No manual steps required. Schema changes are applied automatically on startup.

```bash
# Pull the latest image
docker compose pull

# Restart with the new image
docker compose up -d

# Verify
docker compose logs web --tail=20
docker compose ps
```

### Major Version Upgrade

A full database backup before any major upgrade is strongly recommended.

```bash
# 1. Back up the database first (PostgreSQL)
docker compose exec db pg_dump -U inventory inventory -F c > backup_$(date +%Y%m%d_%H%M%S).dump

# 2. Pull and restart
docker compose pull
docker compose up -d

# 3. Watch startup logs for migration messages
docker compose logs web -f
```

#### Schema migrations applied automatically on upgrade

| Migration | What it does |
|---|---|
| `ensure_laptop_generation_column` | Adds the `generation` column to the `laptop` table if missing |
| `migrate_plaintext_credentials` | Re-encrypts any plaintext LDAP/SMTP passwords stored by older versions |
| `init_db` | Creates any missing tables for new models |

No manual SQL is needed — all of the above run on first startup after upgrade.

---

## Migration Guide (Old Server → New Server)

Use this procedure when moving an existing installation to a new server, or performing a clean upgrade.

### Overview

```
Old Server                          New Server
──────────                          ──────────
1. Take full backup  ──────────►   2. Deploy new version
                                   3. Restore backup
                                   4. Auto-migration on first start
                                   5. Verify → cut over
```

---

### Step 1 — Back Up on the Old Server

#### Option A — In-app (easiest)

Log in as admin → **Settings → Backup → Full Backup** → download the ZIP.

#### Option B — PostgreSQL command line

```bash
# Create a binary dump
docker compose exec db pg_dump -U inventory inventory -F c -f /tmp/backup.dump

# Copy it out of the container
docker compose cp db:/tmp/backup.dump ./backup_$(date +%Y%m%d_%H%M%S).dump
```

Keep this file safe. You can restore it if anything goes wrong.

---

### Step 2 — Deploy the New Version on the New Server

```bash
# Clone the repository on the new server
git clone https://github.com/tayyabtahir143/AssetManager.git
cd AssetManager

# Generate a new SECRET_KEY and DB_PASSWORD
./generate_secrets.sh

# Optional: copy the old SECRET_KEY if you want to skip credential re-encryption
# (see note below)
nano .env

# Create data directory and start
mkdir -p data
docker compose up -d
```

Wait until the container is healthy:

```bash
docker compose ps   # web should show "healthy"
```

> **Note on SECRET_KEY:**
> - **New `SECRET_KEY` (default):** The app automatically re-encrypts LDAP/SMTP passwords with the new key on first start. No manual steps needed.
> - **Same `SECRET_KEY` as old server:** Credentials remain encrypted with the existing key — no re-encryption occurs. Useful when testing before cutting over.

---

### Step 3 — Restore the Backup

#### Option A — In-app restore

1. Log in to the new server as `admin` (default password `admin`)
2. Go to **Settings → Backup → Restore Backup**
3. Upload the ZIP from Step 1
4. Confirm the restore

The app validates the ZIP, clears data inside a transaction, imports all tables, and rolls back automatically on failure.

#### Option B — PostgreSQL command line

```bash
# Copy the dump to the new server
scp backup_20240101.dump user@new-server:~/

# On the new server — restore into the running database
cat backup_20240101.dump | docker compose exec -T db pg_restore -U inventory -d inventory --clean

# Restart the app so init_db and migrations run
docker compose restart web
```

---

### Step 4 — Automatic Migrations on First Start

When the app starts after restore, it runs these migrations automatically:

#### `migrate_plaintext_credentials`

1. Reads the LDAP bind password and SMTP password from the database
2. If either is stored as plaintext (from an older version without encryption), it re-encrypts them using the current `SECRET_KEY`-derived Fernet key
3. Commits and logs: `"migrate_plaintext_credentials: encrypted existing plaintext credentials"`

#### `ensure_laptop_generation_column`

1. Checks whether the `generation` column exists on the `laptop` table
2. If missing (upgrading from a version before this column was added), it runs `ALTER TABLE laptop ADD COLUMN generation VARCHAR(50)`
3. Logs: `"Added generation column to laptop table"`

#### Session invalidation

All active sessions are invalidated when `SECRET_KEY` changes. This is expected — users simply log in again.

Watch migrations complete:

```bash
docker compose logs web | grep -E "migrate|generation|credential|encrypt|init_db"
```

---

### Step 5 — Verify

```bash
# Confirm the app is responding
curl -s http://new-server:5000/login | grep "Sign in"

# Check for errors in logs
docker compose logs web --tail=50
```

Then verify in the browser:

- Log in as admin with the original admin password
- Check that assets, users, and roles are present and correct
- Go to **Settings → LDAP → Test Connection** to confirm LDAP still works
- Go to **Settings → SMTP** — re-enter the SMTP password if it wasn't captured in the backup
- Send a test backup email
- If Laptop assets exist, confirm the Generation column is visible on the laptop list and edit pages

---

### Step 6 — Cut Over

Update DNS or your load balancer to point to the new server. Decommission the old one.

---

## Backup and Restore

### Backup Types

| Type | Contents | Best For |
|---|---|---|
| **Config Backup** | Roles, LDAP/SMTP settings, branding, departments | Quick config snapshot |
| **Full Backup** | Entire database as ZIP | Before upgrades, server migrations, disaster recovery |

### Scheduled Backups

**Settings → Backup → Add Schedule:**

- Frequency: Daily, Weekly, Monthly
- Time: HH:MM in server timezone
- Day of week (weekly) or day of month (monthly)
- Delivery: Email (requires SMTP configured)

### Manual Restore

1. **Settings → Backup → Restore Backup**
2. Upload the ZIP file
3. The app validates the structure and rolls back on failure

### Command-line Backup (PostgreSQL)

```bash
# Backup
docker compose exec db pg_dump -U inventory inventory -F c > backup.dump

# Restore (replaces all data)
docker compose exec -T db pg_restore -U inventory -d inventory --clean < backup.dump
docker compose restart web
```

---

## LDAP / Active Directory Integration

### Basic Setup

1. **Settings → LDAP**
2. Fill in your server details:

   | Field | Example |
   |---|---|
   | LDAP Server | `ldap://dc.example.com` or `ldaps://dc.example.com` |
   | Base DN | `DC=example,DC=com` |
   | Bind DN | `CN=svc-assetmgr,OU=Service Accounts,DC=example,DC=com` |
   | Bind Password | stored encrypted at rest |
   | User Filter | `(sAMAccountName={username})` |
   | User List Filter | `(&(objectClass=user)(!(objectClass=computer))(sAMAccountName=*))` |
   | User Attribute | `sAMAccountName` |
   | Email Attribute | `mail` (or `userPrincipalName` for UPN-style addresses) |

3. Click **Test Connection** before saving
4. Set a **Default Role** for new LDAP users (e.g. `reader`)

Users can log in with their AD credentials immediately — accounts are auto-provisioned on first login.

### Group-Based Roles

**Settings → Groups → Import from LDAP** → assign a role to each imported group.

Members of those groups automatically inherit the group's role at login.

### LDAP Auto-Sync Schedule

Automatically import new LDAP users and update existing ones on a schedule, without manual intervention.

1. Configure and save your LDAP settings first (server + Base DN are required)
2. Go to **Settings → LDAP → Auto-Sync Schedule**
3. Enable the schedule and choose:
   - **Frequency:** Daily, Weekly, or Monthly
   - **Time:** HH:MM in 24-hour format (server timezone)
   - **Day of week** (weekly) or **day of month** (monthly)
4. Save — the background scheduler picks it up immediately

> The schedule cannot be enabled until LDAP is configured. A red warning banner is shown if you try.

### Manual Sync

**Settings → LDAP → Sync LDAP** — imports users immediately on demand.

---

## SMTP / Email Notifications

### Setup

1. **Settings → SMTP**
2. Enable email notifications with the toggle switch
3. Configure the connection:
   - **SMTP Server** and **Port** (common: 587 for STARTTLS, 465 for SSL, 25 for relay)
   - **Encryption:** None / SSL / STARTTLS
   - **Sender Email**
   - For relay servers with no login required, enable **Skip authentication**
4. Save settings

### Notifications

| Toggle | What it sends |
|---|---|
| Asset assignment email | Sends an email to the user when an asset is assigned to them |
| Monthly report | Full inventory report on a set day of the month |
| Low stock alerts | Alert when any asset type's In Stock count falls below a threshold |

### Per-Event Recipients

Add one or more email addresses under **Recipients** and choose which events each address receives:

- Create / Update / Delete / Bulk Delete
- Monthly Report
- Low Stock Alert

### Manual Triggers

Use the **Send monthly report now** and **Send low stock report now** buttons to test delivery without waiting for the schedule.

### Low Stock Alerts

Set **Low Stock Threshold** and **Frequency (days)** — an alert is sent when any asset type's In Stock count falls below the threshold, at most once per the configured interval.

---

## API Reference

Both `/api/` (legacy) and `/api/v1/` (current) paths work. Existing integrations using `/api/` continue to work unchanged.

### Authentication

```bash
# Get tokens
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 900
}

# Use the access token (valid 15 minutes)
curl http://localhost:5000/api/v1/assets/laptops \
  -H "Authorization: Bearer <access_token>"

# Refresh before expiry (refresh token valid 14 days)
curl -X POST http://localhost:5000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

### Asset Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/assets/{type}` | List assets (paginated, filterable) |
| `GET` | `/api/v1/assets/{type}/{id}` | Get single asset |
| `POST` | `/api/v1/assets/{type}` | Create asset |
| `PUT` | `/api/v1/assets/{type}/{id}` | Update asset |
| `DELETE` | `/api/v1/assets/{type}/{id}` | Delete asset |

**Supported `{type}` values:** `laptops`, `computers`, `screens`, `keyboards`, `mice`, `headsets`, `ram`, plus any custom asset type key.

**Query Parameters (List):**

| Parameter | Description | Default |
|---|---|---|
| `q` | Search query | — |
| `status` | Filter: `In Stock`, `Assigned`, `Broken`, `Write Off`, `all` | `all` |
| `page` | Page number | `1` |
| `per_page` | Items per page (max 200) | `25` |

### Reference Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/asset-types` | All asset type keys and labels |
| `GET` | `/api/v1/users` | All users (local + LDAP) |
| `GET` | `/api/v1/departments` | All departments |

### Rate Limiting

Login endpoints: **20 requests/minute per IP**. Returns HTTP `429` when exceeded.

---

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests (uses in-memory SQLite — no services required)
pytest

# With coverage report
pip install pytest-cov
pytest --cov=app --cov-report=term-missing

# Specific test file
pytest tests/test_auth.py -v

# Specific test
pytest tests/test_assets.py::TestApiAssets::test_create_laptop_via_api -v
```

Tests are fully isolated — each test session spins up a fresh in-memory database.

---

## Security Hardening Checklist

Before going to production:

- [ ] **Change default admin password** — Settings → Users → admin → Edit
- [ ] **Set a strong `SECRET_KEY`** — run `./generate_secrets.sh` (auto-generates 64-char hex)
- [ ] **Use a strong `DB_PASSWORD`** — auto-generated by `generate_secrets.sh`
- [ ] **Enable HTTPS** — place nginx/Caddy/Traefik in front with a valid TLS certificate
- [ ] **Restrict port access** — bind app to `127.0.0.1:5000` if behind a reverse proxy
- [ ] **Set correct `TZ`** — ensures accurate audit log timestamps
- [ ] **Configure SMTP** — receive backup emails and low-stock alerts
- [ ] **Schedule regular backups** — Settings → Backup → enable a daily scheduled backup
- [ ] **Review LDAP role assignments** — be conservative with `app_admin`
- [ ] **Keep images updated** — `docker compose pull && docker compose up -d`

### nginx HTTPS Example

```nginx
server {
    listen 443 ssl http2;
    server_name assets.example.com;
    ssl_certificate     /etc/ssl/certs/assets.crt;
    ssl_certificate_key /etc/ssl/private/assets.key;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        client_max_body_size 32m;
    }
}
server {
    listen 80;
    server_name assets.example.com;
    return 301 https://$host$request_uri;
}
```

---

## Troubleshooting

### App won't start

```bash
docker compose logs web --tail=100
```

Common causes:
- Missing `SECRET_KEY` → run `./generate_secrets.sh`
- Database not ready → check `docker compose logs db`
- Port 5000 in use → change the port mapping in `docker-compose.yml`

### Container shows "unhealthy"

The health check runs `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/login')"`. It may show "starting" for up to 15 seconds on first boot. If it stays unhealthy:

```bash
docker compose logs web --tail=50
```

If you built from source using the distroless Chainguard image, make sure your health check uses `CMD` (not `CMD-SHELL`) — distroless containers have no shell.

### Laptop Generation column missing after upgrade

Run:
```bash
docker compose restart web
```

On startup the app detects the missing column and runs `ALTER TABLE laptop ADD COLUMN generation VARCHAR(50)` automatically. Check the log:

```bash
docker compose logs web | grep generation
```

### LDAP schedule cannot be saved

The schedule requires LDAP to be configured first. Go to **Settings → LDAP**, fill in at minimum the **LDAP Server** and **Base DN** fields, and save. The Auto-Sync Schedule form will then be enabled.

### LDAP login fails

1. **Settings → LDAP → Test Connection**
2. Check bind DN format (`CN=user,OU=Users,DC=example,DC=com`)
3. Use `ldap://` for port 389, `ldaps://` for 636
4. Check firewall rules on the LDAP server

### SMTP not sending

1. **Settings → SMTP** — verify host, port, and encryption
2. If you changed `SECRET_KEY` after restore, re-enter the SMTP password manually (the auto-migration encrypts it with the new key, but if the password was not in the backup it will be blank)
3. Check firewall (ports 25, 465, 587)
4. Use **Send monthly report now** to test immediately

### Print report is blank

Ensure you are on the latest version. An earlier bug caused all report cards to be hidden in print mode. After upgrading, hard-refresh the browser (`Ctrl+Shift+R`) and print again.

### Backup restore fails

- Ensure the ZIP came from a compatible AssetManager version
- Check disk space: `df -h`
- Check logs: `docker compose logs web | grep -i restore`

### Sessions invalidated after upgrade

Expected when `SECRET_KEY` changes. All users log in again. This is intentional security behaviour.

### Database locked errors (SQLite)

SQLite only supports one concurrent writer. Switch to PostgreSQL for multi-user deployments.

### How do I read the JSON logs?

```bash
# Pretty-print
docker compose logs web | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('{'):
        print(json.dumps(json.loads(line), indent=2))
"

# Filter errors only
docker compose logs web | grep '"level": "ERROR"'
```

---

## Default Credentials

| Username | Password | Role |
|---|---|---|
| `admin` | `admin` | App Administrator |

**Change the admin password immediately after first login.**

---

## License

MIT — see `LICENSE` for details.

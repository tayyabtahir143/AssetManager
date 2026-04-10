# AssetManager

![Postgres](https://img.shields.io/badge/Database-PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Runtime-Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/App-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

A production-ready IT asset inventory management system built with Python/Flask. Track laptops, computers, peripherals, and any custom asset types across your organisation with full assignment history, LDAP/AD integration, reporting, and automated backups.

---

## Table of Contents

1. [Features](#features)
2. [Quick Start](#quick-start)
3. [Environment Variables](#environment-variables)
4. [Deployment Guide](#deployment-guide)
   - [Fresh Installation (PostgreSQL)](#fresh-installation-postgresql)
   - [Lightweight Installation (SQLite)](#lightweight-installation-sqlite)
   - [Build from Source](#build-from-source)
   - [Kubernetes](#kubernetes)
5. [Upgrading an Existing Installation](#upgrading-an-existing-installation)
6. [Client Migration Guide (Backup → Deploy → Restore)](#client-migration-guide)
7. [Backup and Restore](#backup-and-restore)
8. [LDAP / Active Directory Integration](#ldap--active-directory-integration)
9. [SMTP / Email Notifications](#smtp--email-notifications)
10. [API Reference](#api-reference)
11. [Running Tests](#running-tests)
12. [Security Hardening Checklist](#security-hardening-checklist)
13. [Troubleshooting](#troubleshooting)

---

## Features

- **Asset tracking** — 7 built-in types (Laptops, Computers, Screens, Keyboards, Mice, Headsets, RAM) plus unlimited custom asset types
- **Assignment history** — full audit trail of who had what and when
- **LDAP / Active Directory** — user sync, group-based roles, auto-provisioning on login
- **Role-based access control** — granular per-asset-type permissions
- **Email notifications** — SMTP with TLS/SSL, per-event recipients, monthly reports, low-stock alerts
- **Excel import/export** — bulk import with header validation; export any view
- **Scheduled backups** — config-only or full database, delivered via email
- **Audit log** — every create/update/delete action recorded with user and IP
- **REST API** — JWT-authenticated, versioned (`/api/v1/`)
- **CSRF protection** — all web forms protected with CSRF tokens
- **Rate limiting** — brute-force protection on login (20 req/min per IP)
- **Credential encryption** — LDAP bind password and SMTP password encrypted at rest using Fernet symmetric encryption
- **Structured JSON logging** — machine-parseable logs for easy aggregation
- **Kubernetes-ready** — manifests included

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/tayyabtahir/AssetManager.git
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
| `TZ` | No | `UTC` | Server timezone (e.g. `Australia/Brisbane`) |
| `MAX_UPLOAD_MB` | No | `16` | Maximum file upload size in megabytes |
| `DB_POOL_SIZE` | No | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | No | `20` | SQLAlchemy max overflow connections |
| `LOG_DIR` | No | `/data/logs` | Directory for application log files |
| `LOG_FILE` | No | `app.log` | Log filename (JSON structured format) |
| `APP_VERSION` | No | `1.0.0` | Application version tag |

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
git clone https://github.com/tayyabtahir/AssetManager.git
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

### Standard Upgrade (minor/patch releases)

```bash
# Pull new image
docker compose pull

# Restart with new image
docker compose up -d

# Verify
docker compose logs web --tail=20
```

Schema changes are applied automatically on startup. No manual migration steps.

### Major Version Upgrade

```bash
# 1. Always back up first
docker compose exec db pg_dump -U inventory inventory > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Pull and restart
docker compose pull
docker compose up -d

# 3. Watch for migration log messages
docker compose logs web -f
```

---

## Client Migration Guide

Use this procedure when moving a client's existing installation to a new server, or applying a major upgrade where you want a clean slate.

### The Strategy

```
Old Server                         New Server
──────────                         ──────────
1. Take full backup  ──────────►  2. Deploy new version
                                  3. Restore backup
                                  4. Auto-migration runs on first request
                                  5. Verify → hand over
```

**Why this works safely:**
- All web form data, assets, users, roles, and settings are in the database
- The backup ZIP captures the entire database
- The new version's first-boot migration automatically re-encrypts any plaintext credentials with the new `SECRET_KEY`
- No data is lost; all clients just need to log in again

---

### Step 1 — Take a Full Backup (on old server)

**In-app:** Log in as admin → **Settings → Backup → Full Backup** → download the ZIP.

**Command line (PostgreSQL):**
```bash
docker compose exec db pg_dump -U inventory inventory -F c -f /tmp/backup.dump
docker compose cp db:/tmp/backup.dump ./backup_$(date +%Y%m%d_%H%M%S).dump
```

Keep this backup safe. You can restore it if anything goes wrong.

---

### Step 2 — Deploy New Version on New Server

```bash
# On the new server:
git clone https://github.com/tayyabtahir/AssetManager.git
cd AssetManager

./generate_secrets.sh    # Generates a new SECRET_KEY and DB_PASSWORD

# Optional: copy the old SECRET_KEY if you want to skip credential re-encryption
# (see note below)
nano .env

mkdir -p data
docker compose up -d
```

Wait until the app is healthy:
```bash
docker compose ps   # web should show "healthy"
```

> **Note on SECRET_KEY:**
> - If you use a **new** `SECRET_KEY` (default): The auto-migration re-encrypts LDAP/SMTP passwords using the new key. You don't need to do anything.
> - If you copy the **old** `SECRET_KEY`: Credentials stay encrypted with the same key — no re-encryption needed. Useful if you want to test before cutting over.

---

### Step 3 — Restore the Backup

**Option A — In-app restore (easiest):**

1. Log in to the new server as `admin` (default password)
2. Go to **Settings → Backup → Restore Backup**
3. Upload the ZIP from Step 1
4. Confirm the restore

The app validates the ZIP, clears existing data inside a transaction, imports all tables, and rolls back automatically if anything fails.

**Option B — PostgreSQL command line:**
```bash
# Copy backup file to new server
scp backup_20240101.dump user@new-server:~/

# Restore
cat backup_20240101.dump | docker compose exec -T db pg_restore -U inventory -d inventory --clean
docker compose restart web   # Re-run init_db migration
```

---

### Step 4 — Automatic Migration on First Request

When the app serves its first request after restore, it runs `migrate_plaintext_credentials()` which:

1. Checks if LDAP bind password in DB is plaintext (from old version without encryption)
2. If plaintext — encrypts it with the current `SECRET_KEY`-derived Fernet key
3. Same for SMTP password
4. Commits the change and logs: `"migrate_plaintext_credentials: encrypted existing plaintext credentials"`

**All users will be logged out** because sessions signed with the old `SECRET_KEY` are invalid. This is expected and safe — they just log in again.

Watch the migration:
```bash
docker compose logs web | grep -E "migrate|credential|encrypt|init_db"
```

---

### Step 5 — Verify

```bash
# Check app health
curl -s http://new-server:5000/login | grep "Sign in"

# Check logs for errors
docker compose logs web --tail=50
```

Then verify in the browser:
- Log in as admin with the original admin password
- Check a few assets are present and correct
- Go to **Settings → LDAP → Test Connection** — verify LDAP works
- Go to **Settings → SMTP** — re-enter SMTP password if it wasn't in the backup (it should be)
- Send a test backup email

---

### Step 6 — Cut Over

Update DNS or your load balancer to point to the new server. Decommission the old one.

---

## Backup and Restore

### Backup Types

| Type | Contents | Best For |
|---|---|---|
| **Config Backup** | Roles, LDAP/SMTP settings, branding | Quick config snapshot, routine |
| **Full Backup** | Entire database as ZIP | Before upgrades, server migrations, DR |

### Scheduled Backups

**Settings → Backup → Add Schedule:**
- Frequency: Daily, Weekly, Monthly
- Time: HH:MM in server timezone
- Delivery: Email (requires SMTP configured)

### Manual Restore

1. **Settings → Backup → Restore Backup**
2. Upload the ZIP file
3. The app validates structure and rolls back on failure

### Command-line Backup (PostgreSQL)

```bash
# Backup
docker compose exec db pg_dump -U inventory inventory -F c > backup.dump

# Restore (will replace all data)
docker compose exec -T db pg_restore -U inventory -d inventory --clean < backup.dump
docker compose restart web
```

---

## LDAP / Active Directory Integration

1. **Settings → LDAP**
2. Fill in your LDAP server details:
   - **Server:** `ldap://dc.example.com` or `ldaps://dc.example.com`
   - **Base DN:** `DC=example,DC=com`
   - **Bind DN:** `CN=svc-assetmgr,OU=Service Accounts,DC=example,DC=com`
   - **Bind Password:** stored encrypted at rest (Fernet)
3. Click **Test Connection** before saving
4. Set a **Default Role** for new LDAP users
5. Recommended **User List Filter** for AD: `(&(objectClass=user)(!(objectClass=computer))(sAMAccountName=*))`

Users can log in immediately with their AD credentials — accounts are auto-provisioned on first login.

### Group-Based Roles

**Settings → Groups → Import from LDAP** → assign a role to each group.

Members of those groups automatically inherit the role at login.

---

## SMTP / Email Notifications

1. **Settings → SMTP**
2. Configure host, port, encryption (None / StartTLS / SSL)
3. Username and password (stored encrypted at rest)
4. Add recipients with per-event subscriptions:
   - Create / Update / Delete / Bulk Delete
   - Monthly Report
   - Low Stock Alert

### Low Stock Alerts

Set **Low Stock Threshold** — an alert is sent when any asset type's "In Stock" count falls below the threshold.

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

# Use access token (valid 15 minutes)
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
- [ ] **Set a strong `SECRET_KEY`** — run `./generate_secrets.sh` (auto-generates)
- [ ] **Use a strong `DB_PASSWORD`** — auto-generated by `generate_secrets.sh`
- [ ] **Enable HTTPS** — place nginx/Caddy/Traefik in front with a valid TLS certificate
- [ ] **Restrict port access** — bind app to `127.0.0.1:5000` if behind a reverse proxy
- [ ] **Set correct `TZ`** — correct timezone ensures accurate audit log timestamps
- [ ] **Configure SMTP** — receive backup emails and security alerts
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

### LDAP login fails

1. **Settings → LDAP → Test Connection**
2. Check bind DN format (e.g. `CN=user,OU=Users,DC=example,DC=com`)
3. Use `ldap://` for port 389, `ldaps://` for 636
4. Check firewall rules on the LDAP server

### SMTP not sending

1. **Settings → SMTP** — verify host, port, encryption
2. If you changed `SECRET_KEY` on the new server, re-enter the SMTP password (it was encrypted with the old key, then auto-migrated — but if migration didn't run, re-enter manually)
3. Check firewall (ports 25, 465, 587)

### Backup restore fails

- Ensure the ZIP came from a compatible AssetManager version
- Check disk space: `df -h`
- Check logs: `docker compose logs web | grep -i restore`

### Sessions invalidated after upgrade

Expected when `SECRET_KEY` changes. All users log in again. This is intentional security behaviour.

### Database locked errors (SQLite)

SQLite only supports one concurrent writer. Switch to PostgreSQL for multi-user deployments.

### Logs are in JSON format — how do I read them?

```bash
# Pretty print
docker compose logs web | python3 -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin if l.strip().startswith('{')]"

# Filter by level
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

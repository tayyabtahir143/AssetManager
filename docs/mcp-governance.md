# MCP Governance — Design & Build Plan

Status: plan approved by the user; implementation follows phase by phase.

## Goals

1. **Audit** — every MCP action is logged: who (user + token), which tool,
   what arguments, when, result, duration, client IP. Auth failures logged too.
2. **Self-service** — any user can request MCP access from Settings → MCP.
3. **Admin approval** — requests appear in the admin panel; approve/decline
   with scope + expiry decisions.
4. **Email** — admins notified of new requests; users emailed on
   approve/decline/revoke/rotate, with the token and add-to-LLM commands.
5. **Least privilege** — MCP access is ALWAYS the user's actual in-app
   permissions (token resolves to the owner user; role checks run per call).
   Scope is a cap on top: `read_only` blocks writes; `full` allows whatever
   the user's roles allow.
6. **Admin proactive grant** — admin grants access to any user; user gets the
   setup email.

## Data model

New tables (created by `create_all` — no destructive changes):

- `McpAccessRequest` — self-service requests:
  id, user_id, scope, expiry_days, reason, status (pending/approved/declined),
  created_at, decided_by, decided_at, admin_note.
- `McpAccess` — the user's MCP access (one active row per user):
  id, user_id, scope (read_only/full), expires_at (nullable), status
  (active/revoked), granted_by, granted_at, revoked_by, revoked_at.
- `McpUsageLog` — per-tool-call audit:
  id, user_id, username (snapshot), token_id (nullable), tool_name,
  success, error (nullable), arguments (truncated 500), duration_ms,
  ip_address, created_at.

Existing table change (guarded migration, `ensure_mcp_token_access_column`):
- `mcp_token.access_id` — nullable FK to `McpAccess`. Legacy rows (access_id
  NULL) keep working with their own scope/expiry.

## Flows

- **Request (user):** Settings → MCP → "Request access" (scope + expiry +
  reason) → row pending → email to all app-admins → audit entry. Duplicate
  pending request for a user is rejected.
- **Approve (admin):** pick scope + expiry (pre-filled from request) →
  create/update `McpAccess` active + generate token (hashed at rest, shown
  once in panel + emailed) → email user with token + add-to-LLM commands →
  audit entry. Approving replaces any previous token for that user.
- **Decline (admin):** reason recorded, email user, audit entry.
- **Grant (admin, no request):** username + scope + expiry → same as approve.
- **Revoke (admin or self?):** admin revokes → all tokens for the access
  disabled, status revoked, email user, audit. Users can rotate their own
  token (revoke old, issue new, email self) but cannot revoke their access.
- **Expiry:** existing auto-revoke on use stays; expiry set per access.
- **Usage audit:** embedded gateway logs every tool call + auth failures via
  a logger hook registered by the app (runs in the gateway thread with an
  app context); client IP from the MCP request context.

## Permission inheritance (unchanged core)

`_resolve_mcp_token` maps token → owner user → per-request role/permission
checks in the API layer. Scope `read_only` returns 403 for non-GET. This is
already how the gateway behaves; the new work formalises it and makes the
grant lifecycle visible.

## Emails

Reuse `send_email` + SMTP settings. When SMTP is disabled, actions still
succeed and the UI notes "email not sent — SMTP not configured".
Templates: request notice (admins), approved (token + commands), declined,
revoked, rotated. App-admin recipients = users with `role.is_app_admin`.

## UI (Settings → MCP)

- Sidebar link visible to ALL signed-in users (moved out of the app-admin
  block).
- **User view:** access status card (none/pending/active/revoked/declined),
  request form (scope, expiry, reason), self-rotate button when active,
  add-to-LLM commands when active.
- **Admin view:** gateway toggle + endpoint; pending requests table with
  approve/decline; accesses table (user, scope, expiry, last used, status)
  with grant form, rotate, revoke; usage log table (paginated) + quick
  stats; add-to-LLM commands.

The previous standalone "create token for the admin user" form is replaced
by the access model (unreleased feature — clean break).

## Routes

- GET  /settings/mcp                     role-aware page
- POST /settings/mcp/request             self-service request
- POST /settings/mcp/requests/<id>/approve
- POST /settings/mcp/requests/<id>/decline
- POST /settings/mcp/accesses            admin grant
- POST /settings/mcp/accesses/<id>/revoke
- POST /settings/mcp/accesses/<id>/rotate
- POST /settings/mcp/self/rotate         user rotates own token
- POST /settings/mcp/toggle              (existing)

## Testing plan

1. Request lifecycle: request → pending → approve (token + email + access
   active) → usage works; decline; duplicate pending rejected; approval
   replaces old token.
2. Least privilege: reader user with `full` token still 403 on writes (role);
   admin with `read_only` token 403 on writes (cap).
3. Emails: mocked `send_email` assertions for all five templates; SMTP-off
   path skips gracefully.
4. Usage audit: gateway tool call writes `McpUsageLog` (tool/user/success/IP);
   failed auth attempts logged.
5. Page tests: user vs admin views; approve/decline/grant/rotate/revoke
   flows; usage table.
6. Regression: full suite + embedded-gateway protocol tests stay green.
7. Live: rebuild preview, enable gateway, walk the user flow end-to-end.

## Phases

- Phase 1: models + migrations + token↔access linkage in auth layer.
- Phase 2: request/grant/approve/decline/revoke/rotate routes + audit entries.
- Phase 3: emails (5 templates) + SMTP-off handling.
- Phase 4: usage logging (gateway hook + table + admin UI).
- Phase 5: role-aware settings page + sidebar link.
- Phase 6: test suite completion, full-suite green, README, live verification.

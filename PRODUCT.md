# Product

<!-- impeccable:product-schema 1 -->

> Inferred record: this subagent has no interview channel. Every fact below is
> inferred from the delegating brief and repository evidence (app.py, templates/,
> tests/), and marked [INFERRED] where not directly verifiable in code. Nothing
> here was confirmed with a human.

## Platform

web

## Stack

Existing codebase: Python Flask + SQLAlchemy server, Jinja2 templates, vanilla
JavaScript (workspace.js, inventory.js), Chart.js and qrcodejs (both vendored
under static/vendor/). CSS is hand-authored (foundation.css + per-surface
stylesheets). CSP restricts scripts to 'self' + inline, styles to 'self' +
inline + fonts.googleapis.com, fonts to fonts.gstatic.com + data:, images to
'self' + data:. No build system, no frontend framework.

## Users

IT administrators and operations staff managing an organization's equipment
pool; staff members who check what is assigned to them. [INFERRED: exact
industries/team sizes unknown; the app's roles (admin, reader), departments,
groups, and LDAP integration show a small-to-mid IT team running inventory
for a larger workforce.]

## Product Purpose

Track IT assets (laptops, monitors, network gear, plus user-defined custom
asset types) across their lifecycle: who holds what, what is available, what
is broken or written off. Success is an operator answering "where is it, who
has it, what state is it in" in seconds, and keeping the record honest via
bulk edits, reports, audits, and printable QR labels.

## Positioning

A self-hosted, role-aware inventory system that covers both fixed asset
classes and operator-defined custom asset types, with physical-world hooks
(printable QR labels linking back to the record) and bulk operations built
for high-volume corrections. [INFERRED: no competitive claims on record.]

## Operating Context

Screen-first, desktop-heavy work inside an office/IT context: dense tables,
filters, exports to Excel/CSV for stakeholders, printable A4 label sheets
stuck to physical devices. Both dark and light theme use are supported and
persisted; users may sit in bright or dim rooms. Fast keyboard use matters
(quick-nav Ctrl+K, E for edit, N for new, Backspace for back, live asset
search in the quick-nav dialog).

## Capabilities and Constraints

- Built-in asset types (laptops, screens, mice, keyboards, ...) + custom types
- Search (global + per-list), status filtering, per-type column chooser
  (persisted in localStorage), load-more pagination with retry, client-side
  sorting (aria-sort + data-sort-col), bulk select/delete/bulk-update, delete
  by tags, CSV + Excel export, Excel import
- Reports with dept/status filters; dashboard with KPI row, category browse,
  status doughnut + department bar charts (Chart.js), activity feed
- Printable QR labels (vendored qrcodejs; absolute asset URLs; print CSS)
- RBAC: roles, permissions, groups, departments; LDAP and SMTP settings;
  security settings, audit log, logs, backups/restore, branding (name + logo),
  forced password change, auto-logout with warning overlay
- Theme cycle (dark/classic/light/ocean/forest/sunset) persisted in
  localStorage; density toggle (data-density="compact"); quick-nav dialog
  (#quick-nav) with page + asset search; toast + flash messaging
- Hard UI contracts (tests/): no horizontal scroll at 1920/1440/1280/1024/768/
  390px; labelled stacked mobile records; editor two-column grid with save bar;
  no CSS gradients/animations on the dashboard and auth surfaces; both dark and
  light themes must stay fully styled; CSP and vendored-only runtime deps.
- Undecided product facts: none requested beyond the redesign.

## Brand Commitments

None recorded. The app name/branding is runtime-configurable (branding_name,
branding_logo); the code refers to "AssetManager" and a GitHub repository.
[INFERRED: no visual identity is sacred; the incumbent look is evidence, not
authority.]

## Evidence on Hand

No real customer data, testimonials, or screenshots. Test fixtures and demo
rows (e.g. "Acme / ProBook X") are synthetic. Future work must not fabricate
customers or benchmarks.

## Product Principles

1. Answers before decoration: an operator must find any asset faster than
   the old tool allowed.
2. Data density with air: tables stay precise and scannable without feeling
   cramped; every screen keeps one clear primary action.
3. Consistency across every surface: list, editor, report, settings, labels,
   login share one component grammar.
4. Both lights are first-class: dark and light themes are fully designed,
   never one real theme plus an inversion.
5. The record is the product: statuses, assignment, and history stay visibly
   true everywhere, including print.

## Accessibility & Inclusion

Keyboard-operable everywhere (skip link, quick-nav, sorting, dialogs, focus
return), aria-live status regions, visible focus rings, prefers-reduced-motion
handled in workspace.css, touch-friendly hit targets at 390px.

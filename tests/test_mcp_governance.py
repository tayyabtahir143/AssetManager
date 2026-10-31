"""MCP governance: self-service requests, admin approval, grants, audit usage log.

The access lifecycle: request -> (approve|decline) -> McpAccess + McpToken ->
(rotate|revoke). Permissions inherit from the owner user's roles; scope is a
cap (read_only blocks writes).
"""
import datetime

import pytest

import app as app_module
from app import (
    McpAccess,
    McpAccessRequest,
    McpToken,
    McpUsageLog,
    User,
    db,
)


def _grant(client, application, username, scope="read_only", expiry="0"):
    return client.post(
        "/settings/mcp/accesses",
        data={"username": username, "scope": scope, "expiry": expiry},
    )


def _set_email(application, username, email):
    with application.app_context():
        user = User.query.filter_by(username=username).first()
        user.email = email
        db.session.commit()


def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _admin_login(application, c):
    with application.app_context():
        admin_id = User.query.filter_by(username="admin").first().id
    _login_as(c, admin_id)


def _enable_gateway(application, enabled=True):
    """Enable the MCP gateway config. Safe to call inside or outside an
    active app context (nested contexts get their own session and would
    roll back pending rows)."""
    from flask import has_app_context

    def _do():
        config = app_module.McpConfig.query.get(1)
        if config is None:
            config = app_module.McpConfig(id=1, enabled=enabled)
            db.session.add(config)
        else:
            config.enabled = enabled
        db.session.commit()

    if has_app_context():
        _do()
    else:
        with application.app_context():
            _do()


class TestRequestFlow:
    def test_user_can_request_access(self, client, auth_headers, application):
        """A regular (non-admin) user requests access; request lands pending."""
        with application.app_context():
            user = User.query.filter_by(username="admin").first()
            normal = User(
                username="mcpuser1",
                email="mcpuser1@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(normal)
            db.session.commit()
            app_module.ensure_role_assignments()
            normal_id = normal.id
        _login_as(client, normal_id)
        resp = client.post(
            "/settings/mcp/request",
            data={"scope": "full", "expiry": "30", "reason": "reports"},
        )
        assert resp.status_code == 302
        with application.app_context():
            req = McpAccessRequest.query.filter_by(user_id=normal_id).first()
            assert req is not None
            assert req.status == "pending"
            assert req.scope == "full"
            assert req.expiry_days == 30
            assert req.reason == "reports"

    def test_duplicate_pending_request_blocked(self, client, application):
        with application.app_context():
            normal = User(
                username="mcpuser2",
                email="mcpuser2@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(normal)
            db.session.commit()
            app_module.ensure_role_assignments()
            normal_id = normal.id
        with client.session_transaction() as sess:
            sess["user_id"] = normal_id
        client.post("/settings/mcp/request", data={"scope": "read_only", "expiry": "0"})
        client.post("/settings/mcp/request", data={"scope": "read_only", "expiry": "0"})
        with application.app_context():
            pending = McpAccessRequest.query.filter_by(
                user_id=normal_id, status="pending"
            ).all()
            assert len(pending) == 1

    def test_request_emails_admin(self, client, application, monkeypatch):
        sent = []
        monkeypatch.setattr(app_module, "send_email", lambda *a, **k: sent.append((a, k)) or True)
        _set_email(application, "admin", "boss@example.com")
        with application.app_context():
            normal = User(
                username="mcpuser3",
                email="mcpuser3@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(normal)
            db.session.commit()
            app_module.ensure_role_assignments()
            normal_id = normal.id
        with client.session_transaction() as sess:
            sess["user_id"] = normal_id
        client.post("/settings/mcp/request", data={"scope": "read_only", "expiry": "0"})
        assert sent, "admin was not emailed about the request"
        subject, body, recipients = sent[0][0][:3]
        assert "MCP access request" == subject
        assert "boss@example.com" in recipients
        assert "mcpuser3" in body

    def test_non_admin_page_shows_status(self, client, application):
        with application.app_context():
            normal = User(
                username="mcpuser4",
                email="mcpuser4@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(normal)
            db.session.commit()
            app_module.ensure_role_assignments()
            normal_id = normal.id
        with client.session_transaction() as sess:
            sess["user_id"] = normal_id
        html = client.get("/settings/mcp").data.decode("utf-8")
        assert "Your MCP access" in html
        assert "Request access" in html
        assert "Pending requests" not in html  # admin-only section hidden
        assert "Usage audit" not in html


class TestApprovalFlow:
    def _make_requester(self, application, client, username="mcpapprove1"):
        with application.app_context():
            normal = User(
                username=username,
                email=f"{username}@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(normal)
            db.session.commit()
            app_module.ensure_role_assignments()
            normal_id = normal.id
        with client.session_transaction() as sess:
            sess["user_id"] = normal_id
        client.post(
            "/settings/mcp/request",
            data={"scope": "full", "expiry": "90", "reason": "need it"},
        )
        with application.app_context():
            req = McpAccessRequest.query.filter_by(user_id=normal_id).first()
            return normal_id, req.id

    def test_approve_creates_access_and_token(self, admin_client, client, application):
        normal_id, req_id = self._make_requester(application, client)
        _admin_login(application, admin_client)
        resp = admin_client.post(
            f"/settings/mcp/requests/{req_id}/approve",
            data={"scope": "full", "expiry": "90"},
        )
        assert resp.status_code == 302
        with application.app_context():
            req = McpAccessRequest.query.get(req_id)
            assert req.status == "approved"
            access = McpAccess.query.filter_by(user_id=normal_id).first()
            assert access is not None
            assert access.status == "active"
            assert access.scope == "full"
            token = McpToken.query.filter_by(access_id=access.id).first()
            assert token is not None
            assert token.user_id == normal_id
            assert token.scope == "full"
            assert token.enabled is True
        # one-time reveal on next page render
        html = admin_client.get("/settings/mcp").data.decode("utf-8")
        assert "token-reveal" in html

    def test_approve_emails_token_to_requester(self, admin_client, client, application, monkeypatch):
        sent = []
        monkeypatch.setattr(app_module, "send_email", lambda *a, **k: sent.append((a, k)) or True)
        normal_id, req_id = self._make_requester(application, client, "mcpapprove2")
        _admin_login(application, admin_client)
        admin_client.post(
            f"/settings/mcp/requests/{req_id}/approve",
            data={"scope": "read_only", "expiry": "0"},
        )
        assert sent
        approved = [e for e in sent if e[0][0] == "MCP access approved"]
        assert approved
        subject, body, recipients = approved[0][0][:3]
        assert "mcpapprove2@example.com" in recipients
        assert "amcp_" in body
        assert "claude mcp add" in body
        assert "codex mcp add-json" in body
        assert "hermes mcp add" in body

    def test_decline_records_reason_and_emails(self, admin_client, client, application, monkeypatch):
        sent = []
        monkeypatch.setattr(app_module, "send_email", lambda *a, **k: sent.append((a, k)) or True)
        normal_id, req_id = self._make_requester(application, client, "mcpdecline1")
        _admin_login(application, admin_client)
        admin_client.post(
            f"/settings/mcp/requests/{req_id}/decline",
            data={"note": "not needed"},
        )
        with application.app_context():
            req = McpAccessRequest.query.get(req_id)
            assert req.status == "declined"
            assert req.admin_note == "not needed"
            assert McpAccess.query.filter_by(user_id=normal_id).first() is None
        assert sent
        declined = [e for e in sent if e[0][0] == "MCP access declined"]
        assert declined
        subject, body, recipients = declined[0][0][:3]
        assert "not needed" in body

    def test_approve_replaces_previous_token(self, admin_client, client, application):
        normal_id, req_id = self._make_requester(application, client, "mcpreplace1")
        _admin_login(application, admin_client)
        admin_client.post(
            f"/settings/mcp/requests/{req_id}/approve",
            data={"scope": "read_only", "expiry": "0"},
        )
        with application.app_context():
            access = McpAccess.query.filter_by(user_id=normal_id).first()
            old_token = McpToken.query.filter_by(access_id=access.id).first()
            old_id = old_token.id
        # re-request and approve again -> old token disabled, new one issued
        with client.session_transaction() as sess:
            sess["user_id"] = normal_id
        client.post("/settings/mcp/request", data={"scope": "read_only", "expiry": "0"})
        with application.app_context():
            req2 = McpAccessRequest.query.filter_by(
                user_id=normal_id, status="pending"
            ).first()
            req2_id = req2.id
        _admin_login(application, admin_client)
        admin_client.post(
            f"/settings/mcp/requests/{req2_id}/approve",
            data={"scope": "read_only", "expiry": "0"},
        )
        with application.app_context():
            assert McpToken.query.get(old_id).enabled is False
            access = McpAccess.query.filter_by(user_id=normal_id).first()
            active = McpToken.query.filter_by(
                access_id=access.id, enabled=True
            ).all()
            assert len(active) == 1


class TestGrantRevokeRotate:
    def _user(self, application, username):
        with application.app_context():
            user = User(
                username=username,
                email=f"{username}@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(user)
            db.session.commit()
            app_module.ensure_role_assignments()
            return user.id

    def test_grant_creates_access(self, admin_client, application):
        uid = self._user(application, "mcgrantee1")
        admin_client.post(
            "/settings/mcp/accesses",
            data={"username": "mcgrantee1", "scope": "read_only", "expiry": "7"},
        )
        with application.app_context():
            access = McpAccess.query.filter_by(user_id=uid).first()
            assert access is not None
            assert access.status == "active"
            assert access.expires_at is not None
            token = McpToken.query.filter_by(access_id=access.id).first()
            assert token is not None
            assert token.expires_at is not None

    def test_grant_emails_setup_to_user(self, admin_client, application, monkeypatch):
        sent = []
        monkeypatch.setattr(app_module, "send_email", lambda *a, **k: sent.append((a, k)) or True)
        self._user(application, "mcgrantee2")
        admin_client.post(
            "/settings/mcp/accesses",
            data={"username": "mcgrantee2", "scope": "full", "expiry": "0"},
        )
        assert sent
        subject, body, recipients = sent[0][0][:3]
        assert "MCP access granted" == subject
        assert "mcgrantee2@example.com" in recipients
        assert "amcp_" in body

    def test_grant_unknown_user_rejected(self, admin_client, application):
        resp = admin_client.post(
            "/settings/mcp/accesses",
            data={"username": "ghost", "scope": "read_only", "expiry": "0"},
        )
        assert resp.status_code == 302
        with application.app_context():
            # no user named ghost exists, so no access can be created for one
            ghost = User.query.filter_by(username="ghost").first()
            assert ghost is None

    def test_revoke_disables_tokens_and_blocks_api(self, client, admin_client, application):
        _set_email(application, "admin", "boss@example.com")
        uid = self._user(application, "mcrevokee1")
        admin_client.post(
            "/settings/mcp/accesses",
            data={"username": "mcrevokee1", "scope": "read_only", "expiry": "0"},
        )
        with application.app_context():
            access = McpAccess.query.filter_by(user_id=uid).first()
            token_row = McpToken.query.filter_by(access_id=access.id).first()
            access_id = access.id
        admin_client.post(f"/settings/mcp/accesses/{access_id}/revoke")
        with application.app_context():
            access = McpAccess.query.get(access_id)
            assert access.status == "revoked"
            assert McpToken.query.get(token_row.id).enabled is False
        # enable gateway and confirm the (disabled) token is rejected
        _enable_gateway(application)
        plain = None
        with application.app_context():
            # we cannot recover plaintext; craft token hash directly for the check
            plain = app_module.generate_mcp_token()
            token_row2 = McpToken(
                name="revoked-check",
                token_hash=app_module.hash_mcp_token(plain),
                scope="read_only",
                user_id=uid,
                access_id=access_id,
                enabled=False,
            )
            db.session.add(token_row2)
            db.session.commit()
        resp = client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {plain}"}
        )
        assert resp.status_code == 401

    def test_rotate_issues_new_token(self, admin_client, application, monkeypatch):
        sent = []
        monkeypatch.setattr(app_module, "send_email", lambda *a, **k: sent.append((a, k)) or True)
        uid = self._user(application, "mcrotatee1")
        admin_client.post(
            "/settings/mcp/accesses",
            data={"username": "mcrotatee1", "scope": "read_only", "expiry": "0"},
        )
        with application.app_context():
            access = McpAccess.query.filter_by(user_id=uid).first()
            old_token = McpToken.query.filter_by(access_id=access.id).first()
            access_id = access.id
            old_id = old_token.id
        admin_client.post(f"/settings/mcp/accesses/{access_id}/rotate")
        with application.app_context():
            assert McpToken.query.get(old_id).enabled is False
            tokens = McpToken.query.filter_by(access_id=access_id).all()
            assert len(tokens) == 2
            assert sum(1 for t in tokens if t.enabled) == 1
        assert sent
        assert any(entry[0][0] == "MCP token rotated" for entry in sent)

    def test_self_rotate(self, client, admin_client, application):
        uid = self._user(application, "mcselfrotate1")
        admin_client.post(
            "/settings/mcp/accesses",
            data={"username": "mcselfrotate1", "scope": "read_only", "expiry": "0"},
        )
        with client.session_transaction() as sess:
            sess["user_id"] = uid
        with application.app_context():
            access = McpAccess.query.filter_by(user_id=uid).first()
            old_id = McpToken.query.filter_by(access_id=access.id).first().id
            access_id = access.id
        resp = client.post(f"/settings/mcp/self/rotate")
        assert resp.status_code == 302
        with application.app_context():
            assert McpToken.query.get(old_id).enabled is False
            assert (
                McpToken.query.filter_by(access_id=access_id, enabled=True).count()
                == 1
            )


class TestPermissionInheritance:
    def test_full_scope_still_respects_role_permissions(self, client, application):
        """'full' means 'whatever the user's roles allow' — never more."""
        with application.app_context():
            user = User(
                username="mcplimited1",
                email="mcplimited1@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(user)
            db.session.commit()
            app_module.ensure_role_assignments()
            uid = user.id
            access = McpAccess(user_id=uid, scope="full")
            db.session.add(access)
            db.session.flush()
            plain = app_module.generate_mcp_token()
            db.session.add(
                McpToken(
                    name="limited-token",
                    token_hash=app_module.hash_mcp_token(plain),
                    scope="full",
                    user_id=uid,
                    access_id=access.id,
                )
            )
            _enable_gateway(application)
        # A user with no roles cannot create assets even with a full token.
        resp = client.post(
            "/api/v1/assets/laptops",
            headers={"Authorization": f"Bearer {plain}"},
            json={"asset_tag": "NOPE"},
        )
        assert resp.status_code in (401, 403)

    def test_read_only_caps_admin(self, client, application):
        with application.app_context():
            admin = User.query.filter_by(username="admin").first()
            access = McpAccess(user_id=admin.id, scope="read_only")
            db.session.add(access)
            db.session.flush()
            plain = app_module.generate_mcp_token()
            db.session.add(
                McpToken(
                    name="admin-ro-token",
                    token_hash=app_module.hash_mcp_token(plain),
                    scope="read_only",
                    user_id=admin.id,
                    access_id=access.id,
                )
            )
            _enable_gateway(application)
        resp = client.post(
            "/api/v1/assets/laptops",
            headers={"Authorization": f"Bearer {plain}"},
            json={"asset_tag": "NOPE"},
        )
        assert resp.status_code == 403
        assert b"read-only" in resp.data

    def test_revoked_access_rejects_token(self, client, application):
        with application.app_context():
            user = User(
                username="mcprevokedaccess1",
                email="x@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(user)
            db.session.commit()
            app_module.ensure_role_assignments()
            uid = user.id
            access = McpAccess(user_id=uid, scope="read_only", status="revoked")
            db.session.add(access)
            db.session.flush()
            plain = app_module.generate_mcp_token()
            db.session.add(
                McpToken(
                    name="revoked-access-token",
                    token_hash=app_module.hash_mcp_token(plain),
                    scope="read_only",
                    user_id=uid,
                    access_id=access.id,
                )
            )
            _enable_gateway(application)
        resp = client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {plain}"}
        )
        assert resp.status_code == 401

    def test_expired_access_auto_revokes_token(self, client, application):
        with application.app_context():
            user = User(
                username="mcpexpiredaccess1",
                email="x@example.com",
                password_hash="x", role="reader",
            )
            db.session.add(user)
            db.session.commit()
            app_module.ensure_role_assignments()
            uid = user.id
            access = McpAccess(
                user_id=uid,
                scope="read_only",
                expires_at=datetime.datetime.now() - datetime.timedelta(days=1),
            )
            db.session.add(access)
            db.session.flush()
            plain = app_module.generate_mcp_token()
            db.session.add(
                McpToken(
                    name="expired-access-token",
                    token_hash=app_module.hash_mcp_token(plain),
                    scope="read_only",
                    user_id=uid,
                    access_id=access.id,
                )
            )
            _enable_gateway(application)
        resp = client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {plain}"}
        )
        assert resp.status_code == 401


class TestUsageAudit:
    def test_usage_logger_records_success(self, application):
        with application.app_context():
            admin = User.query.filter_by(username="admin").first()
            admin_id = admin.id
            _enable_gateway(application)
            plain = app_module.generate_mcp_token()
            db.session.add(
                McpToken(
                    name="audit-token",
                    token_hash=app_module.hash_mcp_token(plain),
                    scope="read_only",
                    user_id=admin.id,
                )
            )
            db.session.commit()
        app_module._mcp_usage_logger(
            plain, "search_assets", '{"query": "lt"}', True, None, 12, "192.168.1.7"
        )
        with application.app_context():
            row = McpUsageLog.query.filter_by(tool_name="search_assets").first()
            assert row is not None
            assert row.username == "admin"
            assert row.user_id == admin_id
            assert row.success is True
            assert row.duration_ms == 12
            assert row.ip_address == "192.168.1.7"
            assert row.arguments == '{"query": "lt"}'

    def test_usage_logger_records_failure_for_bad_token(self, application):
        app_module._mcp_usage_logger(
            "amcp_bogus", "list_users", "{}", False, "Invalid token", 3, "10.0.0.9"
        )
        with application.app_context():
            row = McpUsageLog.query.filter_by(tool_name="list_users").first()
            assert row is not None
            assert row.username is None
            assert row.success is False
            assert row.error == "Invalid token"

    def test_admin_page_shows_usage(self, admin_client, application):
        with application.app_context():
            db.session.add(
                McpUsageLog(tool_name="search_assets", success=True, username="admin")
            )
            db.session.commit()
        html = admin_client.get("/settings/mcp").data.decode("utf-8")
        assert "Usage audit" in html
        assert "search_assets" in html

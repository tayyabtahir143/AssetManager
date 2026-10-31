"""MCP management: scoped API tokens, gateway enable/disable, settings page."""
import app as app_module
from app import McpConfig, McpToken, User, db


def _make_token(application, name="Test token", scope="read_only", enabled=True):
    plain = app_module.generate_mcp_token()
    with application.app_context():
        admin = User.query.filter_by(username="admin").first()
        db.session.add(
            McpToken(
                name=name,
                token_hash=app_module.hash_mcp_token(plain),
                scope=scope,
                user_id=admin.id,
                enabled=enabled,
            )
        )
        db.session.commit()
    return plain


def _enable_gateway(application, enabled=True):
    with application.app_context():
        config = app_module.McpConfig.query.get(1)
        if config is None:
            config = app_module.McpConfig(id=1, enabled=enabled)
            db.session.add(config)
        else:
            config.enabled = enabled
        db.session.commit()


class TestMcpTokenAuth:
    def test_read_only_token_allows_get(self, client, application):
        _enable_gateway(application)
        token = _make_token(application, scope="read_only")
        resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_read_only_token_blocks_write(self, client, application):
        _enable_gateway(application)
        token = _make_token(application, scope="read_only")
        resp = client.post(
            "/api/v1/assets/laptops",
            headers={"Authorization": f"Bearer {token}"},
            json={"asset_tag": "X"},
        )
        assert resp.status_code == 403
        assert b"read-only" in resp.data

    def test_full_token_allows_write(self, client, application):
        _enable_gateway(application)
        token = _make_token(application, scope="full")
        resp = client.post(
            "/api/v1/assets/laptops",
            headers={"Authorization": f"Bearer {token}"},
            json={"asset_tag": "X"},
        )
        # 403 = read-only scope enforcement; anything else means full scope
        # passed the gate (create may still 400 on missing fields).
        assert resp.status_code != 403

    def test_gateway_disabled_blocks_tokens_but_not_jwt(self, client, auth_headers, application):
        _enable_gateway(application, enabled=False)
        token = _make_token(application)
        assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        assert client.get("/api/v1/users", headers=auth_headers).status_code == 200

    def test_revoked_token_rejected(self, client, application):
        _enable_gateway(application)
        token = _make_token(application, enabled=False)
        assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    def test_unknown_token_rejected(self, client, application):
        _enable_gateway(application)
        resp = client.get("/api/v1/users", headers={"Authorization": "Bearer amcp_bogus"})
        assert resp.status_code == 401

    def test_token_usage_updates_last_used(self, client, application):
        _enable_gateway(application)
        token = _make_token(application)
        client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        with application.app_context():
            row = McpToken.query.filter_by(name="Test token").first()
            assert row.last_used_at is not None


class TestMcpSettingsPage:
    def test_page_requires_app_admin(self, application, admin_client):
        anonymous = application.test_client()
        assert anonymous.get("/settings/mcp").status_code == 302
        assert admin_client.get("/settings/mcp").status_code == 200

    def test_page_lists_tokens(self, admin_client, application):
        _make_token(application, name="Claude Desktop")
        html = admin_client.get("/settings/mcp").data.decode("utf-8")
        assert "Claude Desktop" in html
        assert "Create token" in html

    def test_create_token_flow_shows_once(self, admin_client, application):
        resp = admin_client.post(
            "/settings/mcp/tokens",
            data={"name": "Hermes", "scope": "read_only"},
        )
        assert resp.status_code == 302
        html = admin_client.get("/settings/mcp").data.decode("utf-8")
        # The one-time reveal section appears exactly on the next render.
        assert "token-reveal" in html
        assert "Copy it now" in html
        html2 = admin_client.get("/settings/mcp").data.decode("utf-8")
        assert "token-reveal" not in html2
        with application.app_context():
            assert McpToken.query.filter_by(name="Hermes").first() is not None

    def test_invalid_scope_defaults_to_read_only(self, admin_client, application):
        admin_client.post("/settings/mcp/tokens", data={"name": "X", "scope": "nope"})
        with application.app_context():
            assert McpToken.query.filter_by(name="X").first().scope == "read_only"

    def test_toggle_enables_gateway(self, admin_client, application):
        admin_client.post("/settings/mcp/toggle", data={"enabled": "on"})
        with application.app_context():
            assert app_module.McpConfig.query.get(1).enabled is True
        admin_client.post("/settings/mcp/toggle")
        with application.app_context():
            assert app_module.McpConfig.query.get(1).enabled is False

    def test_revoke_and_delete(self, admin_client, application):
        _make_token(application, name="Doomed", scope="full")
        with application.app_context():
            token_id = McpToken.query.filter_by(name="Doomed").first().id
        admin_client.post(f"/settings/mcp/tokens/{token_id}/revoke")
        with application.app_context():
            assert McpToken.query.get(token_id).enabled is False
        admin_client.post(f"/settings/mcp/tokens/{token_id}/delete")
        with application.app_context():
            assert McpToken.query.get(token_id) is None

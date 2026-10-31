"""MCP management: scoped API tokens, gateway enable/disable, settings page."""
import os

import pytest

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

class TestEmbeddedGateway:
    """The MCP gateway runs inside the Flask process, started by the settings
    toggle; verify the protocol end-to-end over a real socket."""

    @pytest.fixture(autouse=True)
    def _gateway_cleanup(self):
        yield
        with app_module.app.app_context():
            config = app_module.get_mcp_config()
            if config.enabled:
                config.enabled = False
                app_module.db.session.commit()
        app_module.stop_mcp_gateway()

    def _wait_ready(self, timeout=10.0):
        import socket, time as _time

        port = int(os.environ.get("MCP_GATEWAY_PORT", "18765"))
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return True
            except OSError:
                _time.sleep(0.25)
        return False

    def _rpc(self, payload, headers=None):
        import httpx

        port = int(os.environ.get("MCP_GATEWAY_PORT", "18765"))
        return httpx.post(
            f"http://127.0.0.1:{port}/mcp",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **(headers or {}),
            },
            timeout=10,
        )

    def _result(self, resp):
        import json as _json

        text = resp.text
        if "event-stream" in resp.headers.get("content-type", ""):
            messages = [
                _json.loads(line[6:])
                for line in text.splitlines()
                if line.startswith("data: ")
            ]
            for msg in messages:
                if "result" in msg:
                    return msg["result"]
            raise AssertionError(f"No SSE result: {text[:300]}")
        return resp.json()["result"]

    def test_gateway_serves_mcp_after_enable(self, admin_client, application):
        admin_client.post("/settings/mcp/toggle", data={"enabled": "on"})
        assert app_module.mcp_gateway_running()
        assert self._wait_ready(), "gateway socket never became ready"
        resp = self._rpc({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        })
        assert resp.status_code == 200, resp.text[:300]
        result = self._result(resp)
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]

    def test_gateway_tool_call_with_token(self, admin_client, application):
        _enable_gateway(application)
        token = _make_token(application, name="Gateway token", scope="read_only")
        admin_client.post("/settings/mcp/toggle", data={"enabled": "on"})
        assert self._wait_ready()
        auth = {"Authorization": f"Bearer {token}"}
        init = self._rpc(
            {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
            headers=auth,
        )
        assert init.status_code == 200, init.text[:300]
        session_id = init.headers.get("mcp-session-id")
        assert session_id, "initialize did not return mcp-session-id"
        resp = self._rpc(
            {
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "search_assets", "arguments": {"query": "zzz"}},
            },
            headers={**auth, "mcp-session-id": session_id},
        )
        assert resp.status_code == 200, resp.text[:300]
        result = self._result(resp)
        assert result["isError"] is False
        text = result["content"][0]["text"]
        assert "results" in text

    def test_gateway_tool_call_without_token_errors(self, admin_client, application):
        _enable_gateway(application)
        admin_client.post("/settings/mcp/toggle", data={"enabled": "on"})
        assert self._wait_ready()
        init = self._rpc(
            {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
        )
        session_id = init.headers.get("mcp-session-id")
        resp = self._rpc(
            {
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "list_users", "arguments": {}},
            },
            headers={"mcp-session-id": session_id} if session_id else None,
        )
        assert resp.status_code == 200
        text = self._result(resp)["content"][0]["text"]
        assert "Missing token" in text or "Invalid token" in text

    def test_disable_stops_gateway(self, admin_client, application):
        admin_client.post("/settings/mcp/toggle", data={"enabled": "on"})
        assert self._wait_ready()
        admin_client.post("/settings/mcp/toggle")
        assert not app_module.mcp_gateway_running()
        assert not self._wait_ready(timeout=2.0)


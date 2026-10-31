"""MCP server client contract tests — drive the real AssetManagerClient
against the real Flask app through an httpx MockTransport (no sockets)."""
import httpx
import pytest

import mcp_server


class FlaskTransport(httpx.BaseTransport):
    """Adapts the Flask test client to the httpx transport interface."""

    def __init__(self, flask_client):
        self._client = flask_client

    def handle_request(self, request):
        # httpx passes bytes; werkzeug test client takes bytes too.
        raw_path = request.url.raw_path.decode()
        path = raw_path.split("?", 1)[0]
        resp = self._client.open(
            path=path,
            method=request.method,
            headers={k: v for k, v in request.headers.items()},
            data=request.content or None,
            query_string=request.url.query.decode() or None,
        )
        headers = list(resp.headers.items())
        return httpx.Response(
            status_code=resp.status_code,
            headers=headers,
            content=resp.data,
            request=request,
        )


class FakeHttp:
    """Minimal httpx.Client-like surface over a transport (for tests)."""

    def __init__(self, transport):
        self._transport = transport

    def _dispatch(self, method, url, **kwargs):
        kwargs.pop("timeout", None)
        kwargs.setdefault("headers", {})
        request = httpx.Request(method, url, **kwargs)
        return self._transport.handle_request(request)

    def get(self, url, **kwargs):
        return self._dispatch("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._dispatch("POST", url, **kwargs)


@pytest.fixture
def mcp_client(application):
    transport = FlaskTransport(application.test_client())
    client = mcp_server.AssetManagerClient(
        base_url="http://localhost",
        username="admin",
        password="admin",
        http=FakeHttp(transport),
    )
    mcp_server._client = client
    return client


class TestMcpClient:
    def test_login_and_search(self, mcp_client, application):
        with application.app_context():
            from app import Laptop, db

            db.session.add(
                Laptop(
                    asset_tag="MCP-LT-1", vendor="Acme", model="ProBook",
                    processor="i7", ram="16GB", hard_disk="512GB",
                    screen_size="14", assigned_to="free", status="In Stock",
                )
            )
            db.session.commit()
        data = mcp_client.get("/api/v1/search", params={"q": "MCP-LT-1"})
        assert data["results"]
        assert data["results"][0]["asset_tag"] == "MCP-LT-1"

    def test_dashboard_summary(self, mcp_client):
        data = mcp_client.get("/api/v1/dashboard-summary")
        assert "total_assets" in data and "categories" in data

    def test_asset_types_include_builtin(self, mcp_client):
        data = mcp_client.get("/api/v1/asset-types")
        keys = [t["key"] for t in data]
        assert "laptops" in keys

    def test_list_assets_builtin(self, mcp_client):
        data = mcp_client.get("/api/v1/assets/laptops")
        assert "items" in data and "total" in data

    def test_users_departments_roles_groups(self, mcp_client):
        assert isinstance(mcp_client.get("/api/v1/users"), list)
        assert isinstance(mcp_client.get("/api/v1/departments"), list)
        roles = mcp_client.get("/api/v1/roles")
        assert any(r["name"] == "admin" for r in roles)
        assert isinstance(mcp_client.get("/api/v1/groups"), list)

    def test_audit_log(self, mcp_client):
        data = mcp_client.get("/api/v1/audit-log")
        assert "items" in data and "total" in data

    def test_custom_asset_fallback(self, mcp_client, application):
        with application.app_context():
            from app import AssetItem, AssetType, Role, RolePermission, db

            asset_type = AssetType(key="cables_mcp3", label="Cables MCP3")
            db.session.add(asset_type)
            db.session.commit()
            admin_role = Role.query.filter_by(name="admin").first()
            db.session.add(
                RolePermission(
                    role_id=admin_role.id, asset_type="custom:cables_mcp3", can_read=True
                )
            )
            db.session.commit()
            item = AssetItem(asset_type_id=asset_type.id, data={"asset_tag": "MCP-CBL-9"})
            db.session.add(item)
            db.session.commit()
        data = mcp_server.list_assets("cables_mcp3")
        assert data["total"] == 1
        assert data["items"][0]["asset_tag"] == "MCP-CBL-9"
        assert mcp_server.get_asset("cables_mcp3", data["items"][0]["id"])["asset_tag"] == "MCP-CBL-9"
        assert "Unknown asset type" in mcp_server.list_assets("nope")["error"]

    def test_bad_credentials_raise(self, application):
        transport = FlaskTransport(application.test_client())
        client = mcp_server.AssetManagerClient(
            base_url="http://localhost", username="admin", password="wrong", http=FakeHttp(transport)
        )
        with pytest.raises(mcp_server.AssetManagerError):
            client.get("/api/v1/users")

    def test_missing_credentials_raise(self):
        client = mcp_server.AssetManagerClient(base_url="http://localhost", http=httpx)
        with pytest.raises(mcp_server.AssetManagerError):
            client.get("/api/v1/users")


class TestMcpToolFunctions:
    def test_tools_are_registered(self):
        tool_names = {fn for fn in dir(mcp_server) if fn in {
            "search_assets", "list_asset_types", "list_assets", "get_asset",
            "dashboard_summary", "list_users", "list_departments",
            "list_roles", "list_groups", "list_audit_log",
        }}
        assert len(tool_names) == 10

"""Contracts for the extended read-only REST API used by the MCP server."""
import app as app_module
from app import AssetItem, AssetType, AuditLog, Laptop, db


class TestExtendedReadOnlyApi:
    def test_dashboard_summary_shape_and_numbers(self, client, auth_headers):
        resp = client.get("/api/dashboard-summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ("total_assets", "assigned", "available", "broken", "categories"):
            assert key in data
        assert data["total_assets"] == data["assigned"] + data["available"] + data["broken"]
        assert any(c["key"] == "laptops" for c in data["categories"])

    def test_audit_log_returns_entries_and_requires_auth(self, client, auth_headers, admin_client, application):
        with application.app_context():
            db.session.add(AuditLog(action="create", entity_type="asset", entity_id="1", username="admin"))
            db.session.commit()
        assert client.get("/api/audit-log").status_code == 401
        resp = client.get("/api/audit-log", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        assert data["items"][0]["action"] == "create"

    def test_roles_endpoint(self, client, auth_headers):
        data = client.get("/api/roles", headers=auth_headers).get_json()
        names = [r["name"] for r in data]
        assert "admin" in names
        admin = next(r for r in data if r["name"] == "admin")
        assert "asset_permissions" in admin

    def test_groups_endpoint(self, client, auth_headers, application):
        with application.app_context():
            db.session.add(app_module.Group(name="Networking", role="reader"))
            db.session.commit()
        data = client.get("/api/groups", headers=auth_headers).get_json()
        assert any(g["name"] == "Networking" for g in data)

    def test_asset_types_include_custom_with_icon(self, client, auth_headers, application):
        with application.app_context():
            asset_type = AssetType(key="cables_mcp", label="Cables MCP", icon="cable")
            db.session.add(asset_type)
            db.session.commit()
        data = client.get("/api/asset-types", headers=auth_headers).get_json()
        custom = [t for t in data if t["key"] == "cables_mcp"]
        assert custom and custom[0]["custom"] is True and custom[0]["icon"] == "cable"
        assert all(t["custom"] is False for t in data if t["key"] == "laptops")

    def test_custom_assets_list_and_get(self, client, auth_headers, application):
        with application.app_context():
            asset_type = AssetType(key="cables_mcp2", label="Cables MCP2", has_quantity=False)
            db.session.add(asset_type)
            db.session.commit()
            admin_role = app_module.Role.query.filter_by(name="admin").first()
            db.session.add(app_module.RolePermission(role_id=admin_role.id, asset_type="custom:cables_mcp2", can_read=True))
            db.session.commit()
            item = AssetItem(
                asset_type_id=asset_type.id,
                data={"asset_tag": "CBL-MCP-1", "model": "USB-C", "status": "In Stock"},
            )
            db.session.add(item)
            db.session.commit()
        resp = client.get("/api/custom/cables_mcp2/assets", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["asset_tag"] == "CBL-MCP-1"
        get_resp = client.get(f"/api/custom/cables_mcp2/assets/{data['items'][0]['id']}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.get_json()["model"] == "USB-C"

    def test_custom_assets_unknown_type_404(self, client, auth_headers):
        assert client.get("/api/custom/nope/assets", headers=auth_headers).status_code == 404

    def test_dashboard_summary_survives_minimal_custom_item(self, client, auth_headers, application):
        # Regression: build_dept_summary raised UnboundLocalError on custom
        # assets whose data has no dept/status keys.
        with application.app_context():
            asset_type = AssetType(key="minimal_mcp", label="Minimal MCP", has_quantity=False)
            db.session.add(asset_type)
            db.session.commit()
            db.session.add(AssetItem(asset_type_id=asset_type.id, data={"asset_tag": "MIN-1"}))
            db.session.commit()
        resp = client.get("/api/dashboard-summary", headers=auth_headers)
        assert resp.status_code == 200

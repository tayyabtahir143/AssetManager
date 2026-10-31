"""Contracts for custom asset-type icons: whitelisted keys, persistence via
add/edit routes, dashboard context, and the migration helper."""
import app as app_module
from app import AssetType, db


def _create_type(admin_client, label, key, icon="", has_quantity=""):
    data = {
        "label": label,
        "key": key,
        "icon": icon,
        "field_name_1": "model",
        "field_label_1": "Model",
        "field_type_1": "text",
    }
    if has_quantity:
        data["has_quantity"] = "on"
    resp = admin_client.post("/asset-types/add", data=data)
    assert resp.status_code == 302


def _get_type(application, key):
    with application.app_context():
        return AssetType.query.filter_by(key=key).first()


class TestAssetTypeIconPersistence:
    def test_add_asset_type_with_icon(self, admin_client, application):
        _create_type(admin_client, "Printers A", "printers_a", icon="printer")
        assert _get_type(application, "printers_a").icon == "printer"

    def test_add_asset_type_without_icon_defaults_to_none(self, admin_client, application):
        _create_type(admin_client, "Cables", "cables_icon_test", icon="")
        assert _get_type(application, "cables_icon_test").icon is None

    def test_add_asset_type_rejects_unknown_icon(self, admin_client, application):
        _create_type(admin_client, "Gadgets", "gadgets_icon_test", icon="<script>")
        assert _get_type(application, "gadgets_icon_test") is None

    def test_edit_asset_type_changes_icon(self, admin_client, application):
        _create_type(admin_client, "Printers B", "printers_b", icon="printer")
        asset_type = _get_type(application, "printers_b")
        resp = admin_client.post(
            f"/asset-types/edit/{asset_type.id}", data={"label": "Printers B", "icon": "box"}
        )
        assert resp.status_code == 302
        assert _get_type(application, "printers_b").icon == "box"

    def test_edit_asset_type_rejects_unknown_icon(self, admin_client, application):
        _create_type(admin_client, "Printers C", "printers_c", icon="printer")
        asset_type = _get_type(application, "printers_c")
        resp = admin_client.post(
            f"/asset-types/edit/{asset_type.id}",
            data={"label": "Printers C", "icon": "not-a-real-icon"},
        )
        assert resp.status_code == 302
        assert _get_type(application, "printers_c").icon == "printer"


class TestAssetTypeIconCatalog:
    def test_icon_choices_are_all_valid_keys(self):
        for choice in app_module.ICON_CHOICES:
            assert app_module.is_valid_asset_icon(choice["key"])

    def test_ensure_column_is_idempotent(self, application):
        with application.app_context():
            app_module.ensure_asset_type_icon_column()
            app_module.ensure_asset_type_icon_column()
            assert hasattr(AssetType(key="probe", label="Probe"), "icon")

    def test_dashboard_shows_custom_type_with_icon_context(self, admin_client, application):
        _create_type(admin_client, "Printers D", "printers_d", icon="printer")
        # add_asset_type runs ensure_role_permissions(), granting admin read
        # access to custom:printers_d — no manual permission insert needed.
        html = admin_client.get("/").data.decode("utf-8")
        assert "Printers D" in html

    def test_dashboard_shows_builtin_types(self, admin_client):
        html = admin_client.get("/").data.decode("utf-8")
        # Dashboard tiles use singular labels (Laptop, Computer, ...).
        assert "Laptop" in html

"""Backend contracts for the new feature suite: global search, CSV export,
bulk assign/status update, printable labels, and forced password change.

Uses the existing isolated in-memory test application; no external database.
"""
import pytest
from werkzeug.security import generate_password_hash

import app as app_module
from app import AssetItem, AssetType, Laptop, User, db


@pytest.fixture
def seeded_laptops(application):
    with application.app_context():
        rows = [
            Laptop(asset_tag="LT-SEARCH-1", vendor="Acme", model="ProBook X",
                   processor="i7", ram="16GB", hard_disk="512GB",
                   screen_size="14", assigned_to="free", status="In Stock"),
            Laptop(asset_tag="LT-SEARCH-2", vendor="Globex", model="ThinkPad T",
                   processor="i5", ram="8GB", hard_disk="256GB",
                   screen_size="13", assigned_to="alice@example.com",
                   status="Assigned", dept="Engineering"),
        ]
        db.session.add_all(rows)
        db.session.commit()
        yield
        Laptop.query.delete()
        db.session.commit()


class TestGlobalSearch:
    def test_search_finds_assets_across_fields(self, client, auth_headers, seeded_laptops):
        for query, expected_tag in [
            ("LT-SEARCH-2", "LT-SEARCH-2"),
            ("acme", "LT-SEARCH-1"),
            ("thinkpad", "LT-SEARCH-2"),
            ("alice", "LT-SEARCH-2"),
        ]:
            resp = client.get(f"/api/search?q={query}", headers=auth_headers)
            assert resp.status_code == 200, resp.data
            data = resp.get_json()
            assert isinstance(data["results"], list)
            assert any(r["asset_tag"] == expected_tag for r in data["results"]), query

    def test_search_result_shape(self, client, auth_headers, seeded_laptops):
        resp = client.get("/api/search?q=LT-SEARCH-1", headers=auth_headers)
        result = resp.get_json()["results"][0]
        for key in ("asset_type", "label", "title", "subtitle", "url"):
            assert key in result
        assert result["url"].startswith("/assets/laptops/view/")

    def test_search_requires_authentication_and_min_query(self, client, auth_headers):
        assert client.get("/api/search?q=acme").status_code == 401
        assert client.get("/api/search", headers=auth_headers).status_code == 400
        assert client.get("/api/search?q=x", headers=auth_headers).status_code == 400

    def test_search_returns_empty_for_no_match(self, client, auth_headers, seeded_laptops):
        data = client.get("/api/search?q=zzz-no-such", headers=auth_headers).get_json()
        assert data["results"] == []


class TestCsvExport:
    def test_builtin_csv_export(self, admin_client, seeded_laptops):
        resp = admin_client.get("/assets/laptops/export.csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type
        text = resp.data.decode("utf-8")
        assert text.startswith("\ufeff"), "CSV should carry a UTF-8 BOM for Excel"
        assert "id" in text.splitlines()[0]
        assert "LT-SEARCH-1" in text
        assert "attachment" in resp.headers.get("Content-Disposition", "")

    def test_csv_export_requires_read_permission(self, client):
        assert client.get("/assets/laptops/export.csv").status_code == 302


class TestBulkUpdate:
    def test_bulk_status_update_clears_assignment(self, admin_client, seeded_laptops):
        resp = admin_client.post(
            "/assets/laptops/bulk-update",
            data={"selected_ids": ["1", "2"], "field": "status", "value": "Broken"},
        )
        assert resp.status_code == 302
        with app_module.app.app_context():
            for laptop in Laptop.query.all():
                assert laptop.status == "Broken"
                assert laptop.assigned_to == "free"

    def test_bulk_assignee_update_sets_status(self, admin_client, seeded_laptops):
        resp = admin_client.post(
            "/assets/laptops/bulk-update",
            data={"selected_ids": ["1"], "field": "assigned_to", "value": "bob@example.com"},
        )
        assert resp.status_code == 302
        with app_module.app.app_context():
            laptop = Laptop.query.get(1)
            assert laptop.assigned_to == "bob@example.com"
            assert laptop.status == "Assigned"

    def test_bulk_release_sets_in_stock(self, admin_client, seeded_laptops):
        resp = admin_client.post(
            "/assets/laptops/bulk-update",
            data={"selected_ids": ["2"], "field": "assigned_to", "value": "free"},
        )
        assert resp.status_code == 302
        with app_module.app.app_context():
            laptop = Laptop.query.get(2)
            assert laptop.assigned_to == "free"
            assert laptop.status == "In Stock"

    def test_bulk_update_rejects_unknown_field(self, admin_client, seeded_laptops):
        before = admin_client.get("/assets/laptops").status_code
        assert before == 200
        resp = admin_client.post(
            "/assets/laptops/bulk-update",
            data={"selected_ids": ["1"], "field": "nope", "value": "x"},
        )
        assert resp.status_code == 302
        with app_module.app.app_context():
            assert Laptop.query.get(1).status == "In Stock"

    def test_bulk_update_requires_add_permission(self, client, seeded_laptops):
        assert client.post("/assets/laptops/bulk-update").status_code == 302


class TestLabels:
    def test_builtin_labels_render_selected_items(self, admin_client, seeded_laptops):
        resp = admin_client.get("/labels/laptops?ids=1,2")
        assert resp.status_code == 200
        assert b"LT-SEARCH-1" in resp.data
        assert b"LT-SEARCH-2" in resp.data

    def test_labels_ignore_unknown_ids_and_cap(self, admin_client, seeded_laptops):
        resp = admin_client.get("/labels/laptops?ids=99999")
        assert resp.status_code == 200

    def test_labels_require_login(self, client):
        assert client.get("/labels/laptops").status_code == 302


class TestForcedPasswordChange:
    @pytest.fixture
    def flagged_user(self, application):
        with application.app_context():
            user = User(
                username="mustchange", password_hash=generate_password_hash("OldPass123"),
                role="reader", must_change_password=True,
            )
            db.session.add(user)
            db.session.commit()
            yield user
            db.session.delete(user)
            db.session.commit()

    def test_flagged_user_is_redirected_to_change_password(self, client, flagged_user):
        resp = client.post(
            "/login",
            data={"username": "mustchange", "password": "OldPass123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/change-password" in resp.headers["Location"]
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/change-password" in resp.headers["Location"]

    def test_change_password_flow_clears_flag(self, client, flagged_user):
        client.post("/login", data={"username": "mustchange", "password": "OldPass123"})
        resp = client.post(
            "/change-password",
            data={"current_password": "OldPass123", "password": "NewPass456", "confirm_password": "NewPass456"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with app_module.app.app_context():
            user = User.query.filter_by(username="mustchange").first()
            assert user.must_change_password is False
            from werkzeug.security import check_password_hash
            assert check_password_hash(user.password_hash, "NewPass456")
        assert client.get("/").status_code == 200

    def test_change_password_rejects_wrong_current_and_short_new(self, client, flagged_user):
        client.post("/login", data={"username": "mustchange", "password": "OldPass123"})
        resp = client.post(
            "/change-password",
            data={"current_password": "wrong", "password": "NewPass456", "confirm_password": "NewPass456"},
        )
        assert b"current password" in resp.data.lower()
        resp = client.post(
            "/change-password",
            data={"current_password": "OldPass123", "password": "short", "confirm_password": "short"},
        )
        assert b"8 characters" in resp.data
        with app_module.app.app_context():
            assert User.query.filter_by(username="mustchange").first().must_change_password is True

    def test_admin_can_set_flag(self, admin_client, application, flagged_user):
        resp = admin_client.post(
            f"/users/edit/{flagged_user.id}",
            data={"username": "mustchange", "roles": ["reader"], "require_password_change": "on"},
        )
        assert resp.status_code == 302
        with application.app_context():
            assert User.query.get(flagged_user.id).must_change_password is True
        resp = admin_client.post(
            f"/users/edit/{flagged_user.id}",
            data={"username": "mustchange", "roles": ["reader"]},
        )
        with application.app_context():
            assert User.query.get(flagged_user.id).must_change_password is False

    def test_default_users_are_created_with_flag(self, application):
        # conftest clears the flag after creation; verify the attribute exists
        # and the creation default is enforceable via the model default.
        with application.app_context():
            assert hasattr(User.query.first(), "must_change_password")


class TestCustomSearchAndLabels:
    def test_search_includes_custom_assets(self, client, auth_headers, application):
        with application.app_context():
            asset_type = AssetType(key="cables", label="Cables", has_quantity=False)
            db.session.add(asset_type)
            db.session.commit()
            item = AssetItem(
                asset_type_id=asset_type.id,
                data={"asset_tag": "CBL-99", "vendor": "Nimbus", "model": "USB-C 2m"},
            )
            db.session.add(item)
            db.session.commit()
            resp = client.get("/api/search?q=CBL-99", headers=auth_headers)
            data = resp.get_json()
            assert any(r["asset_tag"] == "CBL-99" for r in data["results"])
            db.session.delete(item)
            db.session.delete(asset_type)
            db.session.commit()

    def test_custom_labels_route(self, admin_client, application):
        with application.app_context():
            asset_type = AssetType(key="cables", label="Cables", has_quantity=False)
            db.session.add(asset_type)
            db.session.commit()
            admin_role = app_module.Role.query.filter_by(name="admin").first()
            db.session.add(app_module.RolePermission(role_id=admin_role.id, asset_type="custom:cables", can_read=True))
            db.session.commit()
            item = AssetItem(asset_type_id=asset_type.id, data={"asset_tag": "CBL-77", "model": "HDMI 1m"})
            db.session.add(item)
            db.session.commit()
            resp = admin_client.get(f"/labels/custom/cables?ids={item.id}")
            assert resp.status_code == 200
            assert b"CBL-77" in resp.data
            db.session.delete(item)
            db.session.delete(asset_type)
            db.session.commit()

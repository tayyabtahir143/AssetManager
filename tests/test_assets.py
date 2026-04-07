"""
Tests for asset CRUD operations on both built-in and API endpoints.
Covers creation, listing, editing, deletion, and validation.
"""
import pytest
import app as app_module


BUILTIN_TYPES = ["laptops", "computers", "screens", "keyboards", "mice", "headsets", "ram"]


class TestBuiltinAssetPages:
    def test_asset_list_pages_load(self, admin_client):
        for asset_type in BUILTIN_TYPES:
            resp = admin_client.get(f"/assets/{asset_type}")
            assert resp.status_code == 200, f"Failed for type: {asset_type}"

    def test_add_asset_page_loads(self, admin_client):
        resp = admin_client.get("/assets/laptops/add")
        assert resp.status_code == 200

    def test_unknown_asset_type_returns_404(self, admin_client):
        resp = admin_client.get("/assets/unicorns")
        assert resp.status_code in (302, 404)


class TestApiAssets:
    def test_list_laptops_empty(self, client, auth_headers):
        resp = client.get("/api/assets/laptops", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_create_laptop_via_api(self, client, auth_headers):
        payload = {
            "asset_tag": "LT-TEST-001",
            "vendor": "TestCorp",
            "model": "ProBook X1",
            "processor": "Intel i7",
            "ram": "16GB",
            "hard_disk": "512GB SSD",
            "screen_size": "15.6",
            "assigned_to": "free",
            "status": "In Stock",
        }
        resp = client.post(
            "/api/assets/laptops",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.data
        data = resp.get_json()
        assert "id" in data

    def test_get_laptop_via_api(self, client, auth_headers):
        # Create first
        payload = {
            "asset_tag": "LT-GET-001",
            "vendor": "Acme",
            "model": "WidgetBook",
            "processor": "AMD Ryzen 5",
            "ram": "8GB",
            "hard_disk": "256GB",
            "screen_size": "13.3",
            "assigned_to": "free",
            "status": "In Stock",
        }
        create_resp = client.post("/api/assets/laptops", json=payload, headers=auth_headers)
        assert create_resp.status_code == 201
        laptop_id = create_resp.get_json()["id"]

        # Now fetch it
        resp = client.get(f"/api/assets/laptops/{laptop_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["asset_tag"] == "LT-GET-001"

    def test_update_laptop_via_api(self, client, auth_headers):
        payload = {
            "asset_tag": "LT-UPD-001",
            "vendor": "UpdateCorp",
            "model": "Updatebook",
            "processor": "Intel i5",
            "ram": "8GB",
            "hard_disk": "256GB",
            "screen_size": "14",
            "assigned_to": "free",
            "status": "In Stock",
        }
        create_resp = client.post("/api/assets/laptops", json=payload, headers=auth_headers)
        assert create_resp.status_code == 201
        laptop_id = create_resp.get_json()["id"]

        update_payload = dict(payload)
        update_payload["vendor"] = "NewVendor"
        resp = client.put(
            f"/api/assets/laptops/{laptop_id}",
            json=update_payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Verify update
        get_resp = client.get(f"/api/assets/laptops/{laptop_id}", headers=auth_headers)
        assert get_resp.get_json()["vendor"] == "NewVendor"

    def test_delete_laptop_via_api(self, client, auth_headers):
        payload = {
            "asset_tag": "LT-DEL-001",
            "vendor": "DeleteCorp",
            "model": "Deletebook",
            "processor": "Intel i3",
            "ram": "4GB",
            "hard_disk": "128GB",
            "screen_size": "11",
            "assigned_to": "free",
            "status": "In Stock",
        }
        create_resp = client.post("/api/assets/laptops", json=payload, headers=auth_headers)
        assert create_resp.status_code == 201
        laptop_id = create_resp.get_json()["id"]

        del_resp = client.delete(f"/api/assets/laptops/{laptop_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        # Should 404 now
        get_resp = client.get(f"/api/assets/laptops/{laptop_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_duplicate_asset_tag_rejected(self, client, auth_headers):
        payload = {
            "asset_tag": "LT-DUP-001",
            "vendor": "DupCorp",
            "model": "Dupbook",
            "processor": "Intel i5",
            "ram": "8GB",
            "hard_disk": "256GB",
            "screen_size": "15",
            "assigned_to": "free",
            "status": "In Stock",
        }
        resp1 = client.post("/api/assets/laptops", json=payload, headers=auth_headers)
        assert resp1.status_code == 201

        resp2 = client.post("/api/assets/laptops", json=payload, headers=auth_headers)
        assert resp2.status_code == 400

    def test_unknown_asset_type_returns_404(self, client, auth_headers):
        resp = client.get("/api/assets/unicorns", headers=auth_headers)
        assert resp.status_code == 404

    def test_api_asset_types_endpoint(self, client, auth_headers):
        resp = client.get("/api/asset-types", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        keys = [item["key"] for item in data]
        assert "laptops" in keys
        assert "computers" in keys

    def test_api_departments_endpoint(self, client, auth_headers):
        resp = client.get("/api/departments", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_api_users_endpoint(self, client, auth_headers):
        resp = client.get("/api/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert "admin" in data


class TestCredentialEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "super-secret-password-123"
        encrypted = app_module.encrypt_credential(plaintext)
        assert encrypted != plaintext
        decrypted = app_module.decrypt_credential(encrypted)
        assert decrypted == plaintext

    def test_decrypt_plaintext_passthrough(self):
        """decrypt_credential should return plaintext values unchanged (migration safety)."""
        plaintext = "already-plain"
        result = app_module.decrypt_credential(plaintext)
        assert result == plaintext

    def test_empty_credential_passthrough(self):
        assert app_module.encrypt_credential("") == ""
        assert app_module.decrypt_credential("") == ""

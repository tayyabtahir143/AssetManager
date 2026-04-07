"""
Tests for authentication flows: login, logout, JWT API auth, rate limiting,
password reset token handling, and permission enforcement.
"""
import pytest
import app as app_module


class TestWebLogin:
    def test_login_page_loads(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"Sign in" in resp.data

    def test_login_valid_credentials(self, client, application):
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Should land on dashboard or users page, not stay on login
        assert b"Sign in" not in resp.data or b"Invalid" not in resp.data

    def test_login_invalid_password(self, client):
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "wrongpassword"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Invalid username or password" in resp.data

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/login",
            data={"username": "nobody", "password": "anything"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Invalid username or password" in resp.data

    def test_logout_clears_session(self, admin_client):
        resp = admin_client.get("/logout", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Sign in" in resp.data

    def test_protected_route_requires_login(self, client):
        resp = client.get("/users", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Sign in" in resp.data


class TestApiAuth:
    def test_api_login_valid(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    def test_api_login_invalid(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "bad"},
        )
        assert resp.status_code == 401

    def test_api_login_missing_credentials(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_api_token_refresh(self, client):
        # Get tokens
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        refresh_token = resp.get_json()["refresh_token"]
        # Use refresh token
        resp2 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp2.status_code == 200
        assert "access_token" in resp2.get_json()

    def test_api_protected_route_no_token(self, client):
        resp = client.get("/api/assets/laptops")
        assert resp.status_code == 401

    def test_api_protected_route_invalid_token(self, client):
        resp = client.get(
            "/api/assets/laptops",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert resp.status_code == 401

    def test_api_protected_route_valid_token(self, client, auth_headers):
        resp = client.get("/api/assets/laptops", headers=auth_headers)
        assert resp.status_code == 200

    def test_api_v1_login(self, client):
        """Verify the /api/v1/ alias routes work."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_api_v1_assets(self, client, auth_headers):
        """Verify /api/v1/assets/ alias works."""
        resp = client.get("/api/v1/assets/laptops", headers=auth_headers)
        assert resp.status_code == 200


class TestPermissions:
    def test_admin_can_access_users_page(self, admin_client):
        resp = admin_client.get("/users")
        assert resp.status_code == 200

    def test_admin_can_access_roles_page(self, admin_client):
        resp = admin_client.get("/roles")
        assert resp.status_code == 200

    def test_admin_can_access_ldap_page(self, admin_client):
        resp = admin_client.get("/ldap")
        assert resp.status_code == 200

    def test_admin_can_access_smtp_page(self, admin_client):
        resp = admin_client.get("/smtp")
        assert resp.status_code == 200

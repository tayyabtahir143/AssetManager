"""
Pytest configuration and shared fixtures for AssetManager tests.
Uses an in-memory SQLite database so tests are isolated and fast.
"""
import os
import pytest

# Set test environment BEFORE importing app so config is picked up at module load
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOG_DIR"] = "/tmp/assetmanager_test_logs"
os.environ["WTF_CSRF_ENABLED"] = "False"

import app as app_module


@pytest.fixture(scope="session")
def application():
    """Create a test Flask application with in-memory SQLite."""
    app_module.app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "WTF_CSRF_CHECK_DEFAULT": False,
            "SECRET_KEY": "test-secret-key-do-not-use-in-production",
            "SERVER_NAME": "localhost",
        }
    )
    # Rebuild the Fernet key with the test SECRET_KEY
    app_module._FERNET = app_module.Fernet(
        app_module._make_fernet_key("test-secret-key-do-not-use-in-production")
    )
    with app_module.app.app_context():
        app_module.db.create_all()
        app_module.ensure_default_roles()
        app_module.ensure_role_assignments()
        app_module.ensure_default_users()
        app_module.ensure_role_permissions()
        yield app_module.app
        app_module.db.session.remove()
        app_module.db.drop_all()


@pytest.fixture()
def client(application):
    """Test client with a fresh session per test."""
    return application.test_client()


@pytest.fixture()
def admin_client(client, application):
    """Test client pre-logged-in as the default admin user."""
    with application.app_context():
        admin = app_module.User.query.filter_by(username="admin").first()
        assert admin is not None, "Default admin user not found"
        admin_id = admin.id
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
    return client


@pytest.fixture()
def auth_headers(application):
    """Return JWT Bearer headers for API tests. Each call generates fresh tokens."""
    with application.test_client() as c:
        resp = c.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        if resp.status_code != 200:
            # Roll back any failed DB transaction before retrying
            with application.app_context():
                app_module.db.session.rollback()
            resp = c.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
        assert resp.status_code == 200, f"API login failed: {resp.data}"
        token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

"""Operational hardening contracts: response headers, static caching, and
update-check backoff. No database or schema involvement."""
import pytest

import app as app_module


class TestSecurityHeaders:
    def test_unauthenticated_pages_carry_security_headers(self, client):
        response = client.get('/login')
        assert response.status_code == 200
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('X-Frame-Options') == 'DENY'
        assert response.headers.get('Referrer-Policy') == 'same-origin'
        permissions = response.headers.get('Permissions-Policy', '')
        assert 'camera=()' in permissions
        assert 'geolocation=()' in permissions

    def test_content_security_policy_allows_local_assets_only(self, client):
        response = client.get('/login')
        csp = response.headers.get('Content-Security-Policy', '')
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp
        assert "form-action 'self'" in csp
        assert "'self'" in csp
        assert 'https://fonts.googleapis.com' in csp
        assert 'https://fonts.gstatic.com' in csp
        # No third-party script origins are permitted.
        assert 'jsdelivr' not in csp and 'unpkg' not in csp and 'cdnjs' not in csp

    def test_authenticated_pages_carry_security_headers(self, admin_client):
        response = admin_client.get('/assets/laptops')
        assert response.status_code == 200
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('X-Frame-Options') == 'DENY'
        assert 'frame-ancestors' in response.headers.get('Content-Security-Policy', '')

    def test_session_cookie_contract(self, client):
        assert app_module.app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
        assert app_module.app.config['SESSION_COOKIE_HTTPONLY'] is True


class TestStaticCaching:
    def test_static_responses_carry_cache_control(self, client):
        response = client.get('/static/workspace.css')
        assert response.status_code == 200
        assert response.headers.get('Cache-Control')

    def test_production_cache_policy_is_long_lived(self):
        control = app_module.static_cache_control(development=False)
        assert 'max-age=86400' in control
        assert 'public' in control

    def test_development_cache_policy_is_short(self):
        control = app_module.static_cache_control(development=True)
        assert 'max-age=' in control and '86400' not in control


class TestUpdateCheckBackoff:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        before = dict(app_module.UPDATE_CHECK_CACHE)
        app_module.UPDATE_CHECK_CACHE.update({
            'timestamp': 0, 'next_check': 0, 'available': False,
            'error': None, 'latest_digest': None, 'current_digest': None,
        })
        yield
        app_module.UPDATE_CHECK_CACHE.update(before)

    def test_failure_backs_off_and_does_not_refetch(self, monkeypatch):
        calls = []
        def failing_urlopen(*args, **kwargs):
            calls.append(args[0])
            raise OSError('offline')
        monkeypatch.setattr(app_module, 'urlopen', failing_urlopen)
        monkeypatch.setattr(app_module, 'APP_VERSION', None)
        first = app_module.get_update_status()
        second = app_module.get_update_status()
        assert first['error'] == 'offline'
        assert second is first or second['error'] == 'offline'
        assert len(calls) == 1, 'backoff window must skip repeated network calls'

    def test_success_resets_to_short_window(self, monkeypatch):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return self._payload

        def ok_urlopen(url, timeout=None):
            return FakeResponse(b'{"last_updated":"2026-01-01T00:00:00Z","images":[]}')

        monkeypatch.setattr(app_module, 'urlopen', ok_urlopen)
        monkeypatch.setattr(app_module, 'APP_VERSION', None)
        app_module.UPDATE_CHECK_CACHE['next_check'] = 0
        app_module.get_update_status()
        import time
        assert app_module.UPDATE_CHECK_CACHE['next_check'] > time.time()
        assert app_module.UPDATE_CHECK_CACHE['next_check'] <= time.time() + 400

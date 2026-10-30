"""UI contracts exercised against the isolated in-memory application."""
from html.parser import HTMLParser


class LayoutParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_shared_layout_has_keyboard_navigation(admin_client):
    response = admin_client.get('/assets/laptops')
    assert response.status_code == 200
    document = LayoutParser()
    document.feed(response.get_data(as_text=True))
    assert any(tag == 'a' and attrs.get('href') == '#main-content'
               for tag, attrs in document.tags)
    assert any(tag == 'main' and attrs.get('id') == 'main-content'
               for tag, attrs in document.tags)
    assert any(tag == 'button' and attrs.get('aria-controls') == 'sidebar'
               and attrs.get('aria-expanded') == 'false'
               for tag, attrs in document.tags)


def test_shared_design_stylesheet_is_served(client):
    response = client.get('/static/workspace.css')
    assert response.status_code == 200
    assert b'prefers-reduced-motion' in response.data


def test_shared_layout_renders_settings_and_inventory(admin_client):
    for path in ['/','/assets/laptops', '/assets/laptops/add', '/reports',
                 '/users', '/groups', '/roles', '/departments', '/settings/security',
                 '/branding', '/ldap', '/smtp', '/audit', '/backups']:
        response = admin_client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        assert b'workspace.css' in response.data

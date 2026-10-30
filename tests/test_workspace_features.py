"""Regression coverage for progressive-enhancement navigation."""
from html.parser import HTMLParser


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


def test_quick_navigation_is_available_without_database_changes(admin_client):
    response = admin_client.get('/')
    html = response.get_data(as_text=True)
    doc = Elements()
    doc.feed(html)
    assert any(tag == 'dialog' and attrs.get('id') == 'quick-nav'
               for tag, attrs in doc.items)
    assert any(tag == 'input' and attrs.get('id') == 'quick-nav-search'
               and attrs.get('aria-label') for tag, attrs in doc.items)
    assert 'workspace.js' in html
    assert any(tag == 'button' and attrs.get('id') == 'density-toggle'
               for tag, attrs in doc.items)


def test_workspace_script_is_served(client):
    response = client.get('/static/workspace.js')
    assert response.status_code == 200
    assert b'localStorage' in response.data
    assert b'keydown' in response.data

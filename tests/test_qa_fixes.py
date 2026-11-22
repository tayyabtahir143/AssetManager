"""Regression tests for issues found in the exploratory QA pass."""
from urllib.parse import urlparse

import pytest

import app as app_module

pw = pytest.importorskip('playwright.sync_api')

XSS_USER = '<img src=x onerror="window.__xss=1">'


def _serve_with_csp(client):
    def serve(route):
        url = urlparse(route.request.url)
        if url.netloc != 'localhost':
            route.fulfill(status=200, body='')
            return
        response = client.get(url.path + ('?' + url.query if url.query else ''))
        route.fulfill(status=response.status_code, body=response.data,
                      content_type=response.content_type,
                      headers={'Content-Security-Policy': response.headers.get('Content-Security-Policy', '')})
    return serve


def test_assignee_autocomplete_does_not_render_usernames_as_html(application, admin_client):
    """Usernames (local or LDAP-synced) reach the assignee dropdown; they must
    be inserted as text, never parsed as markup (stored DOM XSS)."""
    with application.app_context():
        user = app_module.User.query.filter_by(username=XSS_USER).first()
        if user is None:
            user = app_module.User(username=XSS_USER, password_hash='x', role='reader')
            app_module.db.session.add(user)
            app_module.db.session.commit()
    try:
        with pw.sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except pw.Error as exc:
                pytest.skip(f'Install Chromium with playwright install chromium: {exc}')
            page = browser.new_page()
            page.route('**/*', _serve_with_csp(admin_client))
            page.goto('http://localhost/assets/laptops/add')
            status = page.locator('#status')
            assigned = status.locator('option', has_text='Assigned').first.get_attribute('value')
            status.select_option(assigned)
            field = page.locator('#assigned_to')
            field.focus()
            field.fill('img')
            item = page.locator('.ac-dropdown .ac-name', has_text='onerror')
            pw.expect(item.first).to_be_visible()
            assert item.first.text_content() == XSS_USER
            page.wait_for_timeout(200)
            assert page.evaluate('window.__xss') is None
            assert page.locator('.ac-dropdown img').count() == 0
            browser.close()
    finally:
        with application.app_context():
            app_module.User.query.filter_by(username=XSS_USER).delete()
            app_module.db.session.commit()


def test_sidebar_nav_links_have_accessible_names(admin_client):
    """In the collapsed icon rail the visible labels are display:none, so every
    nav link needs its own accessible name (and a hover tooltip)."""
    html = admin_client.get('/').get_data(as_text=True)
    import re
    links = re.findall(r'<a class="nav-link[^"]*"[^>]*>', html)
    assert links
    for tag in links:
        assert 'aria-label="' in tag and 'title="' in tag, tag


def test_photo_lightbox_has_no_empty_src(application, admin_client):
    """An <img src=""> re-requests the current page as an image."""
    with application.app_context():
        laptop = app_module.Laptop(screen_size='14', ram='8', processor='i5', hard_disk='256',
                                   model='QA', vendor='QA', asset_tag='QA-LB-1', status='In Stock')
        app_module.db.session.add(laptop)
        app_module.db.session.commit()
        laptop_id = laptop.id
    try:
        html = admin_client.get(f'/assets/laptops/view/{laptop_id}').get_data(as_text=True)
        assert 'id="photo-lightbox-image"' in html
        assert 'src=""' not in html
    finally:
        with application.app_context():
            app_module.Laptop.query.filter_by(id=laptop_id).delete()
            app_module.db.session.commit()


@pytest.mark.parametrize('path, marker', [
    ('/audit', 'name="date_from"'),
    ('/audit', 'name="date_to"'),
    ('/audit', 'name="action"'),
    ('/logs', 'id="log-lines"'),
])
def test_filter_inputs_have_labels(admin_client, path, marker):
    import re
    html = admin_client.get(path).get_data(as_text=True)
    tag = re.search(r'<(?:input|select)[^>]*' + re.escape(marker) + r'[^>]*>', html).group(0)
    field_id = re.search(r'\bid="([^"]+)"', tag)
    labelled = 'aria-label="' in tag or (field_id and f'for="{field_id.group(1)}"' in html)
    assert labelled, tag


@pytest.mark.parametrize('path', ['/free', '/users', '/reports', '/roles'])
def test_tables_do_not_scroll_sideways_on_phones(admin_client, path):
    """Data tables restack into labelled records instead of a sideways scroll."""
    with pw.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except pw.Error as exc:
            pytest.skip(f'Install Chromium with playwright install chromium: {exc}')
        page = browser.new_page(viewport={'width': 390, 'height': 844})
        page.route('**/*', _serve_with_csp(admin_client))
        page.goto('http://localhost' + path)
        page.wait_for_load_state('load')
        page.wait_for_timeout(200)
        scrolling = page.evaluate("""() => [...document.querySelectorAll('.table-wrap')]
            .filter(w => w.offsetParent && w.scrollWidth > w.clientWidth + 2).length""")
        assert scrolling == 0
        browser.close()

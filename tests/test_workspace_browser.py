"""Optional Chromium checks. Install requirements-dev.txt and playwright chromium."""
from datetime import datetime, timezone
from urllib.parse import urlparse
import pytest

pw = pytest.importorskip('playwright.sync_api')


@pytest.fixture
def workspace_browser(admin_client):
    with pw.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except pw.Error as exc:
            pytest.skip(f'Install Chromium with playwright install chromium: {exc}')
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def serve(route):
            url = urlparse(route.request.url)
            if url.netloc != 'localhost':
                route.fulfill(status=200, body='')
                return
            response = admin_client.get(url.path + ('?' + url.query if url.query else ''))
            route.fulfill(status=response.status_code, body=response.data,
                          content_type=response.content_type)
        page.route('**/*', serve)
        yield page, errors
        assert not errors
        browser.close()


def test_quick_nav_keyboard_search_and_focus_return(workspace_browser):
    page, _ = workspace_browser
    page.goto('http://localhost/')
    page.locator('#quick-nav-open').focus()
    page.keyboard.press('Control+k')
    pw.expect(page.locator('#quick-nav')).to_be_visible()
    pw.expect(page.locator('#quick-nav-search')).to_be_focused()
    page.locator('#quick-nav-search').fill('no-such-page')
    pw.expect(page.locator('.quick-nav-empty')).to_be_visible()
    page.locator('#quick-nav-search').fill('Security')
    pw.expect(page.locator('.quick-nav-result')).to_have_count(1)
    page.keyboard.press('ArrowDown')
    pw.expect(page.locator('.quick-nav-result')).to_be_focused()
    page.keyboard.press('Escape')
    pw.expect(page.locator('#quick-nav')).not_to_be_visible()
    pw.expect(page.locator('#quick-nav-open')).to_be_focused()


def test_density_persists_and_mobile_nav_closes_with_escape(workspace_browser):
    page, _ = workspace_browser
    page.goto('http://localhost/')
    page.locator('#density-toggle').click()
    page.reload()
    pw.expect(page.locator('html')).to_have_attribute('data-density', 'compact')
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#mobile-nav-toggle').click()
    pw.expect(page.locator('#mobile-nav-toggle')).to_have_attribute('aria-expanded', 'true')
    page.keyboard.press('Escape')
    pw.expect(page.locator('#mobile-nav-toggle')).to_have_attribute('aria-expanded', 'false')
    pw.expect(page.locator('#mobile-nav-toggle')).to_be_focused()


def test_editor_responsive_grid_and_unsaved_change_warning(workspace_browser):
    page, _ = workspace_browser
    page.goto('http://localhost/assets/laptops/add')
    grid = page.locator('.editor-grid')
    assert len(grid.evaluate('el => getComputedStyle(el).gridTemplateColumns').split()) == 2
    page.locator('#vendor').fill('Unsaved browser test')
    pw.expect(page.locator('[data-editor-state]')).to_have_text('Unsaved changes')
    dialogs = []
    def dismiss(dialog):
        dialogs.append(dialog.type)
        dialog.dismiss()
    page.on('dialog', dismiss)
    page.get_by_role('link', name='Cancel', exact=True).click()
    assert dialogs == ['beforeunload']
    assert page.url.endswith('/add')
    page.locator('#vendor').fill('')
    pw.expect(page.locator('[data-editor-state]')).to_have_text('Changes are saved only when you select Save.')
    page.set_viewport_size({'width': 390, 'height': 844})
    assert len(grid.evaluate('el => getComputedStyle(el).gridTemplateColumns').split()) == 1
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.parametrize('logout_trigger', ['main_timeout', 'warning_countdown'])
def test_dirty_editor_cannot_cancel_inactivity_logout(
        workspace_browser, admin_client, monkeypatch, logout_trigger):
    import app as app_module

    monkeypatch.setattr(app_module, 'get_autologout_minutes', lambda: 1)
    page, _ = workspace_browser
    page.clock.install()
    page.goto('http://localhost/assets/laptops/add')
    page.locator('#vendor').click()
    page.locator('#vendor').fill('Unsaved inactivity regression')
    pw.expect(page.locator('[data-editor-state]')).to_have_text('Unsaved changes')

    dialogs = []
    logout_requests = []

    def cancel_navigation(dialog):
        dialogs.append(dialog.type)
        dialog.dismiss()

    page.on('dialog', cancel_navigation)
    page.on('request', lambda request: logout_requests.append(request.url)
            if urlparse(request.url).path == '/logout' else None)

    if logout_trigger == 'warning_countdown':
        page.clock.run_for(30_000)
        pw.expect(page.locator('#autologout-overlay')).to_have_class('autologout-overlay show')
        # Advance wall time without firing the main timeout: the next countdown
        # tick must independently enforce logout, even after a suspended clock.
        page.clock.set_system_time(datetime.fromtimestamp(
            page.evaluate('Date.now() + 30_000') / 1000, tz=timezone.utc))
        page.clock.run_for(500)
    else:
        # The main deadline must also work when the warning UI is unavailable.
        page.evaluate("document.getElementById('autologout-overlay').remove()")
        page.clock.run_for(60_000)

    pw.expect(page).to_have_url('http://localhost/logout')
    assert dialogs == [], 'Security logout must not offer a cancellable beforeunload dialog'
    assert logout_requests == ['http://localhost/logout']
    with admin_client.session_transaction() as session:
        assert 'user_id' not in session

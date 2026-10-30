"""Global asset search UI inside the quick-navigation dialog.

Browser-level coverage runs when Playwright + Chromium are available (same
pattern as tests/test_workspace_browser.py). Server-side markup/wiring tests
run unconditionally as a fallback so the feature is still guarded on hosts
without a browser.
"""
import re
import time
from urllib.parse import urlparse

import pytest

import app as app_module
from app import Laptop, db

try:
    from playwright import sync_api as pw
    HAS_PLAYWRIGHT = True
except ImportError:  # pragma: no cover - environment-dependent
    pw = None
    HAS_PLAYWRIGHT = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_ui_laptop(application):
    """One laptop with a distinctive vendor/tag so queries only match it."""
    with application.app_context():
        row = Laptop(asset_tag="LT-UI-99", vendor="AcmeUI", model="ProBook UI",
                     processor="i7", ram="16GB", hard_disk="512GB",
                     screen_size="14", assigned_to="free", status="In Stock")
        db.session.add(row)
        db.session.commit()
        row_id = row.id
    yield row_id
    with application.app_context():
        Laptop.query.filter_by(id=row_id).delete()
        db.session.commit()


@pytest.fixture
def search_browser(admin_client):
    """Playwright page served by the Flask test client, like workspace_browser."""
    if not HAS_PLAYWRIGHT:  # pragma: no cover - environment-dependent
        pytest.skip('playwright not installed')
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


def _open_quick_nav(page):
    page.goto('http://localhost/')
    page.locator('#quick-nav-open').click()
    pw.expect(page.locator('#quick-nav')).to_be_visible()


# ---------------------------------------------------------------------------
# Always-on markup / wiring tests (no browser required)
# ---------------------------------------------------------------------------

class TestSearchUiMarkup:
    def test_dialog_contains_asset_search_container(self, admin_client):
        html = admin_client.get('/').get_data(as_text=True)
        assert 'id="quick-nav-assets"' in html
        assert 'id="quick-nav-search"' in html

    def test_workspace_js_wires_asset_search(self, client):
        js = client.get('/static/workspace.js').get_data(as_text=True)
        # Live fetch against the session endpoint (CSP connect-src 'self').
        assert "fetch('/search?q=" in js
        # Debounced (~200 ms) rather than per-keystroke.
        assert 'ASSET_SEARCH_DEBOUNCE_MS = 200' in js
        assert re.search(r'setTimeout\(.*ASSET_SEARCH_DEBOUNCE_MS\)', js)
        # Empty-state copy required by the spec.
        assert 'No matching assets' in js
        # Result rows use a distinct class from page rows.
        assert 'quick-nav-asset-result' in js


# ---------------------------------------------------------------------------
# Browser tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason='playwright not installed')
class TestAssetSearchBrowser:
    def test_search_input_lists_matching_assets_and_keeps_nav(self,
                                                             search_browser,
                                                             seeded_ui_laptop):
        page, _ = search_browser
        _open_quick_nav(page)
        pw.expect(page.locator('#quick-nav-search')).to_be_focused()
        # Existing quick-nav page links remain available with an empty query.
        pw.expect(page.locator('.quick-nav-result', has_text='Dashboard').first).to_be_visible()
        page.locator('#quick-nav-search').fill('AcmeUI')
        results = page.locator('.quick-nav-asset-result')
        pw.expect(results).to_have_count(1)
        first = results.first
        text = first.inner_text()
        assert 'LT-UI-99' in text, 'row must show the asset tag'
        assert 'laptop' in text.lower(), 'row must show the asset type label'
        assert 'ProBook UI' in text, 'row must show the title'
        assert 'AcmeUI' in text, 'row must show the subtitle'
        assert first.get_attribute('href').endswith(
            f'/assets/laptops/view/{seeded_ui_laptop}')
        # Esc still closes the dialog (once focus leaves the search input —
        # Chromium clears a focused type=search input on Escape instead).
        page.keyboard.press('ArrowDown')
        pw.expect(first).to_be_focused()
        page.keyboard.press('Escape')
        pw.expect(page.locator('#quick-nav')).not_to_be_visible()

    def test_clicking_result_navigates_to_asset_detail(self, search_browser,
                                                       seeded_ui_laptop):
        page, _ = search_browser
        _open_quick_nav(page)
        page.locator('#quick-nav-search').fill('LT-UI-99')
        result = page.locator('.quick-nav-asset-result').first
        pw.expect(result).to_be_visible()
        result.click()
        pw.expect(page).to_have_url(
            re.compile(rf'/assets/laptops/view/{seeded_ui_laptop}$'))

    def test_arrow_and_enter_open_selected_asset(self, search_browser,
                                                 seeded_ui_laptop):
        page, _ = search_browser
        _open_quick_nav(page)
        # Matches no nav page, so the first selectable link is the asset row.
        page.locator('#quick-nav-search').fill('AcmeUI')
        result = page.locator('.quick-nav-asset-result').first
        pw.expect(result).to_be_visible()
        page.keyboard.press('ArrowDown')
        pw.expect(result).to_be_focused()
        page.keyboard.press('Enter')
        pw.expect(page).to_have_url(
            re.compile(rf'/assets/laptops/view/{seeded_ui_laptop}$'))

    def test_short_query_shows_hint_and_never_fetches(self, search_browser,
                                                      seeded_ui_laptop):
        page, _ = search_browser
        _open_quick_nav(page)
        search_requests = []
        page.on('request', lambda r: search_requests.append(r.url)
                if '/search' in r.url else None)
        page.locator('#quick-nav-search').fill('a')
        hint = page.locator('.quick-nav-assets-hint')
        pw.expect(hint).to_be_visible()
        assert '2' in hint.inner_text()
        # Longer than the debounce window; no fetch may have been issued.
        time.sleep(0.6)
        assert search_requests == [], search_requests

    def test_no_matching_assets_state(self, search_browser, seeded_ui_laptop):
        page, _ = search_browser
        _open_quick_nav(page)
        page.locator('#quick-nav-search').fill('zzz-no-such-asset-xyz')
        empty = page.locator('.quick-nav-assets-empty')
        pw.expect(empty).to_be_visible()
        assert 'No matching assets' in empty.inner_text()

    def test_debounce_coalesces_rapid_keystrokes(self, search_browser,
                                                 seeded_ui_laptop):
        page, _ = search_browser
        _open_quick_nav(page)
        search_requests = []
        page.on('request', lambda r: search_requests.append(r.url)
                if '/search' in r.url else None)
        page.locator('#quick-nav-search').press_sequentially('AcmeUI', delay=20)
        pw.expect(page.locator('.quick-nav-asset-result')).to_have_count(1)
        time.sleep(0.5)
        assert len(search_requests) == 1, search_requests

    def test_loading_state_while_fetch_pending(self, search_browser,
                                               seeded_ui_laptop):
        page, _ = search_browser
        _open_quick_nav(page)

        def hold_search(route):
            # Never fulfil: the fetch stays pending so the loading row remains.
            pass

        page.route('**/search*', hold_search)
        page.locator('#quick-nav-search').fill('AcmeUI')
        loading = page.locator('.quick-nav-assets-loading')
        pw.expect(loading).to_be_visible()
        assert 'Searching' in loading.inner_text()

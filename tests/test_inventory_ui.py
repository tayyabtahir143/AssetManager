"""Inventory contracts exercised in Chromium; database fixture is SQLite memory only."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import render_template, session
playwright_api = pytest.importorskip('playwright.sync_api')
expect = playwright_api.expect
sync_playwright = playwright_api.sync_playwright

import app as app_module

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inventory_browser(application):
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except playwright_api.Error as exc:
            pytest.skip(f'Install Chromium with playwright install chromium: {exc}')
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def render(asset_type="laptops", bulk=True, query="", pages=1, empty=False, readonly=False):
            definition = app_module.ASSET_DEFS[asset_type]
            items = []
            for index, tag in enumerate([] if empty else ["UI-Z10", "UI-A2"], 1):
                fields: dict = {name: "" for name, _, _ in definition["fields"]}
                fields.update(id=index, asset_tag=tag, status="In Stock", wired=True, wireless=False)
                items.append(SimpleNamespace(**fields))
            with application.test_request_context():
                admin = app_module.User.query.filter_by(username="admin").first()
                assert admin is not None
                session["user_id"] = admin.id
                return render_template(
                    "list.html", user=admin, app_admin=True, asset_type=asset_type,
                    definition=definition, asset_title=definition["label"], items=items,
                    asset_perms=SimpleNamespace(can_add=not readonly, can_delete=not readonly, can_bulk_delete=bulk),
                    query=query, status_filter="all", import_headers=[], page=1,
                    total_pages=pages, total_items=len(items),
                )

        state = {"html": render()}

        def serve(route):
            from urllib.parse import urlparse
            path = urlparse(route.request.url).path
            if path.startswith("/static/"):
                file = ROOT / path.lstrip("/")
                if file.is_file():
                    route.fulfill(path=str(file))
                    return
            if path.startswith("/assets/") and not path.endswith("/page"):
                route.fulfill(body=state["html"], content_type="text/html")
            else:
                route.fulfill(status=404, body="not found")

        page.route("**/*", serve)

        def open_inventory(**kwargs):
            state["html"] = render(**kwargs)
            page.goto("http://inventory.test/assets/" + kwargs.get("asset_type", "laptops"))
            return page

        yield open_inventory, page, errors
        browser.close()


def test_inventory_readable_toolbar_and_labels(inventory_browser):
    open_inventory, page, errors = inventory_browser
    open_inventory()
    expect(page.get_by_label("Search inventory", exact=True)).to_be_visible()
    expect(page.get_by_label("Filter by status", exact=True)).to_be_visible()
    expect(page.get_by_label("Excel file", exact=True)).to_be_attached()
    expect(page.get_by_label("Select all loaded assets", exact=True)).to_be_attached()
    assert page.locator(".list-table").evaluate("el => getComputedStyle(el).tableLayout") == "fixed"
    assert page.locator(".table-wrap").evaluate("el => el.scrollWidth <= el.clientWidth + 1")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors


@pytest.mark.parametrize('width', [1920, 1440, 1280, 1024, 768, 390])
def test_inventory_fits_without_sideways_scrolling(inventory_browser, width):
    open_inventory, page, errors = inventory_browser
    page.set_viewport_size({'width': width, 'height': 1000})
    open_inventory()
    page.locator('tbody tr').first.locator('td').nth(3).evaluate(
        "el => el.textContent = 'LongVendorAndModelWithoutSpaces'.repeat(5)")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('.table-wrap').evaluate('el => el.scrollWidth <= el.clientWidth + 1')
    actions = page.locator('tbody tr').first.locator('.col-act')
    for button in actions.locator('a, button').all():
        box = button.bounding_box()
        assert box is not None and box['x'] >= 0 and box['x'] + box['width'] <= width
    if width >= 1920:
        main = page.locator('main').bounding_box()
        assert main['x'] + main['width'] >= width - 1
    if width <= 900:
        expect(page.locator('tbody tr').first.locator('td[data-label="Asset Tag"]')).to_be_visible()
    assert not errors


@pytest.mark.parametrize("bulk", [True, False])
def test_keyboard_sort_uses_real_cell_index(inventory_browser, bulk):
    open_inventory, page, errors = inventory_browser
    open_inventory(bulk=bulk)
    header = page.locator('th[data-field="asset_tag"]')
    button = header.get_by_role("button", name="Asset Tag", exact=True)
    expect(button).to_be_visible()
    button.focus()
    page.keyboard.press("Enter")
    expect(header).to_have_attribute("aria-sort", "ascending")
    expect(page.locator("tbody tr").first).to_contain_text("UI-A2")
    page.keyboard.press("Space")
    expect(header).to_have_attribute("aria-sort", "descending")
    expect(page.locator("tbody tr").first).to_contain_text("UI-Z10")
    assert int(header.get_attribute("data-sort-col")) == (2 if bulk else 1)
    assert not errors


def test_columns_persist_per_type_and_reset(inventory_browser):
    open_inventory, page, errors = inventory_browser
    open_inventory()
    page.get_by_text("Columns", exact=True).click()
    choice = page.get_by_label("Asset Tag", exact=True)
    expect(choice).to_be_checked()
    choice.uncheck()
    expect(page.locator('th[data-field="asset_tag"]')).to_be_hidden()
    expect(page.locator("tbody tr").first.locator("td").nth(2)).to_be_hidden()
    page.reload()
    expect(page.locator('th[data-field="asset_tag"]')).to_be_hidden()
    open_inventory(asset_type="screens")
    expect(page.locator('th[data-field="asset_tag"]')).to_be_visible()
    open_inventory()
    expect(page.locator('th[data-field="asset_tag"]')).to_be_hidden()
    page.get_by_text("Columns", exact=True).click()
    page.get_by_role("button", name="Reset columns").click()
    expect(page.locator('th[data-field="asset_tag"]')).to_be_visible()
    page.reload()
    expect(page.locator('th[data-field="asset_tag"]')).to_be_visible()
    assert not errors


def test_columns_tolerate_broken_or_blocked_storage(inventory_browser):
    open_inventory, page, errors = inventory_browser
    open_inventory()
    page.evaluate("localStorage.setItem('inventory-columns:laptops', '{broken')")
    page.reload()
    expect(page.locator('th[data-field="asset_tag"]')).to_be_visible()
    page.add_init_script("Storage.prototype.setItem = () => { throw new Error('blocked'); };")
    page.reload()
    page.get_by_text("Columns", exact=True).click()
    page.get_by_label("Asset Tag", exact=True).uncheck()
    expect(page.locator('th[data-field="asset_tag"]')).to_be_hidden()
    assert not errors


@pytest.mark.parametrize("failure", ["network", "http", "json", "shape"])
def test_load_more_recovers_and_preserves_row_contracts(inventory_browser, failure):
    open_inventory, page, errors = inventory_browser
    open_inventory(pages=2)
    requests = []

    def next_page(route):
        requests.append(route.request.url)
        if len(requests) == 1:
            if failure == "network":
                route.abort()
            elif failure == "http":
                route.fulfill(status=503, body="offline")
            elif failure == "json":
                route.fulfill(content_type="text/html", body="login required")
            else:
                route.fulfill(json={"rows": [], "page": 1, "has_more": True})
            return
        route.fulfill(json={"rows": [{"id": 3, "fields": {"asset_tag": "UI-012", "status": "Assigned"}}], "page": 2, "has_more": False})

    page.route("**/assets/laptops/page?*", next_page)
    page.get_by_text("Columns", exact=True).click()
    page.get_by_label("Vendor", exact=True).uncheck()
    page.get_by_text("Columns", exact=True).click()
    page.locator('th[data-field="asset_tag"] button').click()
    page.get_by_role("button", name="Bulk Delete", exact=True).click()
    page.get_by_label("Select all loaded assets", exact=True).check()
    page.get_by_role("button", name="Load more", exact=True).click()
    expect(page.locator("#infinite-status")).to_contain_text("Could not load")
    expect(page.get_by_role("button", name="Retry loading")).to_be_enabled()
    page.get_by_role("button", name="Retry loading").click()
    expect(page.locator("tbody tr")).to_have_count(3)
    expect(page.locator("tbody tr").first).to_contain_text("UI-012")
    row = page.locator("tbody tr").filter(has_text="UI-012")
    expect(row.locator(".asset-checkbox")).to_be_checked()
    expect(row.locator("td").nth(3)).to_be_hidden()
    expect(row.locator(".badge")).to_have_text("Assigned")
    delete = row.get_by_role("button", name="Delete", exact=True)
    assert delete.evaluate("el => el.form.querySelector('[name=csrf_token]').value")
    assert delete.get_attribute("formaction") == "/assets/laptops/delete/3"
    assert page.locator("form form").count() == 0
    expect(page.locator("#infinite-status")).to_have_text("All items loaded.")
    expect(page.locator("#load-more-assets")).to_be_hidden()
    assert len(requests) == 2
    assert not errors


def test_search_query_is_serialized_safely(inventory_browser):
    open_inventory, page, errors = inventory_browser
    query = '\\"</script><script>window.inventoryInjected=true</script>\n&'
    open_inventory(query=query, pages=2)
    assert page.evaluate("window.inventoryInjected") is None
    assert not errors
    requests = []

    def next_page(route):
        requests.append(route.request.url)
        route.fulfill(json={"rows": [], "page": 2, "has_more": False})

    page.route("**/assets/laptops/page?*", next_page)
    page.get_by_role("button", name="Load more", exact=True).click()
    expect(page.locator("#infinite-status")).to_have_text("All items loaded.")
    from urllib.parse import parse_qs, urlparse
    assert parse_qs(urlparse(requests[0]).query)["q"] == [query]
    assert not errors


@pytest.mark.parametrize("bulk,readonly", [(True, False), (False, False), (False, True)])
def test_empty_inventory_spans_actual_columns(inventory_browser, bulk, readonly):
    open_inventory, page, errors = inventory_browser
    open_inventory(bulk=bulk, readonly=readonly, empty=True)
    cell = page.get_by_role("cell", name="No items found.")
    expect(cell).to_be_visible()
    assert int(cell.get_attribute("colspan")) == page.locator("thead th").count()
    assert not errors


def test_appended_delete_posts_csrf_without_database_write(inventory_browser):
    open_inventory, page, errors = inventory_browser
    open_inventory(pages=2, bulk=False)
    page.route("**/assets/laptops/page?*", lambda route: route.fulfill(json={
        "rows": [{"id": 3, "fields": {"asset_tag": "UI-POST"}}], "page": 2, "has_more": False,
    }))
    page.get_by_role("button", name="Load more", exact=True).click()
    expect(page.locator("tbody tr")).to_have_count(3)
    token = page.locator('#bulk-delete-form [name="csrf_token"]').input_value()
    posts = []

    def capture_delete(route):
        posts.append(route.request)
        route.fulfill(status=200, body="Captured without database access")

    page.route("**/assets/laptops/delete/3", capture_delete)
    page.on("dialog", lambda dialog: dialog.accept())
    page.locator("tbody tr").filter(has_text="UI-POST").get_by_role("button", name="Delete", exact=True).click()
    page.wait_for_url("**/assets/laptops/delete/3")
    from urllib.parse import parse_qs
    assert posts[0].method == "POST"
    assert parse_qs(posts[0].post_data)["csrf_token"] == [token]
    assert not errors


def test_opt_in_scroll_loading_and_bulk_toggle_include_new_rows(inventory_browser):
    open_inventory, page, errors = inventory_browser
    open_inventory(pages=2)
    page.route("**/assets/laptops/page?*", lambda route: route.fulfill(json={
        "rows": [{"id": 3, "fields": {"asset_tag": "UI-SCROLL"}}], "page": 2, "has_more": False,
    }))
    page.get_by_label("Automatically load on scroll").check()
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight); window.dispatchEvent(new Event('scroll'))")
    expect(page.locator("tbody tr")).to_have_count(3)
    box = page.locator("tbody tr").filter(has_text="UI-SCROLL").locator(".asset-checkbox")
    expect(box).to_be_hidden()
    page.get_by_role("button", name="Bulk Delete", exact=True).click()
    expect(box).to_be_visible()
    page.get_by_role("button", name="Bulk Delete", exact=True).click()
    expect(box).to_be_hidden()
    assert not errors

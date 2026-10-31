"""Design refresh features: asset-type icon picker, macro-driven dashboard
tiles, and the six colour schemes with a shell picker."""

from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMES = ["amber", "indigo", "emerald", "rose", "ocean", "slate"]


def _create_type(admin_client, label, key, icon=""):
    """POST a minimal asset type through the real add route (302 on success)."""
    data = {
        "label": label,
        "key": key,
        "icon": icon,
        "field_name_1": "model",
        "field_label_1": "Model",
        "field_type_1": "text",
    }
    resp = admin_client.post("/asset-types/add", data=data)
    assert resp.status_code == 302


def _type_id(application, key):
    import app as app_module

    with application.app_context():
        asset_type = app_module.AssetType.query.filter_by(key=key).first()
        assert asset_type is not None, f"no asset type with key {key}"
        return asset_type.id


class TestAssetTypeIconPickerAdd:
    def test_add_form_has_auto_option_and_whitelisted_radios(self, admin_client):
        html = admin_client.get("/asset-types/add").data.decode("utf-8")
        assert 'class="icon-picker"' in html
        # Auto choice first, selected by default, empty value.
        assert 'name="icon" value="" checked' in html
        assert "Auto — pick by name" in html
        # Whitelisted choices render as radios (ICON_CHOICES has 18 entries).
        assert 'name="icon" value="printer"' in html
        assert 'name="icon" value="box"' in html
        assert html.count('name="icon"') == 1 + 18
        # Each choice paints a live stencil SVG.
        assert html.count('viewBox="0 0 24 24"') >= 18


class TestAssetTypeIconPickerEdit:
    def test_edit_form_checks_current_icon(self, admin_client, application):
        _create_type(admin_client, "Boxes Ui", "design_ui_boxes", icon="box")
        type_id = _type_id(application, "design_ui_boxes")
        html = admin_client.get(f"/asset-types/edit/{type_id}").data.decode("utf-8")
        assert 'class="icon-picker"' in html
        assert 'name="icon" value="box" checked' in html
        assert 'name="icon" value="" checked' not in html

    def test_edit_form_auto_selected_when_no_icon(self, admin_client, application):
        _create_type(admin_client, "Cables Ui", "design_ui_cables", icon="")
        type_id = _type_id(application, "design_ui_cables")
        html = admin_client.get(f"/asset-types/edit/{type_id}").data.decode("utf-8")
        assert 'name="icon" value="" checked' in html


class TestDashboardTilesUseSharedMacro:
    def test_rendered_tiles_carry_data_icon_and_keep_nav_attrs(self, admin_client):
        html = admin_client.get("/").data.decode("utf-8")
        assert 'data-icon="' in html
        assert 'data-category-label="' in html
        assert 'data-quick-nav="' in html
        assert 'dashboard-category-glyph' in html

    def test_template_imports_macro_and_drops_inline_svg_chain(self):
        source = (REPO_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        assert 'from "_icons.html" import asset_icon' in source
        assert "asset_icon(asset.icon, asset.label, 22)" in source
        # The old inline heuristic chain is gone (its first condition marker).
        assert "'laptop' in gl" not in source


class TestSchemePickerInShell:
    def test_shell_renders_picker_and_server_default_scheme(self, admin_client):
        html = admin_client.get("/").data.decode("utf-8")
        # Server-side default so no-JS users get a themed page.
        assert '<html lang="en" data-scheme="amber">' in html
        assert 'data-scheme-picker' in html
        for scheme in SCHEMES[1:]:
            assert f'data-scheme-value="{scheme}"' in html
        for scheme in SCHEMES:
            assert f'aria-label="{scheme.capitalize()} scheme"' in html

    def test_workspace_js_persists_scheme_preference(self):
        js = (REPO_ROOT / "static" / "workspace.js").read_text(encoding="utf-8")
        assert "assetmanager-scheme" in js

    def test_base_head_script_restores_saved_scheme(self):
        source = (REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        assert "assetmanager-scheme" in source
        assert 'data-scheme="amber"' in source


class TestColourSchemeTokens:
    def test_foundation_css_defines_all_five_new_schemes_for_both_shifts(self):
        css = (REPO_ROOT / "static" / "foundation.css").read_text(encoding="utf-8")
        for scheme in SCHEMES[1:]:
            assert f'[data-scheme="{scheme}"]' in css
            assert f'[data-scheme="{scheme}"][data-theme="light"]' in css
        # Each scheme redefines the accent family, not new token names.
        for token in ("--accent:", "--accent-2:", "--accent-dim:", "--on-accent:",
                      "--ring:", "--warning:"):
            assert css.count(token) >= len(SCHEMES), token


class TestSemanticStatusTokens:
    """The six schemes tune the semantic status family (green/blue/warning/
    danger/muted) for both shifts, and surfaces consume the tokens instead of
    hardcoded stock status hexes."""

    SEMANTIC = ("--green", "--green-dim", "--blue", "--blue-dim",
                "--warning", "--warning-dim", "--danger", "--danger-dim",
                "--muted")

    @staticmethod
    def _scheme_blocks(css):
        import re

        blocks = {scheme: {"night": "", "light": ""} for scheme in SCHEMES}
        for match in re.finditer(
            r'\[data-scheme="([a-z]+)"\](?:\[data-theme="light"\])?\s*\{([^}]*)\}',
            css,
        ):
            scheme = match.group(1)
            if scheme not in blocks:
                continue
            shift = "light" if '[data-theme="light"]' in match.group(0) else "night"
            blocks[scheme][shift] = match.group(2)
        return blocks

    def test_every_scheme_tunes_all_semantic_tokens_in_both_shifts(self):
        css = (REPO_ROOT / "static" / "foundation.css").read_text(encoding="utf-8")
        blocks = self._scheme_blocks(css)
        for scheme in SCHEMES:
            for shift in ("night", "light"):
                body = blocks[scheme][shift]
                for token in self.SEMANTIC:
                    assert f"{token}:" in body, f"{scheme} {shift} is missing {token}"

    def test_status_palettes_are_distinct_across_schemes(self):
        import re

        css = (REPO_ROOT / "static" / "foundation.css").read_text(encoding="utf-8")
        blocks = self._scheme_blocks(css)
        for token in ("--green", "--blue", "--warning", "--danger", "--muted"):
            for shift in ("night", "light"):
                values = []
                for scheme in SCHEMES:
                    match = re.search(rf"{token}:\s*([^;]+);", blocks[scheme][shift])
                    assert match, f"{scheme} {shift} is missing {token}"
                    values.append(match.group(1).strip())
                assert len(set(values)) == len(SCHEMES), (
                    f"{token} {shift} values collide across schemes: {values}"
                )

    def test_warning_stays_in_the_amber_family_everywhere(self):
        """Warning means pending; in every tuned scheme it keeps the amber/
        yellow family instead of collapsing onto the accent hue (an indigo
        'warning' badge was exactly the reported bug). Amber is the identity
        scheme: its warning is the safety amber itself."""
        import re

        css = (REPO_ROOT / "static" / "foundation.css").read_text(encoding="utf-8")
        blocks = self._scheme_blocks(css)
        for scheme in SCHEMES:
            for shift in ("night", "light"):
                body = blocks[scheme][shift]
                warning = re.search(r"--warning:\s*(#[0-9a-fA-F]{6})", body)
                assert warning, f"{scheme} {shift} is missing --warning"
                for sibling in ("--green", "--blue", "--danger"):
                    other = re.search(rf"{sibling}:\s*(#[0-9a-fA-F]{{6}})", body)
                    assert other, f"{scheme} {shift} is missing {sibling}"
                    assert warning.group(1) != other.group(1), (
                        f"{scheme} {shift}: warning {warning.group(1)} collides "
                        f"with {sibling} {other.group(1)}"
                    )
                if scheme != "amber":
                    accent = re.search(r"--accent:\s*(#[0-9a-fA-F]{6})", body)
                    assert accent, f"{scheme} {shift} is missing --accent"
                    assert warning.group(1) != accent.group(1), (
                        f"{scheme} {shift}: warning {warning.group(1)} should "
                        f"not equal accent {accent.group(1)}"
                    )

    def test_inventory_css_has_no_hardcoded_status_hexes(self):
        css = (REPO_ROOT / "static" / "inventory.css").read_text(encoding="utf-8")
        for hex_value in ("#22c55e", "#3b82f6", "#ef4444", "#f59e0b",
                          "#10b981", "#818cf8", "#fb7185", "#4f46e5"):
            assert hex_value not in css, f"inventory.css hardcodes {hex_value}"

    def test_dashboard_charts_consume_semantic_tokens(self):
        source = (REPO_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        assert "tok('--green')" in source
        assert "tok('--blue')" in source
        assert "tok('--danger')" in source
        for hex_value in ("#22c55e", "#3b82f6", "#ef4444", "#f59e0b",
                          "#10b981", "#818cf8", "#fb7185", "#4f46e5"):
            assert hex_value not in source, f"index.html charts hardcode {hex_value}"


@pytest.fixture
def scheme_browser(admin_client):
    """Playwright page backed by the in-memory Flask test client."""
    import playwright.sync_api as pw

    with pw.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except pw.Error as exc:
            pytest.skip(f"Install Chromium with playwright install chromium: {exc}")
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            url = urlparse(route.request.url)
            if url.netloc != "localhost":
                route.fulfill(status=200, body="")
                return
            response = admin_client.get(url.path + ("?" + url.query if url.query else ""))
            route.fulfill(status=response.status_code, body=response.data,
                          content_type=response.content_type)

        page.route("**/*", serve)
        yield page, errors
        assert not errors
        browser.close()


def test_scheme_swatch_sets_and_persists_across_reload(scheme_browser):
    import playwright.sync_api as pw

    page, _ = scheme_browser
    page.goto("http://localhost/")
    pw.expect(page.locator("html")).to_have_attribute("data-scheme", "amber")
    page.locator('[data-scheme-value="ocean"]').click()
    pw.expect(page.locator("html")).to_have_attribute("data-scheme", "ocean")
    pw.expect(page.locator('[data-scheme-value="ocean"]')).to_have_attribute(
        "aria-pressed", "true")
    page.reload()
    pw.expect(page.locator("html")).to_have_attribute("data-scheme", "ocean")
    # Switch back and confirm the default scheme round-trips too.
    page.locator('[data-scheme-value="amber"]').click()
    pw.expect(page.locator("html")).to_have_attribute("data-scheme", "amber")

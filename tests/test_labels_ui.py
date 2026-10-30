"""UI contract tests for the printable asset labels page.

Covers the vendored QR library, per-label QR containers carrying absolute
asset URLs, the client-side QR generator (with double-invocation guard),
and preservation of the backend contract (label-tag element / tag text).
"""
import re
from pathlib import Path

import pytest

import app as app_module
from app import AssetItem, AssetType, Laptop, db

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_QR = REPO_ROOT / "static" / "vendor" / "qrcode.min.js"
VENDOR_LICENSE = REPO_ROOT / "static" / "vendor" / "qrcode-LICENSE.md"


@pytest.fixture
def seeded_laptops(application):
    with application.app_context():
        rows = [
            Laptop(asset_tag="LT-UI-1", vendor="Acme", model="ProBook X",
                   processor="i7", ram="16GB", hard_disk="512GB",
                   screen_size="14", assigned_to="free", status="In Stock"),
            Laptop(asset_tag="LT-UI-2", vendor="Globex", model="ThinkPad T",
                   processor="i5", ram="8GB", hard_disk="256GB",
                   screen_size="13", assigned_to="alice@example.com",
                   status="Assigned", dept="Engineering"),
        ]
        db.session.add_all(rows)
        db.session.commit()
        yield rows
        Laptop.query.delete()
        db.session.commit()


class TestLabelsQrUi:
    def test_page_loads_vendored_qr_library_not_cdn(self, admin_client, seeded_laptops):
        resp = admin_client.get("/labels/laptops?ids=1,2")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert 'src="/static/vendor/qrcode.min.js"' in html
        assert "cdn.jsdelivr.net" not in html

    def test_each_label_has_qr_container_with_absolute_url(self, admin_client, seeded_laptops):
        resp = admin_client.get("/labels/laptops?ids=1,2")
        html = resp.data.decode("utf-8")
        qr_divs = re.findall(r'<div class="label-qr"[^>]*data-url="([^"]+)"', html)
        assert len(qr_divs) == 2, f"expected one label-qr div per item, got {qr_divs}"
        for url in qr_divs:
            assert url.startswith("http://"), f"QR data-url must be absolute, got {url}"
            assert "/assets/laptops/view/" in url

    def test_qr_generator_inline_script_present_and_guarded(self, admin_client, seeded_laptops):
        resp = admin_client.get("/labels/laptops?ids=1,2")
        html = resp.data.decode("utf-8")
        assert "new QRCode(" in html, "inline QR generator should instantiate qrcodejs"
        assert "qrGenerated" in html, "generator must guard against double invocation"
        assert 'querySelectorAll(\'.label-qr\')' in html

    def test_label_tag_element_preserved_for_backend_contract(self, admin_client, seeded_laptops):
        resp = admin_client.get("/labels/laptops?ids=1,2")
        html = resp.data.decode("utf-8")
        assert "LT-UI-1" in html and "LT-UI-2" in html
        assert 'class="label-tag"' in html

    def test_print_controls_present(self, admin_client, seeded_laptops):
        resp = admin_client.get("/labels/laptops?ids=1,2")
        html = resp.data.decode("utf-8")
        assert "window.print()" in html
        assert "Back to dashboard" in html

    def test_custom_labels_page_has_qr_divs(self, admin_client, application):
        with application.app_context():
            asset_type = AssetType(key="cables", label="Cables", has_quantity=False)
            db.session.add(asset_type)
            db.session.commit()
            admin_role = app_module.Role.query.filter_by(name="admin").first()
            # Another suite (test_features_backend) may have left a
            # custom:cables permission row behind in this shared in-memory DB.
            perm = app_module.RolePermission.query.filter_by(
                role_id=admin_role.id, asset_type="custom:cables").first()
            created_perm = None
            if perm is None:
                created_perm = app_module.RolePermission(
                    role_id=admin_role.id, asset_type="custom:cables", can_read=True)
                db.session.add(created_perm)
                db.session.commit()
            else:
                perm.can_read = True
                db.session.commit()
            item = AssetItem(asset_type_id=asset_type.id,
                             data={"asset_tag": "CBL-77", "model": "HDMI 1m"})
            db.session.add(item)
            db.session.commit()
            try:
                resp = admin_client.get(f"/labels/custom/cables?ids={item.id}")
                assert resp.status_code == 200
                html = resp.data.decode("utf-8")
                assert 'class="label-qr"' in html
                assert "/custom/cables/view/" in html
                match = re.search(r'<div class="label-qr"[^>]*data-url="([^"]+)"', html)
                assert match and match.group(1).startswith("http://")
            finally:
                db.session.rollback()
                db.session.delete(item)
                db.session.delete(asset_type)
                if created_perm is not None:
                    db.session.delete(created_perm)
                db.session.commit()


class TestVendoredLibrary:
    def test_vendor_qr_file_exists_and_is_plausible_js(self):
        assert VENDOR_QR.exists(), f"missing {VENDOR_QR}"
        head = VENDOR_QR.read_text(encoding="utf-8", errors="replace")[:2000]
        assert len(head) > 500, "vendor file looks truncated"
        assert "QRCode" in head
        assert head.lstrip().startswith(("/*", "var QRCode"))

    def test_vendor_license_exists_and_mentions_mit(self):
        assert VENDOR_LICENSE.exists(), f"missing {VENDOR_LICENSE}"
        text = VENDOR_LICENSE.read_text(encoding="utf-8", errors="replace")
        assert "MIT" in text.upper()
        assert "Permission is hereby granted" in text


class TestLabelsQrBrowser:
    def test_qr_codes_render_in_browser(self, admin_client, seeded_laptops):
        """Optional end-to-end check: real browser paints a QR canvas per card."""
        sync_api = pytest.importorskip("playwright.sync_api")
        resp = admin_client.get("/labels/laptops?ids=1,2")
        html = resp.data.decode("utf-8")
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.route(
                    "**/static/vendor/qrcode.min.js",
                    lambda route: route.fulfill(path=str(VENDOR_QR)),
                )
                page.set_content("<base href='http://localhost/'>" + html,
                                 wait_until="load")
                # qrcodejs paints a canvas then swaps in a PNG <img> (the
                # visible element) and hides the canvas.
                page.wait_for_selector(".label-qr img", timeout=5000)
                assert page.locator(".label-qr img").count() == 2
                painted = page.evaluate(
                    "() => Array.from(document.querySelectorAll('.label-qr img'))"
                    ".every(img => { const c = document.createElement('canvas');"
                    " c.width = img.naturalWidth; c.height = img.naturalHeight;"
                    " const ctx = c.getContext('2d'); ctx.drawImage(img, 0, 0);"
                    " const d = ctx.getImageData(0, 0, c.width, c.height).data;"
                    " return d.some(v => v === 0) && d.some(v => v === 255); })"
                )
                assert painted, "each QR image should be painted black on white"
            finally:
                browser.close()

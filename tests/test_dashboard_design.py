"""Dashboard presentation regressions; runnable without Flask or a database."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from urllib.parse import urlencode

try:
    import jinja2
except ImportError:
    jinja2 = None

ROOT = Path(__file__).resolve().parents[1]


class DashboardDesignTests(unittest.TestCase):
    def test_category_search_has_accessible_feedback_and_progressive_enhancement(self):
        source = (ROOT / "templates/index.html").read_text()
        self.assertIn('for="dashboard-category-search"', source)
        self.assertIn('id="dashboard-category-search"', source)
        self.assertIn('data-category-label="{{ asset.label }}"', source)
        self.assertIn('id="dashboard-category-results"', source)
        self.assertIn('aria-live="polite"', source)
        self.assertIn('No asset types match your search.', source)
        self.assertIn("category.hidden = !matches", source)
        self.assertIn("search.addEventListener('input'", source)
        self.assertIn('id="dashboard-category-filter" hidden', source)

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_category_filter_execution(self):
        source = (ROOT / "templates/index.html").read_text()
        match = re.search(r"<script>\s*(.*?)</script>", source, re.S)
        assert match is not None
        script = match.group(1)
        harness = """
const assert = require('node:assert/strict');
const listeners = {};
const search = {value: '', addEventListener: (name, fn) => listeners[name] = fn};
const filter = {hidden: true}, results = {}, empty = {};
const categories = ['Laptops', 'Monitors', 'Network equipment'].map(label => ({dataset: {categoryLabel: label}}));
const ids = {'dashboard-category-search': search, 'dashboard-category-filter': filter,
             'dashboard-category-results': results, 'dashboard-category-no-match': empty};
global.document = {getElementById: id => ids[id], querySelectorAll: () => categories};
""" + script + """
assert.equal(filter.hidden, false);
assert.equal(results.textContent, '3 of 3 asset types');
search.value = '  LAP  '; listeners.input();
assert.deepEqual(categories.map(c => c.hidden), [false, true, true]);
assert.equal(results.textContent, '1 of 3 asset types');
assert.equal(empty.hidden, true);
search.value = 'does-not-exist'; listeners.input();
assert.equal(empty.hidden, false);
assert.equal(results.textContent, '0 of 3 asset types');
listeners.keydown({key: 'Escape', preventDefault: () => {}});
assert.equal(search.value, '');
assert.equal(categories.every(c => !c.hidden), true);
assert.equal(empty.hidden, true);
console.log('Category filtering, no-match feedback, and Escape reset passed');
"""
        result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_operations_dashboard_preserves_data_with_responsive_layout(self):
        source = (ROOT / "templates/index.html").read_text()
        self.assertRegex(source, r"<h1[^>]*>Inventory overview</h1>")
        self.assertNotIn("Asset Command Center", source)
        self.assertNotIn("hero-shell", source)
        self.assertNotIn("gradient(", source)
        self.assertIn("filename='dashboard.css'", source)
        for binding in ("{{ total_assets }}", "{{ total_assigned }}", "{{ total_available }}",
                        "{{ asset.count }}", "{{ asset.label }}", "{{ asset.url }}",
                        "{{ entry.action }}", "{{ entry.display_time or entry.created_at }}"):
            self.assertIn(binding, source)
        for condition in ("{% if total_assets > 0 %}", "{% for asset in assets %}",
                          "{% if dept_summary %}", "{% if recent_activity %}"):
            self.assertIn(condition, source)
        for endpoint in ("reports", "free_inventory", "user_assets", "audit_log"):
            self.assertIn("url_for('" + endpoint + "'", source)
        for chart in ("statusChart", "deptChart"):
            self.assertIn('id="' + chart + '"', source)
            self.assertIn("document.getElementById('" + chart + "')", source)
        self.assertIn("No readable asset types for your role.", source)
        self.assertIn("No activity yet", source)
        self.assertIn("No assets tracked yet", source)
        css = (ROOT / "static/dashboard.css").read_text()
        self.assertIn(".dashboard-chart-row", css)
        self.assertIn(".dashboard-activity-row", css)
        self.assertRegex(css, r"@media\s*\(max-width:\s*\d+px\)")
        self.assertIn("grid-template-columns: 1fr", css)
        self.assertIn("minmax(0, 1fr)", css)
        self.assertIn(":focus-visible", css)
        self.assertNotIn("gradient(", css)
        self.assertNotRegex(source, r'grid-template-columns:1fr 1fr')


@unittest.skipIf(jinja2 is None, "Jinja2 is not installed")
class DashboardRenderTests(unittest.TestCase):
    def render(self, **overrides):
        # Isolate the dashboard from shared-shell edits and all database access.
        assert jinja2 is not None
        env = jinja2.Environment(loader=jinja2.ChoiceLoader([
            jinja2.DictLoader({"base.html": "{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
            jinja2.FileSystemLoader(ROOT / "templates"),
        ]), autoescape=True)
        env.globals["url_for"] = lambda endpoint, **kw: "/" + endpoint + ("?" + urlencode(kw) if kw else "")
        context = dict(total_assets=0, total_assigned=0, total_available=0,
                       assets=[], dept_summary=[], recent_activity=[])
        context.update(overrides)
        return env.get_template("index.html").render(**context)

    def test_empty_dashboard_has_no_charts_or_division_by_zero(self):
        rendered = self.render()
        self.assertIn("No assets tracked yet", rendered)
        self.assertIn("No readable asset types for your role.", rendered)
        self.assertIn("No activity yet", rendered)
        self.assertNotIn('id="statusChart"', rendered)
        self.assertNotIn("chart.umd.min.js", rendered)
        self.assertNotIn("All assets are currently assigned", rendered)

    def test_populated_dashboard_keeps_counts_routes_and_escaped_activity(self):
        departments = [dict(dept="Engineering", assigned=3, available=1),
                       dict(dept="In Stock", assigned=0, available=2),
                       dict(dept="Broken", assigned=0, available=0),
                       dict(dept="Write Off", assigned=0, available=0)]
        rendered = self.render(total_assets=8, total_assigned=3, total_available=4,
                               assets=[dict(label="Laptops", count=7, url="/laptops")],
                               dept_summary=departments,
                               recent_activity=[dict(action="update_asset", username="<admin>",
                                                     display_time="Today", created_at="fallback")])
        self.assertIn('href="/laptops"', rendered)
        self.assertIn('dashboard-category-count">7 ', rendered)
        self.assertIn('>37<span', rendered)
        self.assertIn('width:75%;', rendered)
        self.assertIn('dept=in_stock&amp;asset=all&amp;status=in_stock', rendered)
        self.assertIn('dept=all&amp;asset=all&amp;status=broken', rendered)
        self.assertIn('dept=all&amp;asset=all&amp;status=write_off', rendered)
        self.assertIn('&lt;admin&gt;', rendered)
        self.assertIn('>Today</p>', rendered)
        self.assertIn('id="statusChart"', rendered)
        self.assertIn('id="deptChart"', rendered)
        self.assertIn('href="/audit_log"', rendered)
        self.assertNotIn('No assets tracked yet', rendered)

    def test_no_available_assets_uses_inventory_status(self):
        rendered = self.render(total_assets=2, total_assigned=2)
        self.assertIn("All assets are currently assigned or accounted for.", rendered)
        self.assertIn('>2 / 2 <span>assigned of total</span>', rendered)
        self.assertNotIn('Ready to allocate</h2>', rendered)


if __name__ == "__main__":
    unittest.main()

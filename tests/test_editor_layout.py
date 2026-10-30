"""Editor layout and read-only view database regression checks."""
from pathlib import Path
import pytest
import app as app_module
from sqlalchemy import inspect, select


@pytest.mark.parametrize('template', ['add.html', 'edit.html', 'custom_add.html', 'custom_edit.html'])
def test_editors_use_responsive_grid_and_explicit_save_bar(template):
    source = (Path(__file__).resolve().parents[1] / 'templates' / template).read_text()
    assert 'asset-editor' in source
    assert 'editor-actions' in source
    assert 'data-unsaved-form' in source
    assert 'csrf_token' in source


def test_view_refresh_keeps_asset_records_and_schema(application, admin_client):
    # Initialize existing application defaults before recording the baseline.
    admin_client.get('/')
    with application.app_context():
        def snapshot():
            schema = inspect(app_module.db.engine)
            columns = {table: [col['name'] for col in schema.get_columns(table)]
                       for table in schema.get_table_names()}
            assets = {name: [tuple(row) for row in app_module.db.session.execute(select(definition['model'].__table__)).all()]
                      for name, definition in app_module.ASSET_DEFS.items()}
            return columns, assets
        before = snapshot()
        for url in ['/', '/assets/laptops', '/assets/laptops/add', '/reports', '/users', '/settings/security']:
            assert admin_client.get(url).status_code == 200
        assert snapshot() == before

(() => {
  'use strict';
  const table = document.querySelector('.inventory-page .list-table');
  if (!table) return;
  const body = table.tBodies[0];
  const config = JSON.parse(document.getElementById('inventory-config').textContent);
  const headers = [...table.querySelectorAll('th[data-sort-col]')];
  const choices = [...document.querySelectorAll('[data-column-choice]')];
  const storageKey = `inventory-columns:${table.closest('[data-asset-type]').dataset.assetType}`;
  let hiddenFields = new Set();
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey));
    if (Array.isArray(stored)) hiddenFields = new Set(stored.filter(name => typeof name === 'string'));
  } catch (_) { /* Storage may be unavailable or contain stale preferences. */ }
  const applyColumns = () => {
    // Keep every field readable in the stacked narrow-screen layout, including
    // rows loaded later; preserve real table cells for sorting and selection.
    [...body.rows].forEach(row => {
      if (!row.querySelector('.col-idx')) return;
      [...table.tHead.rows[0].cells].forEach((header, index) => {
        if (row.cells[index]) row.cells[index].dataset.label = header.textContent.replace(/[↑↓]/g, '').trim() || 'Select';
      });
    });
    headers.filter(header => header.dataset.field).forEach(header => {
      const hidden = hiddenFields.has(header.dataset.field);
      header.hidden = hidden;
      [...body.rows].forEach(row => {
        if (row.querySelector('.col-idx') && row.cells[header.cellIndex]) row.cells[header.cellIndex].hidden = hidden;
      });
    });
    choices.forEach(choice => { choice.checked = !hiddenFields.has(choice.dataset.columnChoice); });
  };
  const saveColumns = () => {
    try { localStorage.setItem(storageKey, JSON.stringify([...hiddenFields])); } catch (_) { /* Keep the in-memory preference usable. */ }
    applyColumns();
  };
  choices.forEach(choice => choice.addEventListener('change', () => {
    if (choice.checked) hiddenFields.delete(choice.dataset.columnChoice);
    else hiddenFields.add(choice.dataset.columnChoice);
    saveColumns();
  }));
  document.getElementById('reset-inventory-columns').addEventListener('click', () => {
    hiddenFields.clear();
    saveColumns();
  });
  applyColumns();
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
  let sortHeader = null;
  let sortDirection = 1;
  const sortRows = () => {
    if (!sortHeader) return;
    const index = sortHeader.cellIndex;
    const rows = [...body.rows].filter(row => row.querySelector('.col-idx'));
    rows.sort((a, b) => collator.compare(a.cells[index].textContent.trim(), b.cells[index].textContent.trim()) * sortDirection);
    rows.forEach(row => body.appendChild(row));
  };
  headers.forEach(header => {
    header.querySelector('button').addEventListener('click', () => {
      sortDirection = sortHeader === header ? -sortDirection : 1;
      sortHeader = header;
      headers.forEach(other => {
        other.setAttribute('aria-sort', other === header ? (sortDirection === 1 ? 'ascending' : 'descending') : 'none');
        other.querySelector('.sort-arrow').textContent = other === header ? (sortDirection === 1 ? ' ↑' : ' ↓') : '';
      });
      sortRows();
    });
  });
  const status = document.getElementById('infinite-status');
  const loadButton = document.getElementById('load-more-assets');
  const autoLoad = document.getElementById('inventory-autoload');
  let currentPage = config.page;
  let hasMore = currentPage < config.totalPages;
  let loading = false;
  let failed = false;
  let rowNumber = body.querySelectorAll('.col-idx').length;

  const buildRow = data => {
    const row = document.createElement('tr');
    const selectAll = document.getElementById('select-all-assets');
    const bulkVisible = selectAll && selectAll.style.display !== 'none';
    if (config.canBulk) {
      const cell = row.insertCell();
      cell.className = 'col-chk';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.name = 'selected_ids';
      checkbox.value = data.id;
      checkbox.className = 'asset-checkbox bulk-toggle-asset';
      checkbox.setAttribute('aria-label', `Select asset ${data.id}`);
      checkbox.style.display = bulkVisible ? '' : 'none';
      checkbox.checked = Boolean(bulkVisible && selectAll.checked);
      cell.appendChild(checkbox);
    }
    const index = row.insertCell();
    index.className = 'col-idx';
    index.textContent = ++rowNumber;
    config.fields.forEach(([name]) => {
      const cell = row.insertCell();
      const value = String(data.fields[name] ?? '-');
      cell.title = value;
      if (name === 'status') {
        const badge = document.createElement('span');
        const colors = { Assigned: 'badge-blue', 'In Stock': 'badge-green', Broken: 'badge-danger', 'Write Off': 'badge-warn' };
        badge.className = `badge ${colors[value] || ''}`;
        badge.textContent = value || '-';
        cell.appendChild(badge);
      } else cell.textContent = value || '-';
    });
    if (config.canAdd || config.canDelete) {
      const cell = row.insertCell();
      cell.className = 'col-act';
      if (config.canAdd) {
        ['View', 'Edit', 'Copy'].forEach(action => {
          const link = document.createElement('a');
          link.className = 'button secondary';
          link.href = `${config.assetBase}/${action.toLowerCase()}/${data.id}`;
          link.textContent = action;
          cell.appendChild(link);
        });
      }
      if (config.canDelete) {
        // Use the existing CSRF-protected form, never nest a tokenless form.
        const button = document.createElement('button');
        button.type = 'submit';
        button.className = 'button secondary';
        button.setAttribute('formaction', `${config.assetBase}/delete/${data.id}`);
        button.setAttribute('formmethod', 'post');
        button.textContent = 'Delete';
        button.onclick = () => window.confirm('Delete this item?');
        cell.appendChild(button);
      }
    }
    return row;
  };

  const renderLoadingState = () => {
    loadButton.hidden = !hasMore;
    loadButton.disabled = loading;
    loadButton.textContent = loading ? 'Loading…' : (failed ? 'Retry loading' : 'Load more');
    table.setAttribute('aria-busy', String(loading));
    status.textContent = loading ? 'Loading more items…' : failed ? 'Could not load more items. Check your connection or sign in again, then retry.' : hasMore ? 'More items available.' : 'All items loaded.';
  };
  const loadMore = async () => {
    if (loading || !hasMore) return;
    loading = true;
    failed = false;
    renderLoadingState();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    try {
      const params = new URLSearchParams({ page: currentPage + 1, q: config.query, status: config.status });
      const response = await fetch(`${config.pageUrl}?${params}`, { signal: controller.signal, headers: { Accept: 'application/json' } });
      if (!response.ok || response.redirected) throw new Error('Page unavailable');
      const data = await response.json();
      if (!data || data.page !== currentPage + 1 || typeof data.has_more !== 'boolean' || !Array.isArray(data.rows) ||
          !data.rows.every(row => row && Number.isInteger(row.id) && row.fields && typeof row.fields === 'object')) {
        throw new Error('Unexpected page response');
      }
      const fragment = document.createDocumentFragment();
      data.rows.forEach(row => fragment.appendChild(buildRow(row)));
      body.appendChild(fragment);
      currentPage = data.page;
      hasMore = data.has_more;
      applyColumns();
      sortRows();
      refreshBulkTools();
    } catch (_) {
      failed = true;
    } finally {
      window.clearTimeout(timeout);
      loading = false;
      renderLoadingState();
    }
  };
  loadButton.addEventListener('click', loadMore);
  window.addEventListener('scroll', () => {
    if (autoLoad.checked && !failed && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 200) loadMore();
  }, { passive: true });
  renderLoadingState();

  // Bulk toolbar extras: keep the print-labels link and the bulk-update Apply
  // button in sync with the existing bulk-select machinery. All writes reuse
  // the single CSRF-protected #bulk-delete-form — no second token is created.
  const labelsLink = document.getElementById('bulk-labels-link');
  const labelsBase = labelsLink ? labelsLink.getAttribute('href') : '';
  const bulkUpdateSubmit = document.getElementById('bulk-update-submit');
  const bulkUpdateValue = document.getElementById('bulk-update-value');
  const bulkUpdateField = document.getElementById('bulk-update-field');
  const refreshBulkTools = () => {
    const ids = [...document.querySelectorAll('.asset-checkbox:checked')].map(box => box.value);
    if (labelsLink) {
      const suffix = ids.length ? `?ids=${ids.map(encodeURIComponent).join(',')}` : '';
      labelsLink.setAttribute('href', `${labelsBase}${suffix}`);
      if (ids.length) labelsLink.removeAttribute('aria-disabled');
      else labelsLink.setAttribute('aria-disabled', 'true');
    }
    if (bulkUpdateSubmit) bulkUpdateSubmit.disabled = ids.length === 0;
  };
  if (labelsLink) {
    labelsLink.addEventListener('click', event => {
      if (labelsLink.getAttribute('aria-disabled') === 'true') event.preventDefault();
    });
  }
  if (bulkUpdateField && bulkUpdateValue) {
    bulkUpdateField.addEventListener('change', () => {
      bulkUpdateValue.placeholder = bulkUpdateField.value === 'status'
        ? 'Status, e.g. In Stock, Assigned, Broken, Write Off'
        : "Name, or 'free' to release";
    });
  }
  document.addEventListener('change', event => {
    const target = event.target;
    if (target && (target.id === 'select-all-assets' || (target.classList && target.classList.contains('asset-checkbox')))) refreshBulkTools();
  });
  document.addEventListener('click', () => queueMicrotask(refreshBulkTools));
  refreshBulkTools();
})();

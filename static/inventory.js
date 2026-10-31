(() => {
  'use strict';
  const table = document.querySelector('.inventory-page .list-table');
  if (!table) return;
  const body = table.tBodies[0];
  const config = JSON.parse(document.getElementById('inventory-config').textContent);
  const headers = [...table.querySelectorAll('th[data-sort-col]')];
  const choices = [...document.querySelectorAll('[data-column-choice]')];
  const storageKey = `inventory-columns:${table.closest('[data-asset-type]').dataset.assetType}`;
  const viewStorageKey = `inventory-view:${table.closest('[data-asset-type]').dataset.assetType}`;
  /* Card-view elements are resolved up front: applyColumns() can rebuild the
     card grid on its very first run. */
  const cardsGrid = document.getElementById('inventory-cards');
  const cardsEmpty = document.getElementById('inventory-cards-empty');
  const viewTable = document.getElementById('view-toggle-table');
  const viewCards = document.getElementById('view-toggle-cards');
  const viewContainers = [...document.querySelectorAll('.inventory-page .inventory-view')];
  let currentView = 'table';
  try {
    const pref = localStorage.getItem(viewStorageKey);
    if (pref === 'cards' || pref === 'table') currentView = pref;
  } catch (_) { /* Storage may be unavailable. */ }
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
    buildCardsIfActive();
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
      } else if (name === 'asset_tag') {
        cell.className = 'col-tag';
        cell.textContent = value || '-';
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
      buildCardsIfActive();
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

  /* ── Card view: the same records as bay plates ──────────────────────── */
  /* One data source (the table rows), two presentations. The card grid is
     rebuilt from the table so sorting, column choices, bulk selection and
     load-more stay perfectly in sync; the real form checkboxes live in the
     table and the cards carry mirrors that never submit duplicates. */
  const setView = view => {
    currentView = view === 'cards' ? 'cards' : 'table';
    viewContainers.forEach(container => {
      container.hidden = container.dataset.view !== currentView;
    });
    if (viewTable) viewTable.setAttribute('aria-pressed', String(currentView === 'table'));
    if (viewCards) viewCards.setAttribute('aria-pressed', String(currentView === 'cards'));
    try { localStorage.setItem(viewStorageKey, currentView); } catch (_) {}
    if (currentView === 'cards') buildCards();
  };

  /* Hoisted function declarations: applyColumns() runs before this section
     is evaluated, so the card view must be callable from its first pass. */
  function syncMirrors() {
    if (!cardsGrid) return;
    cardsGrid.querySelectorAll('.inventory-card').forEach(card => {
      const box = [...document.querySelectorAll('.inventory-view[data-view="table"] .asset-checkbox')]
        .find(b => b.value === card.dataset.cardRow);
      const mirror = card.querySelector('.asset-checkbox-mirror');
      if (box && mirror) mirror.checked = box.checked;
    });
  }

  function buildCards() {
    if (!cardsGrid) return;
    cardsGrid.replaceChildren();
    const headerCells = [...table.tHead.rows[0].cells];
    const fieldHeaders = headerCells.filter(th => th.dataset.field && !th.hidden);
    const cellOf = (row, th) => {
      const cell = row.cells[th.cellIndex];
      return cell && !cell.hidden ? cell : null;
    };
    const rows = [...body.rows].filter(row => row.querySelector('.col-idx'));
    rows.forEach(row => {
      const box = row.querySelector('.asset-checkbox');
      const id = box ? box.value : '';
      const article = document.createElement('article');
      article.className = 'inventory-card';
      article.dataset.cardRow = id;

      const top = document.createElement('div');
      top.className = 'inventory-card-top';
      const tagHeader = fieldHeaders.find(th => th.dataset.field === 'asset_tag');
      const tagCell = tagHeader ? cellOf(row, tagHeader) : null;
      if (tagCell) {
        const plate = document.createElement('span');
        plate.className = 'tag-plate';
        plate.textContent = tagCell.textContent.replace(/[↑↓]/g, '').trim() || '-';
        top.appendChild(plate);
      }
      const statusHeader = fieldHeaders.find(th => th.dataset.field === 'status');
      const statusCell = statusHeader ? cellOf(row, statusHeader) : null;
      if (statusCell) {
        const srcBadge = statusCell.querySelector('.badge');
        const badge = document.createElement('span');
        badge.className = srcBadge ? srcBadge.className : 'badge badge-default';
        badge.textContent = statusCell.textContent.trim() || '-';
        top.appendChild(badge);
      }
      const mirror = document.createElement('input');
      mirror.type = 'checkbox';
      mirror.className = 'asset-checkbox-mirror bulk-toggle-asset';
      mirror.setAttribute('aria-label', box ? box.getAttribute('aria-label') : `Select asset ${id}`);
      mirror.checked = Boolean(box && box.checked);
      top.appendChild(mirror);
      article.appendChild(top);

      const vendorHeader = fieldHeaders.find(th => th.dataset.field === 'vendor');
      const modelHeader = fieldHeaders.find(th => th.dataset.field === 'model');
      const titleParts = [];
      [vendorHeader, modelHeader].forEach(th => {
        if (!th) return;
        const cell = cellOf(row, th);
        if (cell) {
          const text = cell.textContent.trim();
          if (text && text !== '-') titleParts.push(text);
        }
      });
      const title = document.createElement('div');
      title.className = 'inventory-card-title';
      if (titleParts.length) {
        title.textContent = titleParts.join(' ');
      } else {
        const fallback = fieldHeaders
          .filter(th => th.dataset.field !== 'asset_tag' && th.dataset.field !== 'status')
          .map(th => cellOf(row, th))
          .find(cell => cell && cell.textContent.trim() && cell.textContent.trim() !== '-');
        title.textContent = fallback ? fallback.textContent.trim() : 'Asset';
      }
      article.appendChild(title);

      const fields = document.createElement('div');
      fields.className = 'inventory-card-fields';
      fieldHeaders.forEach(th => {
        const name = th.dataset.field;
        if (!name || name === 'asset_tag' || name === 'status' || name === 'vendor' || name === 'model') return;
        const cell = cellOf(row, th);
        if (!cell) return;
        const label = th.textContent.replace(/[↑↓]/g, '').trim();
        const value = cell.textContent.trim() || '-';
        const field = document.createElement('div');
        field.className = 'inventory-card-field';
        const dt = document.createElement('span');
        dt.className = 'inventory-card-field-label';
        dt.textContent = label;
        const dd = document.createElement('span');
        dd.className = 'inventory-card-field-value';
        dd.textContent = value;
        field.append(dt, dd);
        fields.appendChild(field);
      });
      if (fields.childElementCount) article.appendChild(fields);

      const act = row.querySelector('.col-act');
      if (act && act.childElementCount) {
        const actions = document.createElement('div');
        actions.className = 'inventory-card-actions';
        [...act.children].forEach(el => {
          const clone = el.cloneNode(true);
          if (clone.tagName === 'BUTTON' && !clone.getAttribute('onclick')) {
            clone.addEventListener('click', () => window.confirm('Delete this item?'));
          }
          actions.appendChild(clone);
        });
        article.appendChild(actions);
      }
      cardsGrid.appendChild(article);
    });
    if (cardsEmpty) cardsEmpty.hidden = rows.length > 0;
    syncMirrors();
  };

  function buildCardsIfActive() {
    if (currentView === 'cards') buildCards();
  }

  if (cardsGrid) {
    cardsGrid.addEventListener('change', event => {
      const mirror = event.target;
      if (!mirror.classList || !mirror.classList.contains('asset-checkbox-mirror')) return;
      const card = mirror.closest('.inventory-card');
      const box = [...document.querySelectorAll('.inventory-view[data-view="table"] .asset-checkbox')]
        .find(b => b.value === (card ? card.dataset.cardRow : ''));
      if (box) {
        box.checked = mirror.checked;
        box.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  }
  if (viewTable) viewTable.addEventListener('click', () => setView('table'));
  if (viewCards) viewCards.addEventListener('click', () => setView('cards'));

  /* Keep mirrors honest whenever the table checkboxes change. */
  document.addEventListener('change', event => {
    const target = event.target;
    if (target && (target.id === 'select-all-assets' || (target.classList && target.classList.contains('asset-checkbox')))) {
      queueMicrotask(syncMirrors);
    }
  });
  document.addEventListener('click', () => queueMicrotask(syncMirrors));
  document.addEventListener('click', event => {
    if (!cardsGrid || !cardsGrid.contains(event.target)) return;
    if (event.target.closest('a, button, input, label')) return;
    const card = event.target.closest('.inventory-card');
    if (!card || !card.dataset.cardRow) return;
    const box = [...document.querySelectorAll('.inventory-view[data-view="table"] .asset-checkbox')]
      .find(b => b.value === card.dataset.cardRow);
    if (box && box.style.display !== 'none') {
      box.checked = !box.checked;
      box.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  setView(currentView);
})();

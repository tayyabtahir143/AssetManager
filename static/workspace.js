/* Browser-only preferences and keyboard navigation. No API writes. */
(() => {
  'use strict';
  const root = document.documentElement;
  const readPreference = key => {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  };
  const savePreference = (key, value) => {
    try { localStorage.setItem(key, value); } catch (_) { /* Private mode remains usable. */ }
  };

  const density = document.getElementById('density-toggle');
  const setDensity = compact => {
    if (compact) root.dataset.density = 'compact';
    else delete root.dataset.density;
    density?.setAttribute('aria-pressed', String(compact));
    if (density) density.textContent = compact ? 'Comfortable' : 'Compact';
  };
  setDensity(readPreference('workspace-density') === 'compact');
  density?.addEventListener('click', () => {
    const compact = root.dataset.density !== 'compact';
    setDensity(compact);
    savePreference('workspace-density', compact ? 'compact' : 'comfortable');
  });

  document.querySelectorAll('.sidebar .nav-link.active').forEach(link => link.setAttribute('aria-current', 'page'));
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('mobile-overlay');
  const navButton = document.getElementById('mobile-nav-toggle');
  const mobile = window.matchMedia('(max-width: 900px)');
  const setNav = (open, restoreFocus = false) => {
    sidebar?.classList.toggle('open', open);
    overlay?.classList.toggle('show', open);
    navButton?.setAttribute('aria-expanded', String(open));
    navButton?.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    if (sidebar) sidebar.inert = mobile.matches && !open;
    if (open) sidebar?.querySelector('a')?.focus();
    if (restoreFocus) navButton?.focus();
    document.body.style.overflowY = open && mobile.matches ? 'hidden' : '';
  };
  setNav(false);
  navButton?.addEventListener('click', () => setNav(!sidebar?.classList.contains('open')));
  overlay?.addEventListener('click', () => setNav(false, true));
  sidebar?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setNav(false)));
  mobile.addEventListener('change', () => setNav(false));
  document.addEventListener('keydown', event => {
    if (!mobile.matches || !sidebar?.classList.contains('open')) return;
    if (event.key === 'Escape') { setNav(false, true); return; }
    if (event.key !== 'Tab') return;
    const focusable = [...sidebar.querySelectorAll('a, button')].filter(el => el.getClientRects().length);
    const first = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first?.focus();
    }
  });

  // Warn on navigation without caching form contents (especially credentials).
  document.querySelectorAll('form[data-unsaved-form]').forEach(form => {
    const state = form.querySelector('[data-editor-state]');
    const serialize = () => JSON.stringify([...new FormData(form)].filter(([key]) => key !== 'csrf_token').map(([key, value]) => [key, value instanceof File ? (value.name ? [value.name, value.size, value.lastModified] : null) : value]));
    const initial = serialize();
    let dirty = false;
    const warn = event => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    const update = () => {
      dirty = serialize() !== initial;
      if (state) {
        state.textContent = dirty ? 'Unsaved changes' : 'Changes are saved only when you select Save.';
        state.classList.toggle('is-dirty', dirty);
      }
      window.removeEventListener('beforeunload', warn);
      if (dirty) window.addEventListener('beforeunload', warn);
    };
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    form.addEventListener('submit', () => window.removeEventListener('beforeunload', warn));
    // Security deadlines take precedence over protecting unsaved edits.
    window.addEventListener('workspace:security-logout', () => window.removeEventListener('beforeunload', warn));
  });

  const dialog = document.getElementById('quick-nav');
  const trigger = document.getElementById('quick-nav-open');
  const search = document.getElementById('quick-nav-search');
  const results = document.getElementById('quick-nav-results');
  const assetList = document.getElementById('quick-nav-assets');
  const status = document.getElementById('quick-nav-status');
  if (!dialog || !trigger || !search || !results) return;

  // Only index links already rendered for this user's permissions. No hidden
  // administration destinations or destructive actions are added to the menu.
  const seen = new Set();
  const destinations = [...document.querySelectorAll('.sidebar nav a, [data-quick-nav]')].flatMap(link => {
    const href = link.getAttribute('href');
    if (!href || !href.startsWith('/') || seen.has(href)) return [];
    seen.add(href);
    return [{href, label: link.dataset.quickNav || link.textContent.trim(), section: link.closest('aside') ? 'Workspace' : 'Inventory'}];
  });
  const renderResults = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const matches = destinations.filter(item => item.label.toLocaleLowerCase().includes(query));
    results.replaceChildren();
    matches.forEach(item => {
      const link = document.createElement('a');
      link.href = item.href;
      link.className = 'quick-nav-result';
      const label = document.createElement('span');
      label.textContent = item.label;
      const section = document.createElement('span');
      section.textContent = item.section;
      link.append(label, section);
      results.appendChild(link);
    });
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.className = 'quick-nav-empty';
      empty.textContent = 'No matching pages. Try another name.';
      results.appendChild(empty);
    }
    if (status) status.textContent = `${matches.length} matching pages`;
  };

  /* ── Global asset search (GET /search?q=, session cookie auth) ───────── */
  const ASSET_SEARCH_DEBOUNCE_MS = 200;
  const ASSET_SEARCH_MIN_CHARS = 2;
  let assetTimer = null;
  let assetController = null;

  const assetSectionLabel = () => {
    const label = document.createElement('div');
    label.className = 'quick-nav-assets-label';
    label.textContent = 'Assets';
    return label;
  };

  const showAssetState = (className, message) => {
    if (!assetList) return;
    assetList.replaceChildren(assetSectionLabel());
    const row = document.createElement('p');
    row.className = className;
    row.textContent = message;
    assetList.appendChild(row);
  };

  const renderAssetResults = assets => {
    if (!assetList) return;
    if (!assets.length) {
      showAssetState('quick-nav-assets-empty', 'No matching assets');
      return;
    }
    assetList.replaceChildren(assetSectionLabel());
    assets.forEach(item => {
      const link = document.createElement('a');
      link.href = item.url;
      link.className = 'quick-nav-asset-result';
      const title = document.createElement('span');
      title.className = 'qna-title';
      title.textContent = item.title || item.label || 'Asset';
      const badge = document.createElement('span');
      badge.className = 'qna-badge';
      badge.textContent = item.label || 'Asset';
      const tag = document.createElement('span');
      tag.className = 'qna-tag';
      tag.textContent = item.asset_tag || '';
      const subtitle = document.createElement('span');
      subtitle.className = 'qna-subtitle';
      subtitle.textContent = item.subtitle || '';
      link.append(title, badge, tag, subtitle);
      assetList.appendChild(link);
    });
  };

  const fetchAssets = query => {
    if (assetController) assetController.abort();
    assetController = new AbortController();
    showAssetState('quick-nav-assets-loading', 'Searching assets…');
    fetch('/search?q=' + encodeURIComponent(query), {
      headers: { Accept: 'application/json' },
      signal: assetController.signal,
    })
      .then(response => (response.ok ? response.json() : { results: [] }))
      .then(data => renderAssetResults(Array.isArray(data.results) ? data.results : []))
      .catch(error => {
        if (error.name !== 'AbortError') renderAssetResults([]);
      });
  };

  const scheduleAssetSearch = value => {
    if (assetTimer) clearTimeout(assetTimer);
    if (assetController) assetController.abort();
    const query = (value || '').trim();
    if (!query) {
      assetList?.replaceChildren();
      return;
    }
    if (query.length < ASSET_SEARCH_MIN_CHARS) {
      showAssetState('quick-nav-assets-hint',
        `Type ${ASSET_SEARCH_MIN_CHARS} or more characters to search assets.`);
      return;
    }
    assetTimer = setTimeout(() => fetchAssets(query), ASSET_SEARCH_DEBOUNCE_MS);
  };

  let previousFocus;
  const open = () => {
    if (dialog.open) return;
    previousFocus = document.activeElement;
    setNav(false);
    search.value = '';
    renderResults();
    assetList?.replaceChildren();
    dialog.showModal();
    search.focus();
  };
  trigger.addEventListener('click', open);
  search.addEventListener('input', () => {
    renderResults();
    scheduleAssetSearch(search.value);
  });
  document.getElementById('quick-nav-close')?.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => previousFocus?.focus());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.addEventListener('keydown', event => {
    const links = [...results.querySelectorAll('a'), ...(assetList ? assetList.querySelectorAll('a') : [])];
    const current = links.indexOf(document.activeElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!links.length) return;
      const next = event.key === 'ArrowDown' ? (current + 1) % links.length : (current <= 0 ? links.length - 1 : current - 1);
      links[next].focus();
    } else if (event.key === 'Enter' && document.activeElement === search) {
      event.preventDefault(); links[0]?.click();
    }
  });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (dialog.open) dialog.close(); else open();
    }
  });
})();

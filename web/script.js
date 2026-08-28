/**
 * Apple Cleanup — Modern Web Dashboard Controller
 * ──────────────────────────────────────────────────────────
 * Full integration with Python server backend & rich safety controls.
 */
(() => {
  'use strict';

  /* ══════════════════════════════════════════════════════════
     Category Definitions & Safety Risks
     ══════════════════════════════════════════════════════════ */
  const CATEGORIES = [
    {
      key: 'user_cache', index: 1, name: 'User Caches',
      desc: 'Application temporary cache files (~/Library/Caches)',
      risk: 'safe', icon: 'ic-sparkles', color: 'var(--cat-cache)',
      defaultChecked: true, tags: [{ label: 'Safe to remove', type: 'safe' }]
    },
    {
      key: 'system_cache', index: 2, name: 'System Caches',
      desc: 'System-level caches (/Library/Caches)',
      risk: 'caution', icon: 'ic-wrench', color: 'var(--cat-system)',
      defaultChecked: false, tags: [{ label: 'Rebuilt automatically', type: 'caution' }]
    },
    {
      key: 'logs', index: 3, name: 'System & User Logs',
      desc: 'Crash logs, diagnostics, and diagnostic reports',
      risk: 'safe', icon: 'ic-sparkles', color: 'var(--cat-logs)',
      defaultChecked: true, tags: [{ label: 'Safe to remove', type: 'safe' }]
    },
    {
      key: 'temp_files', index: 4, name: 'Temporary Files',
      desc: 'Old temporary items in /tmp and /var/folders',
      risk: 'safe', icon: 'ic-sparkles', color: 'var(--cat-temp)',
      defaultChecked: true, tags: [{ label: 'Safe to remove', type: 'safe' }]
    },
    {
      key: 'xcode', index: 5, name: 'Xcode Derived Data & Archives',
      desc: 'Build caches, DerivedData, iOS DeviceSupport',
      risk: 'safe', icon: 'ic-wrench', color: 'var(--cat-xcode)',
      defaultChecked: true, tags: [{ label: 'Dev cache', type: 'safe' }]
    },
    {
      key: 'mail_downloads', index: 6, name: 'Mail Attachments & Downloads',
      desc: 'Cached copies of opened email attachments',
      risk: 'caution', icon: 'ic-hard-drive', color: 'var(--cat-mail)',
      defaultChecked: false, tags: [{ label: 'Caution', type: 'caution' }]
    },
    {
      key: 'browser_cache', index: 7, name: 'Browser Caches',
      desc: 'Safari, Chrome, Edge, Firefox cached web data',
      risk: 'safe', icon: 'ic-sparkles', color: 'var(--cat-browser)',
      defaultChecked: true, tags: [{ label: 'Fast reload cache', type: 'safe' }]
    },
    {
      key: 'browser_full', index: 8, name: 'Complete Browser Data',
      desc: 'Cookies, history, and stored session data',
      risk: 'danger', icon: 'ic-alert-triangle', color: 'var(--danger)',
      defaultChecked: false, tags: [{ label: 'Permanent / Logouts', type: 'danger' }]
    },
    {
      key: 'trash', index: 9, name: 'Main User Trash',
      desc: 'Items in your macOS ~/.Trash folder',
      risk: 'caution', icon: 'ic-trash', color: 'var(--cat-trash)',
      defaultChecked: true, tags: [{ label: 'Permanent deletion', type: 'caution' }]
    },
    {
      key: 'app_leftovers', index: 10, name: 'App Leftover Files',
      desc: 'Orphaned preferences & containers from uninstalled apps',
      risk: 'caution', icon: 'ic-package-x', color: 'var(--cat-developer)',
      defaultChecked: false, tags: [{ label: 'Orphaned items', type: 'caution' }]
    },
    {
      key: 'developer', index: 11, name: 'Developer Tool Caches',
      desc: 'Homebrew downloads, CocoaPods, npm, yarn, pip cache',
      risk: 'safe', icon: 'ic-wrench', color: 'var(--cat-developer)',
      defaultChecked: true, tags: [{ label: 'Safe to remove', type: 'safe' }]
    },
    {
      key: 'quicklook', index: 12, name: 'QuickLook Thumbnail Cache',
      desc: 'Finder preview thumbnail database',
      risk: 'safe', icon: 'ic-sparkles', color: 'var(--cat-cache)',
      defaultChecked: true, tags: [{ label: 'Re-generated on demand', type: 'safe' }]
    },
    {
      key: 'ios_backups', index: 13, name: 'Old iOS Device Backups',
      desc: 'Local iPhone and iPad backups in MobileSync',
      risk: 'danger', icon: 'ic-alert-triangle', color: 'var(--cat-ios)',
      defaultChecked: false, tags: [{ label: 'Permanent', type: 'danger' }]
    },
    {
      key: 'app_uninstaller', index: 14, name: 'Installed Applications',
      desc: 'Targeted removal of complete app bundles',
      risk: 'caution', icon: 'ic-package-x', color: 'var(--cat-developer)',
      defaultChecked: false, tags: [{ label: 'Explicit select', type: 'caution' }]
    },
    {
      key: 'other_trash', index: 16, name: 'Trash on External Volumes',
      desc: 'Hidden trash bins on connected external drives',
      risk: 'danger', icon: 'ic-alert-triangle', color: 'var(--danger)',
      defaultChecked: false, tags: [{ label: 'Permanent', type: 'danger' }]
    },
    {
      key: 'project_artifacts', index: 17, name: 'Project Build Folders',
      desc: 'Old node_modules, target/, .build directories in user projects',
      risk: 'caution', icon: 'ic-wrench', color: 'var(--cat-developer)',
      defaultChecked: false, tags: [{ label: 'Explicit select', type: 'caution' }]
    },
    {
      key: 'installer_artifacts', index: 18, name: 'Installer Packages & DMGs',
      desc: 'Large .dmg, .pkg, and .iso files in Downloads folder',
      risk: 'caution', icon: 'ic-hard-drive', color: 'var(--cat-system)',
      defaultChecked: false, tags: [{ label: 'Explicit select', type: 'caution' }]
    }
  ];

  const KEY_BY_INDEX = Object.fromEntries(CATEGORIES.map(c => [c.index, c.key]));
  const CAT_BY_KEY = Object.fromEntries(CATEGORIES.map(c => [c.key, c]));

  /* ══════════════════════════════════════════════════════════
     DOM Selectors & State
     ══════════════════════════════════════════════════════════ */
  const $ = (s, p = document) => p.querySelector(s);
  const $$ = (s, p = document) => Array.from(p.querySelectorAll(s));

  const state = {
    activeTab: 'dashboard',
    dryRun: false,
    scanData: null,
    backendOnline: false,
    selectedCategories: new Set(CATEGORIES.filter(c => c.defaultChecked).map(c => c.key)),
    selectedSubitems: {}, // { categoryKey: Set(subitemIds) }
    terminalLines: 0,
    appsList: [],
    largeFiles: [],
    dupGroups: [],
    historyList: []
  };

  /* ══════════════════════════════════════════════════════════
     Helper Utilities
     ══════════════════════════════════════════════════════════ */
  function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
    return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  /* ══════════════════════════════════════════════════════════
     Terminal Logger
     ══════════════════════════════════════════════════════════ */
  function termLog(msg, type = 'info') {
    const term = $('#terminalOutput');
    const badge = $('#termCountBadge');
    if (!term) return;

    const time = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    line.textContent = `[${time}] ${msg}`;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;

    state.terminalLines++;
    if (badge) badge.textContent = `${state.terminalLines} lines`;
  }

  // Toggle terminal drawer
  $('#btnToggleTerminal')?.addEventListener('click', () => {
    $('#terminalDrawer')?.classList.toggle('open');
  });
  $('#terminalHeader')?.addEventListener('click', () => {
    $('#terminalDrawer')?.classList.toggle('open');
  });

  /* ══════════════════════════════════════════════════════════
     Theme Controller
     ══════════════════════════════════════════════════════════ */
  function initTheme() {
    const saved = localStorage.getItem('ac-web-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeToggleUI(saved);
  }

  function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('ac-web-theme', next);
    updateThemeToggleUI(next);
    termLog(`Theme changed to ${next} mode.`, 'info');
  }

  function updateThemeToggleUI(theme) {
    const btn = $('#themeToggle');
    if (!btn) return;
    const sun = btn.querySelector('.ic-sun');
    const moon = btn.querySelector('.ic-moon');
    if (theme === 'dark') {
      if (sun) sun.style.display = 'block';
      if (moon) moon.style.display = 'none';
    } else {
      if (sun) sun.style.display = 'none';
      if (moon) moon.style.display = 'block';
    }
  }

  initTheme();
  $('#themeToggle')?.addEventListener('click', toggleTheme);

  /* ══════════════════════════════════════════════════════════
     API Bridge
     ══════════════════════════════════════════════════════════ */
  function getCleanupToken() {
    return $('meta[name="cleanup-token"]')?.content || '';
  }

  async function apiFetch(url, options = {}) {
    const token = getCleanupToken();
    const headers = {
      'Content-Type': 'application/json',
      'X-Cleanup-Token': token,
      ...(options.headers || {}),
    };

    let res;
    try {
      res = await fetch(url, {
        ...options,
        headers,
      });
    } catch (netErr) {
      throw new Error(`Network connection failed: ${netErr.message || 'Check if server is running'}`);
    }

    if (!res.ok) {
      let msg = `Server HTTP error ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson?.error) msg = errJson.error;
      } catch {}
      throw new Error(msg);
    }

    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      throw new Error(`Invalid JSON response from server`);
    }

    if (data?.success === false) {
      throw new Error(data.error || data.message || 'Operation failed.');
    }
    return data;
  }

  /* ══════════════════════════════════════════════════════════
     Tab Navigation Controller
     ══════════════════════════════════════════════════════════ */
  function switchTab(tabId) {
    state.activeTab = tabId;

    // Update sidebar buttons
    $$('.nav-item').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update tab panes
    $$('.tab-pane').forEach(pane => {
      pane.classList.toggle('active', pane.id === `tab-${tabId}`);
    });

    // Lazy load tab data
    if (tabId === 'smart-clean') renderSmartCleanView();
    if (tabId === 'uninstaller') loadUninstallerApps();
    if (tabId === 'large-files') loadLargeFiles();
    if (tabId === 'duplicates') loadDuplicateFiles();
    if (tabId === 'history') loadHistoryRecords();

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  $('#sidebarMenu')?.addEventListener('click', (e) => {
    const btn = e.target.closest('.nav-item');
    if (btn?.dataset.tab) switchTab(btn.dataset.tab);
  });

  // Action links
  document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-tab-link]');
    if (link?.dataset.tabLink) switchTab(link.dataset.tabLink);
  });
  $('#btnGoClean')?.addEventListener('click', () => switchTab('smart-clean'));

  /* ══════════════════════════════════════════════════════════
     Dry-run Global Switch
     ══════════════════════════════════════════════════════════ */
  const dryRunSwitch = $('#dryRunToggleGlobal');
  dryRunSwitch?.addEventListener('change', (e) => {
    state.dryRun = e.target.checked;
    termLog(`Dry Run Simulation mode is now ${state.dryRun ? 'ENABLED' : 'DISABLED'}.`, state.dryRun ? 'warning' : 'info');
  });

  /* ══════════════════════════════════════════════════════════
     Dashboard & Storage Ring
     ══════════════════════════════════════════════════════════ */
  function renderStorageRing(usedBytes, totalBytes) {
    const svg = $('#storageRingSvg');
    if (!svg || !totalBytes) return;

    const size = 190, stroke = 14;
    const radius = (size - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const cx = size / 2, cy = size / 2;

    const usedPct = Math.min(100, Math.max(0, (usedBytes / totalBytes) * 100));
    const usedDash = (usedPct / 100) * circumference;

    let ringColor = 'var(--accent)';
    const badge = $('#dashRingBadge');
    if (badge) {
      if (usedPct > 90) {
        badge.textContent = 'Critical (90%+)';
        badge.className = 'tag-badge tag-danger';
        ringColor = 'var(--danger)';
      } else if (usedPct > 75) {
        badge.textContent = 'High Space Usage';
        badge.className = 'tag-badge tag-caution';
        ringColor = 'var(--warning)';
      } else {
        badge.textContent = 'Normal';
        badge.className = 'tag-badge tag-safe';
        ringColor = 'var(--accent)';
      }
    }

    const bulletUsed = $('#bulletUsed');
    if (bulletUsed) {
      bulletUsed.style.background = ringColor;
    }

    svg.innerHTML = `
      <circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" stroke="var(--surface-3)" stroke-width="${stroke}"/>
      <circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" stroke="${ringColor}" stroke-width="${stroke}"
        stroke-linecap="round" stroke-dasharray="${usedDash} ${circumference}"
        style="transition: stroke-dasharray 1s ease-out;"/>
    `;

    const usedGB = (usedBytes / (1024 ** 3)).toFixed(1);
    const totalGB = (totalBytes / (1024 ** 3)).toFixed(0);
    const freeBytes = Math.max(0, totalBytes - usedBytes);

    $('#dashRingVal').innerHTML = `${usedGB}<span class="ring-big-unit"> / ${totalGB} GB</span>`;
    $('#dashRingSub').textContent = `${usedPct.toFixed(0)}% Used Storage`;

    $('#metricUsed').textContent = formatBytes(usedBytes);
    $('#metricFree').textContent = formatBytes(freeBytes);
    $('#headDiskFree').textContent = formatBytes(freeBytes);
  }

  function renderDashboardCleanableTiles() {
    const grid = $('#dashCategoriesSubgrid');
    if (!grid) return;

    let totalBytes = 0;
    const scan = state.scanData?.scan || {};

    const tilesHtml = CATEGORIES.slice(0, 8).map(cat => {
      const info = scan[cat.key];
      const bytes = info?.size_bytes || 0;
      totalBytes += bytes;

      return `
        <div class="cat-stat-tile" data-tab-link="smart-clean">
          <div class="tile-icon" style="background:${cat.color}15;color:${cat.color};">
            <svg><use href="#${cat.icon}"/></svg>
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(cat.name)}</div>
            <div style="font-size:12px;color:var(--text-3);font-family:var(--font-mono);margin-top:2px;">${formatBytes(bytes)}</div>
          </div>
        </div>
      `;
    }).join('');

    grid.innerHTML = tilesHtml;
    $('#dashCleanableTotal').textContent = formatBytes(totalBytes);
  }

  /* ══════════════════════════════════════════════════════════
     Smart Clean View & Logic
     ══════════════════════════════════════════════════════════ */
  function renderSmartCleanView() {
    const container = $('#smartCleanCategoriesList');
    if (!container) return;

    const scan = state.scanData?.scan || {};

    const html = CATEGORIES.map(cat => {
      const info = scan[cat.key];
      const bytes = info?.size_bytes || 0;
      const isChecked = state.selectedCategories.has(cat.key);
      const riskClass = cat.risk === 'danger' ? 'danger-category' : (cat.risk === 'caution' ? 'caution-category' : '');
      const subitems = Array.isArray(info?.subitems) ? info.subitems : [];

      const tagsHtml = cat.tags.map(t =>
        `<span class="tag-badge tag-${t.type}">${escapeHtml(t.label)}</span>`
      ).join(' ');

      return `
        <div class="cat-item-card ${riskClass}" data-cat-key="${cat.key}">
          <div class="cat-item-header" data-toggle-accordion="${cat.key}">
            <div class="cat-left-meta">
              <input type="checkbox" class="cat-checkbox" ${isChecked ? 'checked' : ''} data-cat-check="${cat.key}" />
              <div>
                <div class="cat-name-row">
                  <span>${escapeHtml(cat.name)}</span>
                  ${tagsHtml}
                </div>
                <div class="cat-desc-text">${escapeHtml(cat.desc)}</div>
              </div>
            </div>
            <div class="cat-right-meta">
              <span class="cat-size-pill">${formatBytes(bytes)}</span>
              ${subitems.length > 0 ? `<svg width="18" height="18" style="color:var(--text-3);"><use href="#ic-chevron-down"/></svg>` : ''}
            </div>
          </div>

          ${subitems.length > 0 ? `
            <div class="subitems-tray">
              <div style="font-size:11px;font-weight:700;color:var(--text-3);text-transform:uppercase;margin-bottom:8px;">Sub-items (${subitems.length})</div>
              ${subitems.map(sub => `
                <div class="subitem-entry">
                  <div class="subitem-left">
                    <input type="checkbox" class="cat-checkbox" checked data-sub-cat="${cat.key}" data-sub-id="${escapeHtml(sub.id)}" />
                    <div>
                      <div class="subitem-name">${escapeHtml(sub.name || sub.id)}</div>
                      <div class="subitem-path">${escapeHtml(sub.path || '')}</div>
                    </div>
                  </div>
                  <strong style="font-family:var(--font-mono);font-size:12px;">${escapeHtml(sub.size_human || formatBytes(sub.size_bytes))}</strong>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      `;
    }).join('');

    container.innerHTML = html;
    updateSmartCleanSelectedSummary();
  }

  function updateSmartCleanSelectedSummary() {
    let totalBytes = 0;
    let count = 0;
    const scan = state.scanData?.scan || {};

    state.selectedCategories.forEach(key => {
      const bytes = scan[key]?.size_bytes || 0;
      totalBytes += bytes;
      count++;
    });

    $('#smartSelectedSummary').textContent = `${count} categories selected`;
    $('#smartTotalSelectedSize').textContent = formatBytes(totalBytes);
  }

  // Accordion toggle & selection events
  $('#smartCleanCategoriesList')?.addEventListener('click', (e) => {
    // Checkbox clicked
    if (e.target.dataset.catCheck) {
      const key = e.target.dataset.catCheck;
      if (e.target.checked) state.selectedCategories.add(key);
      else state.selectedCategories.delete(key);
      updateSmartCleanSelectedSummary();
      return;
    }

    // Header accordion toggle
    const header = e.target.closest('[data-toggle-accordion]');
    if (header) {
      const card = header.closest('.cat-item-card');
      const open = card.getAttribute('data-open') === 'true';
      card.setAttribute('data-open', String(!open));
    }
  });

  // Select all safe categories
  $('#smartSelectAll')?.addEventListener('change', (e) => {
    const isChecked = e.target.checked;
    CATEGORIES.forEach(c => {
      if (c.risk === 'safe' || (isChecked && c.risk === 'caution')) {
        if (isChecked) state.selectedCategories.add(c.key);
        else state.selectedCategories.delete(c.key);
      }
    });
    renderSmartCleanView();
  });

  /* ══════════════════════════════════════════════════════════
     Execute Cleaning Action
     ══════════════════════════════════════════════════════════ */
  $('#btnExecuteClean')?.addEventListener('click', () => {
    if (state.selectedCategories.size === 0) {
      alert('Please select at least one category to clean.');
      return;
    }

    // Check if high-risk categories selected
    const selectedCats = Array.from(state.selectedCategories).map(k => CAT_BY_KEY[k]).filter(Boolean);
    const hasDanger = selectedCats.some(c => c.risk === 'danger');

    if (hasDanger && !state.dryRun) {
      showSafetyModal(
        'Permanent Cleanup Confirmation',
        `You have selected high-risk categories (such as iOS Backups or Trash). Files deleted in these categories cannot be recovered. Are you sure you want to permanently delete them?`,
        () => performClean()
      );
    } else {
      performClean();
    }
  });

  async function performClean() {
    const btn = $('#btnExecuteClean');
    if (btn) { btn.disabled = true; btn.textContent = state.dryRun ? 'Simulating...' : 'Cleaning...'; }

    const selectedIndices = Array.from(state.selectedCategories)
      .map(k => CAT_BY_KEY[k]?.index)
      .filter(Number.isFinite);

    termLog(`Initiating ${state.dryRun ? 'DRY-RUN simulation' : 'cleaning'} for ${selectedIndices.length} categories...`, 'warning');

    try {
      if (state.backendOnline) {
        const payload = {
          categories: selectedIndices,
          dry_run: state.dryRun
        };
        const res = await apiFetch('/api/clean', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        termLog(`Clean finished successfully! Freed: ${res.freed_human || '0 B'}.`, 'success');
        alert(state.dryRun
          ? `[Dry Run Simulation Finished]\nWould free approximately: ${res.freed_human || '0 B'}`
          : `[Cleanup Complete]\nSuccessfully freed ${res.freed_human || '0 B'} of disk space!`
        );
      } else {
        await sleep(1500);
        termLog('Simulated clean completed (Backend offline).', 'success');
        alert('[Simulation Complete] Space reclaimed in demo mode.');
      }

      // Refresh scan
      await triggerScan();
    } catch (err) {
      termLog(`Clean failed: ${err.message}`, 'error');
      alert(`Error during cleanup: ${err.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Clean Selected Space'; }
    }
  }

  /* ══════════════════════════════════════════════════════════
     System Maintenance Tools Execution
     ══════════════════════════════════════════════════════════ */
  async function runSystemTool(endpoint, toolName, btn) {
    if (btn) { btn.disabled = true; btn.textContent = 'Running...'; }
    termLog(`Starting maintenance tool: ${toolName}...`, 'info');

    try {
      if (state.backendOnline) {
        const res = await apiFetch(endpoint, { method: 'POST', body: '{}' });
        const successMsg = res.message || res.status || res.note || 'Operation completed successfully.';
        termLog(`${toolName} succeeded: ${successMsg}`, 'success');
        alert(`[${toolName}]\n${successMsg}`);
      } else {
        await sleep(1000);
        termLog(`${toolName} executed in simulation mode.`, 'success');
        alert(`[${toolName}]\nOperation simulated successfully.`);
      }
    } catch (err) {
      termLog(`${toolName} error: ${err.message}`, 'error');
      alert(`[${toolName}]\n${err.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = btn.getAttribute('data-orig-text') || 'Run Tool'; }
    }
  }

  $('#btnToolSpotlight')?.addEventListener('click', function() {
    this.setAttribute('data-orig-text', 'Reindex Search Index');
    runSystemTool('/api/spotlight-reindex', 'Rebuild Spotlight Index', this);
  });
  $('#btnToolFlushDns')?.addEventListener('click', function() {
    this.setAttribute('data-orig-text', 'Flush DNS Records');
    runSystemTool('/api/flush-dns', 'Flush DNS Cache', this);
  });
  $('#btnToolPurgeRam')?.addEventListener('click', function() {
    this.setAttribute('data-orig-text', 'Purge Inactive RAM');
    runSystemTool('/api/purge-ram', 'Purge Inactive Memory', this);
  });
  $('#btnToolLaunchAgents')?.addEventListener('click', function() {
    this.setAttribute('data-orig-text', 'Clean Dead Daemons');
    runSystemTool('/api/launchagents-clean', 'Clean Broken LaunchAgents', this);
  });
  $('#btnToolThinSnapshots')?.addEventListener('click', function() {
    this.setAttribute('data-orig-text', 'Thin APFS Snapshots');
    runSystemTool('/api/thin-snapshots', 'Thin APFS Local Snapshots', this);
  });
  $('#btnToolWeeklySchedule')?.addEventListener('click', async function() {
    this.disabled = true;
    try {
      if (state.backendOnline) {
        const status = await apiFetch('/api/schedule-status');
        const nextState = !status.scheduled;
        const res = await apiFetch('/api/schedule-weekly', {
          method: 'POST',
          body: JSON.stringify({ enable: nextState })
        });
        termLog(`Weekly automation: ${res.message || 'Updated'}`, 'success');
        alert(`[Weekly Cleanup Automation]\n${res.message || 'Scheduled updated.'}`);
      }
    } catch (err) {
      alert(`Could not toggle weekly schedule: ${err.message}`);
    } finally {
      this.disabled = false;
    }
  });

  /* ══════════════════════════════════════════════════════════
     App Uninstaller View
     ══════════════════════════════════════════════════════════ */
  async function loadUninstallerApps() {
    const container = $('#uninstallerAppList');
    if (!container) return;

    container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-3);">Scanning installed applications...</div>';

    try {
      if (state.backendOnline) {
        const data = await apiFetch('/api/apps');
        state.appsList = data.apps || [];
      } else {
        state.appsList = [
          { name: 'Xcode', size_bytes: 12400 * 1024 * 1024, version: '15.4', last_used: '2 days ago' },
          { name: 'Docker Desktop', size_bytes: 5200 * 1024 * 1024, version: '4.35', last_used: '5 days ago' },
          { name: 'Visual Studio Code', size_bytes: 1200 * 1024 * 1024, version: '1.94', last_used: 'Today' },
          { name: 'Slack', size_bytes: 780 * 1024 * 1024, version: '4.39', last_used: 'Today' },
          { name: 'Adobe Photoshop', size_bytes: 4800 * 1024 * 1024, version: '25.12', last_used: '1 month ago' },
          { name: 'Google Chrome', size_bytes: 980 * 1024 * 1024, version: '130.0', last_used: 'Today' }
        ];
      }
      renderAppsGrid();
    } catch (err) {
      container.innerHTML = `<div style="padding:40px;text-align:center;color:var(--danger);">Failed to load applications: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderAppsGrid(query = '') {
    const container = $('#uninstallerAppList');
    if (!container) return;

    const filtered = state.appsList.filter(a =>
      a.name.toLowerCase().includes(query.toLowerCase())
    );

    if (filtered.length === 0) {
      container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-3);">No matching applications found.</div>';
      return;
    }

    container.innerHTML = `
      <div class="apps-grid">
        ${filtered.map(app => `
          <div class="app-card-box">
            <div>
              <div style="font-weight:700;font-size:15px;">${escapeHtml(app.name)}</div>
              <div style="font-size:12px;color:var(--text-3);margin-top:2px;">Version ${escapeHtml(app.version || '—')}</div>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--border);padding-top:10px;margin-top:4px;">
              <strong style="font-family:var(--font-mono);font-size:14px;color:var(--accent);">${formatBytes(app.size_bytes)}</strong>
              <button class="btn btn-danger" style="padding:6px 12px;font-size:12px;" data-uninstall-app="${escapeHtml(app.name)}">
                <svg width="14" height="14"><use href="#ic-trash"/></svg> Uninstall
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  $('#appSearchInput')?.addEventListener('input', (e) => {
    renderAppsGrid(e.target.value);
  });

  $('#uninstallerAppList')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-uninstall-app]');
    if (!btn) return;
    const appName = btn.dataset.uninstallApp;

    showSafetyModal(
      `Uninstall Application: ${appName}`,
      `This will completely delete ${appName} and all associated cache and configuration files from ~/Library. Are you sure?`,
      async () => {
        termLog(`Uninstalling app: ${appName}...`, 'warning');
        try {
          if (state.backendOnline) {
            await apiFetch('/api/uninstall', {
              method: 'POST',
              body: JSON.stringify({ app_name: appName })
            });
            termLog(`App ${appName} uninstalled successfully.`, 'success');
          }
          state.appsList = state.appsList.filter(a => a.name !== appName);
          renderAppsGrid($('#appSearchInput')?.value || '');
          alert(`Application "${appName}" removed.`);
        } catch (err) {
          alert(`Failed to uninstall: ${err.message}`);
        }
      }
    );
  });

  /* ══════════════════════════════════════════════════════════
     Large Files & Duplicates (Mock/Demo & Integration)
     ══════════════════════════════════════════════════════════ */
  function loadLargeFiles() {
    const c = $('#largeFilesContainer');
    if (!c) return;
    c.innerHTML = `
      <div class="card" style="padding:24px;">
        <div style="font-weight:700;font-size:16px;margin-bottom:12px;">Large System Files (&gt;100MB)</div>
        <div style="font-size:13px;color:var(--text-2);margin-bottom:20px;">Review and clean unneeded massive installers and backup packages.</div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Filename</th><th>Location</th><th>Size</th><th>Action</th></tr>
            </thead>
            <tbody>
              <tr><td><strong>macOS_Sonoma_14.5.dmg</strong></td><td>~/Downloads/</td><td>12.8 GB</td><td><button class="btn btn-danger" style="padding:4px 8px;font-size:11px;">Delete</button></td></tr>
              <tr><td><strong>xcode_backup_archive.zip</strong></td><td>~/Documents/</td><td>4.2 GB</td><td><button class="btn btn-danger" style="padding:4px 8px;font-size:11px;">Delete</button></td></tr>
              <tr><td><strong>ubuntu_vm_disk.qcow2</strong></td><td>~/VirtualMachines/</td><td>8.4 GB</td><td><button class="btn btn-danger" style="padding:4px 8px;font-size:11px;">Delete</button></td></tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  function loadDuplicateFiles() {
    const c = $('#duplicatesContainer');
    if (!c) return;
    c.innerHTML = `
      <div class="card" style="padding:24px;">
        <div style="font-weight:700;font-size:16px;margin-bottom:12px;">Identified Duplicate Files</div>
        <div style="font-size:13px;color:var(--text-2);margin-bottom:20px;">Copies have identical SHA-256 hashes. Safely delete secondary duplicates while keeping original files.</div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Original File</th><th>Duplicate Copies</th><th>Wasted Space</th><th>Action</th></tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>presentation_final.pptx</strong><div style="font-size:11px;color:var(--text-3);">~/Documents/Work/</div></td>
                <td>~/Desktop/presentation_final copy.pptx</td>
                <td><strong style="color:var(--danger);">48 MB</strong></td>
                <td><button class="btn btn-secondary" style="padding:4px 8px;font-size:11px;">Clean Copy</button></td>
              </tr>
              <tr>
                <td><strong>vacation_video.mov</strong><div style="font-size:11px;color:var(--text-3);">~/Movies/</div></td>
                <td>~/Downloads/vacation_video (1).mov</td>
                <td><strong style="color:var(--danger);">420 MB</strong></td>
                <td><button class="btn btn-secondary" style="padding:4px 8px;font-size:11px;">Clean Copy</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  /* ══════════════════════════════════════════════════════════
     Operations History
     ══════════════════════════════════════════════════════════ */
  async function loadHistoryRecords() {
    const tbody = $('#historyTableBody');
    if (!tbody) return;

    try {
      if (state.backendOnline) {
        const rows = await apiFetch('/api/history');
        if (!Array.isArray(rows) || rows.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-3);padding:32px;">No historical operations recorded yet.</td></tr>';
          return;
        }

        tbody.innerHTML = rows.map(r => `
          <tr>
            <td>${escapeHtml(r.timestamp || '—')}</td>
            <td><strong>${escapeHtml(r.action || 'Clean')}</strong></td>
            <td>${escapeHtml(Array.isArray(r.categories) ? r.categories.join(', ') : (r.items_count || '—'))}</td>
            <td><strong style="color:var(--safe);">${formatBytes(r.freed_bytes || 0)}</strong></td>
            <td><span class="tag-badge tag-safe">SUCCESS</span></td>
          </tr>
        `).join('');
      } else {
        tbody.innerHTML = `
          <tr>
            <td>Today, 09:15</td>
            <td><strong>Smart Clean</strong></td>
            <td>User Caches, Xcode Derived Data, Logs</td>
            <td><strong style="color:var(--safe);">4.8 GB</strong></td>
            <td><span class="tag-badge tag-safe">SUCCESS</span></td>
          </tr>
        `;
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--danger);padding:32px;">Could not load history: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  $('#btnRefreshHistory')?.addEventListener('click', loadHistoryRecords);

  /* ══════════════════════════════════════════════════════════
     Safety Confirmation Modal
     ══════════════════════════════════════════════════════════ */
  let modalConfirmCallback = null;

  function showSafetyModal(title, message, onConfirm) {
    const modal = $('#safetyConfirmModal');
    if (!modal) return;

    $('#modalTitle').textContent = title;
    $('#modalBody').textContent = message;
    modalConfirmCallback = onConfirm;

    modal.classList.add('open');
  }

  function hideSafetyModal() {
    $('#safetyConfirmModal')?.classList.remove('open');
    modalConfirmCallback = null;
  }

  $('#modalBtnCancel')?.addEventListener('click', hideSafetyModal);
  $('#modalBtnConfirm')?.addEventListener('click', () => {
    if (typeof modalConfirmCallback === 'function') {
      modalConfirmCallback();
    }
    hideSafetyModal();
  });

  /* ══════════════════════════════════════════════════════════
     Trigger Scan & Init
     ══════════════════════════════════════════════════════════ */
  async function triggerScan() {
    termLog('Scanning macOS system caches and storage...', 'info');
    try {
      if (state.backendOnline) {
        const scanResult = await apiFetch('/api/scan');
        state.scanData = scanResult;
        termLog('Scan completed successfully.', 'success');
      } else {
        // Mock scan data
        state.scanData = {
          scan: {
            user_cache: { size_bytes: 4820 * 1024 * 1024 },
            system_cache: { size_bytes: 1420 * 1024 * 1024 },
            logs: { size_bytes: 1240 * 1024 * 1024 },
            temp_files: { size_bytes: 3100 * 1024 * 1024 },
            xcode: { size_bytes: 8400 * 1024 * 1024 },
            browser_cache: { size_bytes: 2100 * 1024 * 1024 },
            trash: { size_bytes: 850 * 1024 * 1024 },
            developer: { size_bytes: 1900 * 1024 * 1024 },
            quicklook: { size_bytes: 340 * 1024 * 1024 }
          }
        };
      }
      renderDashboardCleanableTiles();
      if (state.activeTab === 'smart-clean') renderSmartCleanView();
    } catch (err) {
      termLog(`Scan error: ${err.message}`, 'error');
    }
  }

  $('#btnQuickScan')?.addEventListener('click', triggerScan);
  $('#btnSmartRescan')?.addEventListener('click', triggerScan);

  async function init() {
    termLog('Connecting to Apple Cleanup backend...', 'info');

    try {
      await apiFetch('/api/health');
      state.backendOnline = true;
      termLog('Backend connection established (Online).', 'success');

      // Fetch status
      const status = await apiFetch('/api/status');
      $('#headMacVer').textContent = status.macos_version || '14.5';
      $('#sysChipName').textContent = status.chip || 'Apple Silicon';
      $('#sysUser').textContent = status.user || '—';
      $('#sysMemory').textContent = status.memory || '—';

      if (status.disk_total_bytes && status.disk_used_bytes) {
        renderStorageRing(status.disk_used_bytes, status.disk_total_bytes);
      } else {
        renderStorageRing(340 * (1024**3), 512 * (1024**3));
      }
    } catch (e) {
      state.backendOnline = false;
      termLog('Running in standalone frontend mode.', 'warning');
      renderStorageRing(340 * (1024**3), 512 * (1024**3));
    }

    await triggerScan();
  }

  init();
})();

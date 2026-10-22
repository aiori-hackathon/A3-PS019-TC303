/**
 * frontend/app.js
 * ==============================================================================
 * PrivSight — Privacy Intelligence Workspace
 * Enterprise Dashboard Controller (Vanilla ES6 JavaScript)
 * 
 * Features:
 *   - Adaptive Light / Dark Theme Management with LocalStorage persistence
 *   - Responsive Sidebar & Navigation with Mobile Drawer
 *   - Real-time API Integration with FastAPI backend
 *   - Interactive Personal-Data Discovery & Evidence Inventory
 *   - Governance Gap Analysis & Prioritized Human Review Queue
 *   - Ground-Truth Benchmark Evaluation & Confusion Matrix Heatmap
 *   - Technical Detection Rule Inspector & Evidence Download Exports
 * ==============================================================================
 */

// ---------------------------------------------------------------------------
// 1. Application State Container
// ---------------------------------------------------------------------------
const state = {
  inventory: [],
  gaps: [],
  evaluation: null,
  rules: null,
  summary: null,
  currentTheme: 'dark',
  invPage: 1,
  invPageSize: 10,
  gapsPage: 1,
  gapsPageSize: 10,
};

// ---------------------------------------------------------------------------
// 2. DOM Elements Cache
// ---------------------------------------------------------------------------
const elements = {
  // Navigation & Shell
  appSidebar: document.getElementById('appSidebar'),
  sidebarCollapseBtn: document.getElementById('sidebarCollapseBtn'),
  collapseIcon: document.getElementById('collapseIcon'),
  mobileMenuBtn: document.getElementById('mobileMenuBtn'),
  breadcrumbCurrent: document.getElementById('breadcrumbCurrent'),
  tabButtons: document.querySelectorAll('.tab-btn'),
  tabPanes: document.querySelectorAll('.tab-pane'),

  // Theme Switcher
  themeToggleBtn: document.getElementById('themeToggleBtn'),
  themeToggleIcon: document.getElementById('themeToggleIcon'),

  // Header Actions & Status
  btnRunScan: document.getElementById('btnRunScan'),
  btnRunAnalyze: document.getElementById('btnRunAnalyze'),
  scanBtnLabel: document.getElementById('scanBtnLabel'),
  scanBtnIcon: document.getElementById('scanBtnIcon'),
  statusDot: document.getElementById('systemStatusDot'),
  statusText: document.getElementById('systemStatusText'),

  // Sidebar Badges
  sidebarInvBadge: document.getElementById('sidebarInvBadge'),
  sidebarGapsBadge: document.getElementById('sidebarGapsBadge'),

  // Overview Stats
  statScannedFields: document.getElementById('statScannedFields'),
  statCandidates: document.getElementById('statCandidates'),
  statComplete: document.getElementById('statComplete'),
  statGaps: document.getElementById('statGaps'),
  statReviewRequired: document.getElementById('statReviewRequired'),
  gapStatusList: document.getElementById('gapStatusList'),
  classDistributionList: document.getElementById('classDistributionList'),
  overviewGapsTotalBadge: document.getElementById('overviewGapsTotalBadge'),
  ovPrecision: document.getElementById('ovPrecision'),
  ovRecall: document.getElementById('ovRecall'),
  ovF1: document.getElementById('ovF1'),
  ovCompletenessPercent: document.getElementById('ovCompletenessPercent'),
  ovCompletenessBar: document.getElementById('ovCompletenessBar'),
  ovCompleteSub: document.getElementById('ovCompleteSub'),
  ovGapsSub: document.getElementById('ovGapsSub'),
  priorityReviewList: document.getElementById('priorityReviewList'),
  reviewQueueBadge: document.getElementById('reviewQueueBadge'),

  // Inventory Table & Filters
  inventoryTableBody: document.getElementById('inventoryTableBody'),
  inventoryCounter: document.getElementById('inventoryCounter'),
  invSearchInput: document.getElementById('invSearchInput'),
  invClassFilter: document.getElementById('invClassFilter'),
  invStatusFilter: document.getElementById('invStatusFilter'),
  invReviewFilter: document.getElementById('invReviewFilter'),
  btnResetInvFilter: document.getElementById('btnResetInvFilter'),

  // Evidence Gaps Table & Filters
  gapsTableBody: document.getElementById('gapsTableBody'),
  gapsCounter: document.getElementById('gapsCounter'),
  gapsSearchInput: document.getElementById('gapsSearchInput'),
  gapsStatusFilter: document.getElementById('gapsStatusFilter'),
  gapsClassFilter: document.getElementById('gapsClassFilter'),

  // Evaluation
  detPrecision: document.getElementById('detPrecision'),
  detRecall: document.getElementById('detRecall'),
  detF1: document.getElementById('detF1'),
  detCounts: document.getElementById('detCounts'),
  perClassTableBody: document.getElementById('perClassTableBody'),
  cmHeaderRow: document.getElementById('cmHeaderRow'),
  cmBody: document.getElementById('cmBody'),
  errorCountBadge: document.getElementById('errorCountBadge'),
  errorListContainer: document.getElementById('errorListContainer'),

  // Rules
  rulesContainer: document.getElementById('rulesContainer'),

  // Modal Inspector
  detailModal: document.getElementById('detailModal'),
  modalFieldTitle: document.getElementById('modalFieldTitle'),
  modalDetailsBody: document.getElementById('modalDetailsBody'),
  modalCloseBtn: document.getElementById('modalCloseBtn'),
  modalCloseBtnFooter: document.getElementById('modalCloseBtnFooter'),

  // Toast Container
  toastContainer: document.getElementById('toastContainer'),

  // Pagination Elements
  inventoryPagination: document.getElementById('inventoryPagination'),
  gapsPagination: document.getElementById('gapsPagination'),

  // Landing Page Live Highlights
  landingStatScanned: document.getElementById('landingStatScanned'),
  landingStatCandidates: document.getElementById('landingStatCandidates'),
  landingStatGaps: document.getElementById('landingStatGaps'),
  landingPrecisionVal: document.getElementById('landingPrecisionVal'),
  landingRecallVal: document.getElementById('landingRecallVal'),
  landingF1Val: document.getElementById('landingF1Val'),
};

// ---------------------------------------------------------------------------
// 3. Theme System (Light / Dark with Persistent Storage)
// ---------------------------------------------------------------------------
function initTheme() {
  const savedTheme = localStorage.getItem('privsight-theme');
  if (savedTheme) {
    state.currentTheme = savedTheme;
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    state.currentTheme = 'light';
  } else {
    state.currentTheme = 'dark';
  }

  applyTheme(state.currentTheme);

  if (elements.themeToggleBtn) {
    elements.themeToggleBtn.addEventListener('click', toggleTheme);
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  state.currentTheme = theme;
  localStorage.setItem('privsight-theme', theme);

  if (elements.themeToggleIcon) {
    elements.themeToggleIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}

function toggleTheme() {
  const nextTheme = state.currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(nextTheme);
  showToast(`Switched to ${nextTheme === 'dark' ? 'Dark' : 'Light'} theme`, 'info');
}

// ---------------------------------------------------------------------------
// 4. Sidebar & Responsive Layout
// ---------------------------------------------------------------------------
function initSidebar() {
  // Desktop Collapsible Sidebar
  if (elements.sidebarCollapseBtn && elements.appSidebar) {
    elements.sidebarCollapseBtn.addEventListener('click', () => {
      elements.appSidebar.classList.toggle('collapsed');
      const isCollapsed = elements.appSidebar.classList.contains('collapsed');
      if (elements.collapseIcon) {
        elements.collapseIcon.textContent = isCollapsed ? '▶' : '◀';
      }
    });
  }

  // Mobile Drawer Toggle
  if (elements.mobileMenuBtn && elements.appSidebar) {
    elements.mobileMenuBtn.addEventListener('click', () => {
      elements.appSidebar.classList.toggle('mobile-open');
    });
  }

  // Close mobile drawer when clicking outside
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 && elements.appSidebar && elements.appSidebar.classList.contains('mobile-open')) {
      if (!elements.appSidebar.contains(e.target) && e.target !== elements.mobileMenuBtn) {
        elements.appSidebar.classList.remove('mobile-open');
      }
    }
  });
}

// ---------------------------------------------------------------------------
// 5. Tab Navigation
// ---------------------------------------------------------------------------
const TAB_TITLES = {
  'tab-overview': 'Overview',
  'tab-inventory': 'Personal-Data Inventory',
  'tab-gaps': 'Evidence Gaps',
  'tab-evaluation': 'Ground-Truth Evaluation',
  'tab-rules': 'Detection Rules',
  'tab-reports': 'Reports & Downloads',
};

function highlightActiveNav() {
  const path = (window.location.pathname || '').toLowerCase();
  const navLinks = document.querySelectorAll('.sidebar-nav .nav-item');
  if (!navLinks || navLinks.length === 0) return;

  navLinks.forEach(link => {
    link.classList.remove('active');
    const href = link.getAttribute('href') ? link.getAttribute('href').toLowerCase() : '';
    if (!href) return;
    
    const isCurrent =
      ((href === '/workspace' || href.includes('workspace') || href.includes('overview')) && (path.includes('workspace') || path.includes('overview'))) ||
      (href.includes('inventory') && path.includes('inventory')) ||
      ((href.includes('evidence-gaps') || href.includes('gaps')) && (path.includes('evidence-gaps') || path.includes('gaps'))) ||
      (href.includes('evaluation') && path.includes('evaluation')) ||
      (href.includes('rules') && path.includes('rules')) ||
      (href.includes('reports') && path.includes('reports')) ||
      (href === '/' && (path === '' || path === '/' || path === '/index.html'));

    if (isCurrent) {
      link.classList.add('active');
    }
  });
}

function initTabs() {
  highlightActiveNav();

  if (elements.tabButtons && elements.tabButtons.length > 0) {
    elements.tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-tab');
        if (!targetId) return;

        elements.tabButtons.forEach(b => b.classList.remove('active'));
        elements.tabPanes.forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add('active');

        // Update Breadcrumb
        if (elements.breadcrumbCurrent && TAB_TITLES[targetId]) {
          elements.breadcrumbCurrent.textContent = TAB_TITLES[targetId];
        }

        // Close mobile drawer upon navigation
        if (window.innerWidth <= 768 && elements.appSidebar) {
          elements.appSidebar.classList.remove('mobile-open');
        }
      });
    });
  }
}

// ---------------------------------------------------------------------------
// 6. Utility Functions
// ---------------------------------------------------------------------------
function showToast(message, type = 'info') {
  if (!elements.toastContainer) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icon = type === 'success' ? '✔' : type === 'error' ? '✖' : 'ℹ';
  toast.innerHTML = `<span style="font-weight:bold; font-size:1rem;">${icon}</span><span>${escapeHtml(message)}</span>`;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function getClassBadge(cls) {
  if (!cls) return `<span class="badge badge-status-unmapped">Non-PII</span>`;
  const lower = String(cls).toLowerCase();
  const safeCls = escapeHtml(cls);
  if (lower.includes('identity')) return `<span class="badge badge-class-identity">👤 ${safeCls}</span>`;
  if (lower.includes('contact')) return `<span class="badge badge-class-contact">📞 ${safeCls}</span>`;
  if (lower.includes('location')) return `<span class="badge badge-class-location">📍 ${safeCls}</span>`;
  if (lower.includes('financial')) return `<span class="badge badge-class-financial">💳 ${safeCls}</span>`;
  if (lower.includes('sensitive') || lower.includes('health')) return `<span class="badge badge-class-sensitive">🛡️ ${safeCls}</span>`;
  return `<span class="badge">${safeCls}</span>`;
}

function getStatusBadge(status) {
  switch (status) {
    case 'Complete':
      return `<span class="badge badge-status-complete">✔ Complete</span>`;
    case 'Purpose Missing':
      return `<span class="badge badge-status-purp-miss">Purpose Missing</span>`;
    case 'Retention Missing':
      return `<span class="badge badge-status-ret-miss">Retention Missing</span>`;
    case 'Purpose & Retention Missing':
      return `<span class="badge badge-status-both-miss">Both Missing</span>`;
    case 'Not Mapped':
    default:
      return `<span class="badge badge-status-unmapped">Not Mapped</span>`;
  }
}

// ---------------------------------------------------------------------------
// 7. Data Fetching & UI Rendering
// ---------------------------------------------------------------------------

// A. Overview Summary
async function fetchSummary() {
  try {
    const res = await fetch('/api/summary');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.summary = data;

    const scanned = data.scanned_fields || 84;
    const candidates = data.candidate_fields || 0;
    const complete = data.complete_metadata || 0;
    const gaps = data.evidence_gaps || 0;
    const review = data.review_required || 0;

    if (elements.statScannedFields) elements.statScannedFields.textContent = scanned;
    if (elements.statCandidates) elements.statCandidates.textContent = candidates;
    if (elements.statComplete) elements.statComplete.textContent = complete;
    if (elements.statGaps) elements.statGaps.textContent = gaps;
    if (elements.statReviewRequired) elements.statReviewRequired.textContent = review;

    // Update Sidebar Badges
    if (elements.sidebarInvBadge) elements.sidebarInvBadge.textContent = candidates;
    if (elements.sidebarGapsBadge) elements.sidebarGapsBadge.textContent = gaps;
    if (elements.overviewGapsTotalBadge) elements.overviewGapsTotalBadge.textContent = `${gaps} Gaps`;

    // Render Evidence Gaps Distribution
    const breakdown = data.gaps_by_status || {};
    let gapHtml = '';
    const gapCategories = [
      { key: 'Not Mapped', label: 'Not Mapped (No Governance Policy)', colorClass: 'rose' },
      { key: 'Retention Missing', label: 'Retention Missing (Purpose Declared)', colorClass: 'amber' },
      { key: 'Purpose Missing', label: 'Purpose Missing (Retention Declared)', colorClass: 'orange' },
      { key: 'Purpose & Retention Missing', label: 'Both Purpose & Retention Missing', colorClass: 'rose' },
    ];

    gapCategories.forEach(cat => {
      const count = breakdown[cat.key] || 0;
      const pct = gaps > 0 ? Math.round((count / gaps) * 100) : 0;
      gapHtml += `
        <div>
          <div class="progress-item-header">
            <span style="font-weight:600; color:var(--text-secondary); font-size:0.8rem;">${cat.label}</span>
            <span class="font-mono" style="font-weight:700; color:var(--text-primary);">${count} <span style="color:var(--text-muted); font-size:0.75rem;">(${pct}%)</span></span>
          </div>
          <div class="progress-track">
            <div class="progress-fill ${cat.colorClass}" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    });
    if (elements.gapStatusList) elements.gapStatusList.innerHTML = gapHtml;

    // Render Governance Completeness Progress Bar
    const totalConsidered = complete + gaps;
    const compPct = totalConsidered > 0 ? Math.round((complete / totalConsidered) * 100) : 0;
    if (elements.ovCompletenessPercent) elements.ovCompletenessPercent.textContent = `${compPct}%`;
    if (elements.ovCompletenessBar) elements.ovCompletenessBar.style.width = `${compPct}%`;
    if (elements.ovCompleteSub) elements.ovCompleteSub.textContent = `${complete} Complete`;
    if (elements.ovGapsSub) elements.ovGapsSub.textContent = `${gaps} Evidence Gaps`;

    // Snapshot evaluation
    if (data.evaluation) {
      const p = data.evaluation.detection_precision;
      const r = data.evaluation.detection_recall;
      const f = data.evaluation.detection_f1;
      if (elements.ovPrecision) elements.ovPrecision.textContent = p !== null ? `${(p * 100).toFixed(1)}%` : 'N/A';
      if (elements.ovRecall) elements.ovRecall.textContent = r !== null ? `${(r * 100).toFixed(1)}%` : 'N/A';
      if (elements.ovF1) elements.ovF1.textContent = f !== null ? f.toFixed(3) : 'N/A';

      // Landing page metrics
      if (elements.landingPrecisionVal) elements.landingPrecisionVal.textContent = p !== null ? `${(p * 100).toFixed(1)}%` : '--';
      if (elements.landingRecallVal) elements.landingRecallVal.textContent = r !== null ? `${(r * 100).toFixed(1)}%` : '--';
      if (elements.landingF1Val) elements.landingF1Val.textContent = f !== null ? f.toFixed(3) : '--';
    }

    // Landing Page stats
    if (elements.landingStatScanned) elements.landingStatScanned.textContent = scanned;
    if (elements.landingStatCandidates) elements.landingStatCandidates.textContent = candidates;
    if (elements.landingStatGaps) elements.landingStatGaps.textContent = gaps;

    // Set connection status indicator to green
    if (elements.statusDot) {
      elements.statusDot.style.backgroundColor = 'var(--color-success)';
      elements.statusDot.style.boxShadow = '0 0 10px var(--color-success)';
    }
    if (elements.statusText) elements.statusText.textContent = 'API Connected';

  } catch (err) {
    console.error('Error loading summary:', err);
    if (elements.statusDot) {
      elements.statusDot.style.backgroundColor = 'var(--color-danger)';
      elements.statusDot.style.boxShadow = '0 0 10px var(--color-danger)';
    }
    if (elements.statusText) elements.statusText.textContent = 'API Disconnected';
  }
}

// B. Personal-Data Inventory
async function fetchInventory() {
  try {
    const res = await fetch('/api/inventory');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.inventory = data.records || [];
    renderInventory();
    renderClassDistribution();
    renderPriorityReviewQueue();
  } catch (err) {
    console.error('Error loading inventory:', err);
    if (elements.inventoryTableBody) {
      elements.inventoryTableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--color-danger); padding:2rem;">Failed to load inventory: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

function renderInventory() {
  if (!elements.inventoryTableBody) return;

  // Handle URL query parameters on initial load
  if (elements.invReviewFilter && !elements.invReviewFilter.dataset.paramChecked) {
    elements.invReviewFilter.dataset.paramChecked = 'true';
    const params = new URLSearchParams(window.location.search);
    if (params.get('filter') === 'review') {
      elements.invReviewFilter.value = 'true';
    }
    if (params.get('class') && elements.invClassFilter) {
      elements.invClassFilter.value = params.get('class');
    }
  }

  const q = (elements.invSearchInput?.value || '').toLowerCase().trim();
  const cls = elements.invClassFilter?.value || 'All';
  const stat = elements.invStatusFilter?.value || 'All';
  const rev = elements.invReviewFilter?.value || 'All';

  const filtered = state.inventory.filter(r => {
    if (q) {
      const match =
        r.field_name.toLowerCase().includes(q) ||
        r.source_name.toLowerCase().includes(q) ||
        (r.purpose && r.purpose.toLowerCase().includes(q)) ||
        (r.metadata_owner && r.metadata_owner.toLowerCase().includes(q)) ||
        (r.detected_class && r.detected_class.toLowerCase().includes(q));
      if (!match) return false;
    }
    if (cls !== 'All' && r.detected_class !== cls) return false;
    if (stat !== 'All' && r.overall_status !== stat) return false;
    if (rev === 'true' && !r.review_required) return false;
    if (rev === 'false' && r.review_required) return false;
    return true;
  });

  const totalItems = filtered.length;
  if (elements.inventoryCounter) {
    elements.inventoryCounter.textContent = `${totalItems} candidate fields`;
  }

  if (totalItems === 0) {
    elements.inventoryTableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:2.5rem;">No matching candidate fields found.</td></tr>`;
    if (elements.inventoryPagination) elements.inventoryPagination.innerHTML = '';
    return;
  }

  // Calculate pagination
  const pageSize = state.invPageSize === 'All' ? totalItems : parseInt(state.invPageSize, 10);
  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  if (state.invPage > totalPages) state.invPage = totalPages;
  if (state.invPage < 1) state.invPage = 1;

  const startIndex = (state.invPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalItems);
  const pageItems = filtered.slice(startIndex, endIndex);

  let rows = '';
  pageItems.forEach((r) => {
    // Find absolute index in state.inventory
    const originalIndex = state.inventory.findIndex(item => item === r);
    const safeReason = escapeHtml(r.detection_reason);
    const safeSourceName = escapeHtml(r.source_name);
    const safeFieldName = escapeHtml(r.field_name);
    const safePurpose = escapeHtml(r.purpose);
    const safeRetention = escapeHtml(r.retention_period);

    const revBadge = r.review_required
      ? `<span class="badge badge-review" title="${safeReason}">Review Required</span>`
      : `<span style="font-size:0.75rem; font-weight:600; color:var(--color-success);">Auto-Triage</span>`;

    const confVal = r.confidence ? r.confidence.toFixed(2) : '0.00';
    const confLevel = escapeHtml(r.confidence_level || 'Low');

    rows += `
      <tr>
        <td class="font-mono" style="font-size:0.78rem; color:var(--text-secondary);">${safeSourceName}</td>
        <td class="font-mono" style="font-weight:700; color:var(--accent-gold);">${safeFieldName}</td>
        <td>${getClassBadge(r.detected_class)}</td>
        <td>
          <span class="font-mono" style="font-weight:700;">${confVal}</span>
          <span style="font-size:0.72rem; color:var(--text-muted);">(${confLevel})</span>
        </td>
        <td>${revBadge}</td>
        <td style="max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${safePurpose || 'None declared'}">
          ${safePurpose ? safePurpose : '<span style="color:var(--text-muted); font-style:italic;">Not Declared</span>'}
        </td>
        <td style="max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${safeRetention || 'None declared'}">
          ${safeRetention ? safeRetention : '<span style="color:var(--text-muted); font-style:italic;">Not Declared</span>'}
        </td>
        <td>${getStatusBadge(r.overall_status)}</td>
        <td>
          <button class="btn btn-secondary" style="padding:0.25rem 0.6rem; font-size:0.75rem;" onclick="openFieldDetails(${originalIndex})">Details</button>
        </td>
      </tr>
    `;
  });
  elements.inventoryTableBody.innerHTML = rows;

  // Render pagination bar
  if (elements.inventoryPagination) {
    elements.inventoryPagination.innerHTML = `
      <div class="pagination-info">
        Showing <strong>${startIndex + 1}–${endIndex}</strong> of <strong>${totalItems}</strong> records
      </div>
      <div class="pagination-controls">
        <button class="pagination-btn" ${state.invPage <= 1 ? 'disabled' : ''} onclick="changeInvPage(${state.invPage - 1})">← Previous</button>
        <span style="font-size:0.82rem; font-weight:600; padding:0 0.5rem;">Page ${state.invPage} of ${totalPages}</span>
        <button class="pagination-btn" ${state.invPage >= totalPages ? 'disabled' : ''} onclick="changeInvPage(${state.invPage + 1})">Next →</button>
      </div>
      <div class="page-size-selector">
        <span>Per page:</span>
        <select class="select-input" style="padding:0.25rem 0.5rem; font-size:0.8rem; width:auto;" onchange="changeInvPageSize(this.value)">
          <option value="10" ${state.invPageSize === 10 ? 'selected' : ''}>10</option>
          <option value="25" ${state.invPageSize === 25 ? 'selected' : ''}>25</option>
          <option value="50" ${state.invPageSize === 50 ? 'selected' : ''}>50</option>
          <option value="All" ${state.invPageSize === 'All' ? 'selected' : ''}>All</option>
        </select>
      </div>
    `;
  }
}

// C. Overview: Technical Class Distribution Breakdown
function renderClassDistribution() {
  if (!elements.classDistributionList) return;

  const classCounts = {};
  state.inventory.forEach(r => {
    const c = r.detected_class || 'Unknown';
    classCounts[c] = (classCounts[c] || 0) + 1;
  });

  const total = state.inventory.length || 1;
  const classesOrder = ['Identity', 'Contact', 'Location', 'Financial', 'Sensitive/Health'];
  let html = '';

  classesOrder.forEach(cls => {
    const count = classCounts[cls] || 0;
    const pct = Math.round((count / total) * 100);
    const colorClass = cls === 'Identity' ? 'gold' : cls === 'Contact' ? 'orange' : cls === 'Location' ? 'emerald' : cls === 'Financial' ? 'amber' : 'rose';
    html += `
      <div>
        <div class="progress-item-header">
          <span>${getClassBadge(cls)}</span>
          <span class="font-mono" style="font-weight:700; color:var(--text-primary);">${count} <span style="color:var(--text-muted); font-size:0.75rem;">(${pct}%)</span></span>
        </div>
        <div class="progress-track">
          <div class="progress-fill ${colorClass}" style="width: ${pct}%;"></div>
        </div>
      </div>
    `;
  });

  elements.classDistributionList.innerHTML = html;
}

// D. Overview: Priority Human Review Queue
function renderPriorityReviewQueue() {
  if (!elements.priorityReviewList) return;

  const reviewItems = state.inventory.filter(r => r.review_required);
  if (elements.reviewQueueBadge) {
    elements.reviewQueueBadge.textContent = `${reviewItems.length} Pending Review`;
  }

  if (reviewItems.length === 0) {
    elements.priorityReviewList.innerHTML = `
      <div style="text-align:center; padding:1.5rem; color:var(--color-success); font-size:0.85rem;">
        ✔ All candidate fields passed automated high-confidence verification.
      </div>
    `;
    return;
  }

  let html = '';
  // Show up to 5 prioritized items on the overview
  reviewItems.slice(0, 5).forEach((item) => {
    const originalIndex = state.inventory.findIndex(r => r === item);
    const safeSource = escapeHtml(item.source_name);
    const safeField = escapeHtml(item.field_name);
    const confVal = item.confidence ? item.confidence.toFixed(2) : '0.00';

    html += `
      <div class="review-item-card">
        <div style="flex:1; min-width:0;">
          <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem;">
            <span class="font-mono" style="font-weight:700; color:var(--accent-gold); font-size:0.88rem;">${safeField}</span>
            <span class="font-mono" style="font-size:0.72rem; color:var(--text-muted);">in ${safeSource}</span>
            ${getClassBadge(item.detected_class)}
          </div>
          <div style="font-size:0.78rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
            ${escapeHtml(item.detection_reason || 'Borderline confidence score requires validation')}
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:0.75rem; flex-shrink:0;">
          <span class="font-mono" style="font-size:0.82rem; font-weight:700;">Conf: ${confVal}</span>
          <button class="btn btn-secondary-gold" style="padding:0.25rem 0.65rem; font-size:0.75rem;" onclick="openFieldDetails(${originalIndex})">Inspect</button>
        </div>
      </div>
    `;
  });

  if (reviewItems.length > 5) {
    html += `
      <div style="text-align:center; margin-top:0.5rem;">
        <a href="/inventory.html?filter=review" class="btn btn-secondary" style="font-size:0.78rem; padding:0.35rem 0.85rem; text-decoration:none; display:inline-block;">
          View all ${reviewItems.length} review required fields →
        </a>
      </div>
    `;
  }

  elements.priorityReviewList.innerHTML = html;
}

// E. Evidence Gaps
async function fetchGaps() {
  try {
    const res = await fetch('/api/gaps');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.gaps = data.gaps || [];
    renderGaps();
  } catch (err) {
    console.error('Error loading gaps:', err);
    if (elements.gapsTableBody) {
      elements.gapsTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--color-danger); padding:2rem;">Failed to load gaps: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

function renderGaps() {
  if (!elements.gapsTableBody) return;

  // Handle URL query parameters on initial load
  if (elements.gapsClassFilter && !elements.gapsClassFilter.dataset.paramChecked) {
    elements.gapsClassFilter.dataset.paramChecked = 'true';
    const params = new URLSearchParams(window.location.search);
    if (params.get('class')) {
      elements.gapsClassFilter.value = params.get('class');
    }
    if (params.get('status') && elements.gapsStatusFilter) {
      elements.gapsStatusFilter.value = params.get('status');
    }
  }

  const q = (elements.gapsSearchInput?.value || '').toLowerCase().trim();
  const stat = elements.gapsStatusFilter?.value || 'All';
  const cls = elements.gapsClassFilter?.value || 'All';

  const filtered = state.gaps.filter(g => {
    if (q) {
      const match =
        g.field_name.toLowerCase().includes(q) ||
        g.source_name.toLowerCase().includes(q) ||
        (g.evidence_note && g.evidence_note.toLowerCase().includes(q));
      if (!match) return false;
    }
    if (stat !== 'All' && g.overall_status !== stat) return false;
    if (cls !== 'All' && g.detected_class !== cls) return false;
    return true;
  });

  const totalItems = filtered.length;
  if (elements.gapsCounter) {
    elements.gapsCounter.textContent = `${totalItems} evidence gaps`;
  }

  if (totalItems === 0) {
    elements.gapsTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:2.5rem;">No matching evidence gaps found.</td></tr>`;
    if (elements.gapsPagination) elements.gapsPagination.innerHTML = '';
    return;
  }

  // Calculate pagination
  const pageSize = state.gapsPageSize === 'All' ? totalItems : parseInt(state.gapsPageSize, 10);
  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  if (state.gapsPage > totalPages) state.gapsPage = totalPages;
  if (state.gapsPage < 1) state.gapsPage = 1;

  const startIndex = (state.gapsPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalItems);
  const pageItems = filtered.slice(startIndex, endIndex);

  let rows = '';
  pageItems.forEach((g) => {
    const safeSourceName = escapeHtml(g.source_name);
    const safeFieldName = escapeHtml(g.field_name);
    const safeNote = escapeHtml(g.evidence_note);
    let missingStr = 'purpose, retention';
    if (Array.isArray(g.missing_items)) {
      missingStr = g.missing_items.length > 0 ? escapeHtml(g.missing_items.join(', ')) : 'purpose, retention';
    } else if (typeof g.missing_items === 'string' && g.missing_items.trim()) {
      missingStr = escapeHtml(g.missing_items.replace(/;/g, ', '));
    }

    rows += `
      <tr>
        <td class="font-mono" style="font-size:0.78rem; color:var(--text-secondary);">${safeSourceName}</td>
        <td class="font-mono" style="font-weight:700; color:var(--orange-primary);">${safeFieldName}</td>
        <td>${getClassBadge(g.detected_class)}</td>
        <td>${getStatusBadge(g.overall_status)}</td>
        <td class="font-mono" style="font-size:0.78rem; color:var(--color-warning);">${missingStr}</td>
        <td style="font-size:0.8rem; color:var(--text-secondary); max-width:280px; line-height:1.4;">${safeNote}</td>
        <td>
          <button class="btn btn-secondary" style="padding:0.25rem 0.6rem; font-size:0.75rem;" onclick="openGapDetails('${encodeURIComponent(g.source_name)}', '${encodeURIComponent(g.field_name)}')">Inspect</button>
        </td>
      </tr>
    `;
  });
  elements.gapsTableBody.innerHTML = rows;

  // Render pagination bar
  if (elements.gapsPagination) {
    elements.gapsPagination.innerHTML = `
      <div class="pagination-info">
        Showing <strong>${startIndex + 1}–${endIndex}</strong> of <strong>${totalItems}</strong> records
      </div>
      <div class="pagination-controls">
        <button class="pagination-btn" ${state.gapsPage <= 1 ? 'disabled' : ''} onclick="changeGapsPage(${state.gapsPage - 1})">← Previous</button>
        <span style="font-size:0.82rem; font-weight:600; padding:0 0.5rem;">Page ${state.gapsPage} of ${totalPages}</span>
        <button class="pagination-btn" ${state.gapsPage >= totalPages ? 'disabled' : ''} onclick="changeGapsPage(${state.gapsPage + 1})">Next →</button>
      </div>
      <div class="page-size-selector">
        <span>Per page:</span>
        <select class="select-input" style="padding:0.25rem 0.5rem; font-size:0.8rem; width:auto;" onchange="changeGapsPageSize(this.value)">
          <option value="10" ${state.gapsPageSize === 10 ? 'selected' : ''}>10</option>
          <option value="25" ${state.gapsPageSize === 25 ? 'selected' : ''}>25</option>
          <option value="50" ${state.gapsPageSize === 50 ? 'selected' : ''}>50</option>
          <option value="All" ${state.gapsPageSize === 'All' ? 'selected' : ''}>All</option>
        </select>
      </div>
    `;
  }
}

// Global Pagination Handlers
window.changeInvPage = function(page) {
  state.invPage = page;
  renderInventory();
};

window.changeInvPageSize = function(size) {
  state.invPageSize = size === 'All' ? 'All' : parseInt(size, 10);
  state.invPage = 1;
  renderInventory();
};

window.changeGapsPage = function(page) {
  state.gapsPage = page;
  renderGaps();
};

window.changeGapsPageSize = function(size) {
  state.gapsPageSize = size === 'All' ? 'All' : parseInt(size, 10);
  state.gapsPage = 1;
  renderGaps();
};

// Interactive Rule Sandbox Tester
window.testInteractiveRule = function() {
  const colInput = document.getElementById('ruleTestColName');
  const valInput = document.getElementById('ruleTestSampleVal');
  const resultContainer = document.getElementById('ruleTestResult');
  if (!colInput || !resultContainer) return;

  const colName = (colInput.value || '').trim();
  const sampleVal = (valInput ? valInput.value : '').trim();

  if (!colName) {
    resultContainer.innerHTML = '<div style="color:var(--color-warning); font-size:0.85rem;">Please enter a column or field name to evaluate.</div>';
    return;
  }

  if (!state.rules || !state.rules.classes) {
    resultContainer.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">Rules are loading, please try in a moment...</div>';
    return;
  }

  // Tokenize column name (handle camelCase, snake_case, kebab-case)
  const normalized = colName.replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase();
  const tokens = normalized.split(/[_\-\s]+/).filter(Boolean);

  let bestMatch = null;
  let highestScore = 0;

  for (const [clsName, conf] of Object.entries(state.rules.classes)) {
    let kwScore = 0;
    let matchType = null;
    let matchedKw = null;

    const keywords = conf.keywords || [];
    for (const kw of keywords) {
      const kwNorm = kw.toLowerCase();
      if (normalized === kwNorm) {
        kwScore = 0.70;
        matchType = 'Exact match';
        matchedKw = kw;
        break;
      }
      if (tokens.includes(kwNorm) && kwScore < 0.60) {
        kwScore = 0.60;
        matchType = 'Token match';
        matchedKw = kw;
      } else if (normalized.includes(kwNorm) && kwScore < 0.30) {
        kwScore = 0.30;
        matchType = 'Substring match';
        matchedKw = kw;
      }
    }

    // Pattern test if sample value provided
    let patScore = 0;
    let matchedPatName = null;
    if (sampleVal && conf.patterns) {
      for (const pat of conf.patterns) {
        try {
          const reg = new RegExp(pat.regex, 'i');
          if (reg.test(sampleVal)) {
            patScore = 0.30;
            matchedPatName = pat.name;
            break;
          }
        } catch (e) {}
      }
    }

    const totalConf = Math.min(1.0, kwScore + patScore);
    if (totalConf > highestScore) {
      highestScore = totalConf;
      bestMatch = {
        className: clsName,
        confidence: totalConf,
        matchType: matchType,
        matchedKw: matchedKw,
        matchedPatName: matchedPatName,
      };
    }
  }

  if (!bestMatch || highestScore < 0.20) {
    resultContainer.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:var(--radius-md); padding:1rem; display:flex; align-items:center; gap:0.75rem;">
        <span style="font-size:1.25rem;">⚪</span>
        <div>
          <div style="font-weight:700; color:var(--text-secondary); font-size:0.9rem;">Not Classified as Personal Data</div>
          <div style="font-size:0.78rem; color:var(--text-muted); margin-top:0.2rem;">Score: 0.00 &bull; Column '${escapeHtml(colName)}' did not match configured technical keywords or patterns.</div>
        </div>
      </div>
    `;
    return;
  }

  const confLevel = highestScore >= 0.75 ? 'High' : highestScore >= 0.45 ? 'Medium' : 'Low';
  const triageFlag = highestScore < 0.75 ? '<span class="badge badge-review">Review Required</span>' : '<span style="color:var(--color-success); font-weight:700;">Auto-Triage</span>';

  resultContainer.innerHTML = `
    <div style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:var(--radius-md); padding:1.2rem; display:flex; flex-direction:column; gap:0.65rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
        <div style="display:flex; align-items:center; gap:0.65rem;">
          ${getClassBadge(bestMatch.className)}
          <span style="font-weight:700; font-size:0.95rem;">Score: ${highestScore.toFixed(2)} (${confLevel} Confidence)</span>
        </div>
        ${triageFlag}
      </div>
      <div style="font-size:0.82rem; color:var(--text-secondary); line-height:1.5;">
        ${bestMatch.matchType ? `Matched keyword <strong style="color:var(--accent-gold);">${escapeHtml(bestMatch.matchedKw)}</strong> (${bestMatch.matchType})` : ''}
        ${bestMatch.matchedPatName ? ` &bull; Sample value confirmed by regex pattern <strong style="color:var(--color-success);">${escapeHtml(bestMatch.matchedPatName)}</strong>` : ''}
      </div>
    </div>
  `;
};

// F. Ground-Truth Evaluation
async function fetchEvaluation() {
  try {
    const res = await fetch('/api/evaluation');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.evaluation = data;

    // 1. Detection Binary Metrics
    const dm = data.detection_metrics || {};
    if (elements.detPrecision) elements.detPrecision.textContent = dm.precision !== null ? `${(dm.precision * 100).toFixed(1)}%` : 'N/A';
    if (elements.detRecall) elements.detRecall.textContent = dm.recall !== null ? `${(dm.recall * 100).toFixed(1)}%` : 'N/A';
    if (elements.detF1) elements.detF1.textContent = dm.f1 !== null ? dm.f1.toFixed(3) : 'N/A';
    if (elements.detCounts) elements.detCounts.textContent = `TP: ${dm.tp} | FP: ${dm.fp} | FN: ${dm.fn} | TN: ${dm.tn}`;

    // 2. Per-Class Table
    const perClass = data.per_class_metrics || [];
    let pRows = '';
    perClass.forEach(m => {
      const prec = m.precision !== null ? m.precision.toFixed(3) : 'N/A';
      const rec = m.recall !== null ? m.recall.toFixed(3) : 'N/A';
      const f1 = m.f1 !== null ? m.f1.toFixed(3) : 'N/A';
      const isLimited = m.status && m.status.includes('Limited Sample');
      const statusNote = isLimited
        ? `<span class="badge badge-review">${escapeHtml(m.status)}</span>`
        : `<span style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(m.status)}</span>`;

      pRows += `
        <tr>
          <td>${getClassBadge(m.class_name)}</td>
          <td class="font-mono">${m.tp}</td>
          <td class="font-mono">${m.fp}</td>
          <td class="font-mono">${m.fn}</td>
          <td class="font-mono" style="font-weight:700;">${m.support}</td>
          <td class="font-mono" style="color:var(--accent-gold); font-weight:600;">${prec}</td>
          <td class="font-mono" style="color:var(--color-success); font-weight:600;">${rec}</td>
          <td class="font-mono" style="font-weight:800; color:var(--orange-primary);">${f1}</td>
          <td>${statusNote}</td>
        </tr>
      `;
    });
    if (elements.perClassTableBody) elements.perClassTableBody.innerHTML = pRows;

    // 3. Confusion Matrix
    const cm = data.confusion_matrix || {};
    const rowKeys = Object.keys(cm);
    if (rowKeys.length > 0 && elements.cmHeaderRow && elements.cmBody) {
      const colKeys = Object.keys(cm[rowKeys[0]]);
      let headerHtml = '<th>Expected ↓ / Pred →</th>';
      colKeys.forEach(col => {
        headerHtml += `<th style="text-align:center;">${escapeHtml(col)}</th>`;
      });
      elements.cmHeaderRow.innerHTML = headerHtml;

      let cmRows = '';
      rowKeys.forEach(rKey => {
        cmRows += `<tr><td style="font-weight:700; color:var(--text-secondary);">${escapeHtml(rKey)}</td>`;
        colKeys.forEach(cKey => {
          const val = cm[rKey][cKey] || 0;
          const isDiagonal = rKey === cKey || (rKey === 'Non-PII' && cKey === 'Not Detected');
          let cellClass = '';
          if (isDiagonal && val > 0) cellClass = 'cm-correct';
          else if (!isDiagonal && val > 0) cellClass = 'cm-error';

          cmRows += `<td class="font-mono ${cellClass}" style="text-align:center;">${val}</td>`;
        });
        cmRows += '</tr>';
      });
      elements.cmBody.innerHTML = cmRows;
    }

    // 4. Discrepancies & Errors List
    const errors = data.detailed_errors || [];
    if (elements.errorCountBadge) elements.errorCountBadge.textContent = errors.length;
    if (elements.errorListContainer) {
      if (errors.length === 0) {
        elements.errorListContainer.innerHTML = `<div style="color:var(--color-success); font-size:0.85rem; padding:1rem;">✔ Zero classification discrepancies observed across all evaluated fields.</div>`;
      } else {
        let errHtml = '';
        errors.forEach((e) => {
          errHtml += `
            <div style="background:var(--bg-elevated); border:1px solid var(--border-color); padding:0.85rem 1rem; border-radius:var(--radius-md); margin-bottom:0.75rem;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                <span class="font-mono" style="font-weight:700; color:var(--accent-gold); font-size:0.85rem;">${escapeHtml(e.source_name)} → ${escapeHtml(e.field_name)}</span>
                <span class="badge badge-status-both-miss" style="font-size:0.72rem;">${escapeHtml(e.error_type)}</span>
              </div>
              <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:0.25rem;">
                <strong>Expected:</strong> <span class="badge">${escapeHtml(e.expected_class || 'Non-PII')}</span> &nbsp;|&nbsp; 
                <strong>Predicted:</strong> <span class="badge badge-class-contact">${escapeHtml(e.predicted_class || 'Not Detected')}</span> 
                <span class="font-mono" style="color:var(--text-muted); font-size:0.75rem;">(Conf: ${e.confidence || '0.00'})</span>
              </div>
              <div style="font-size:0.75rem; color:var(--text-muted); font-style:italic; line-height:1.4;">
                ${escapeHtml(e.reason || 'No reasoning captured.')}
              </div>
            </div>
          `;
        });
        elements.errorListContainer.innerHTML = errHtml;
      }
    }

  } catch (err) {
    console.error('Error loading evaluation:', err);
  }
}

// G. Detection Rules
async function fetchRules() {
  try {
    const res = await fetch('/api/rules');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.rules = data;

    const classes = data.classes || {};
    let html = '';

    for (const [clsName, conf] of Object.entries(classes)) {
      const keywords = (conf.keywords || []).slice(0, 15).join(', ');
      const moreKw = conf.keywords && conf.keywords.length > 15 ? ` + ${conf.keywords.length - 15} more` : '';
      const patterns = (conf.patterns || []).map(p => `<code style="background:var(--bg-subtle); padding:0.15rem 0.4rem; border-radius:4px;">${escapeHtml(p.name)}</code> (${escapeHtml(p.regex)})`).join(', ') || 'None';

      html += `
        <div style="background:var(--bg-elevated); border:1px solid var(--border-color); padding:1.25rem; border-radius:var(--radius-md);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.65rem;">
            <div style="display:flex; align-items:center; gap:0.65rem;">
              ${getClassBadge(clsName)}
              <span style="font-size:0.85rem; color:var(--text-secondary); font-weight:600;">${escapeHtml(conf.description || '')}</span>
            </div>
            <span class="badge" style="background:var(--bg-card); color:var(--accent-gold); font-family:var(--font-mono);">${(conf.keywords || []).length} keywords</span>
          </div>
          <div style="font-size:0.82rem; margin-bottom:0.45rem;">
            <strong style="color:var(--text-muted);">Keywords:</strong> <span class="font-mono" style="color:var(--text-secondary);">${escapeHtml(keywords)}${moreKw}</span>
          </div>
          <div style="font-size:0.82rem;">
            <strong style="color:var(--text-muted);">Regex Patterns:</strong> <span class="font-mono" style="color:var(--accent-gold);">${patterns}</span>
          </div>
        </div>
      `;
    }
    if (elements.rulesContainer) elements.rulesContainer.innerHTML = html;
  } catch (err) {
    console.error('Error loading rules:', err);
    if (elements.rulesContainer) {
      elements.rulesContainer.innerHTML = `<div style="color:var(--color-danger); font-size:0.85rem;">Failed to load rules: ${escapeHtml(err.message)}</div>`;
    }
  }
}

// ---------------------------------------------------------------------------
// 8. Field Detail Modal Inspector
// ---------------------------------------------------------------------------
window.openFieldDetails = function(idx) {
  const item = state.inventory[idx];
  if (!item || !elements.detailModal) return;

  const safeSourceName = escapeHtml(item.source_name);
  const safeFieldName = escapeHtml(item.field_name);
  const safeSourceType = escapeHtml(item.source_type);
  const safePurpose = escapeHtml(item.purpose);
  const safeRetention = escapeHtml(item.retention_period);
  const safeOwner = escapeHtml(item.metadata_owner);
  const safeReason = escapeHtml(item.detection_reason);
  const safeNote = escapeHtml(item.evidence_note);
  let missingStr = 'None (Fully Documented)';
  if (Array.isArray(item.missing_items)) {
    missingStr = item.missing_items.length > 0 ? escapeHtml(item.missing_items.join(', ')) : 'None (Fully Documented)';
  } else if (typeof item.missing_items === 'string' && item.missing_items.trim()) {
    missingStr = escapeHtml(item.missing_items.replace(/;/g, ', '));
  }

  if (elements.modalFieldTitle) {
    elements.modalFieldTitle.textContent = `${item.source_name} → ${item.field_name}`;
  }

  if (elements.modalDetailsBody) {
    elements.modalDetailsBody.innerHTML = `
      <div class="detail-row"><div class="detail-label">Source Type</div><div class="detail-value font-mono">${safeSourceType}</div></div>
      <div class="detail-row"><div class="detail-label">Source Asset</div><div class="detail-value font-mono">${safeSourceName}</div></div>
      <div class="detail-row"><div class="detail-label">Field Name</div><div class="detail-value font-mono" style="color:var(--accent-gold); font-weight:700;">${safeFieldName}</div></div>
      <div class="detail-row"><div class="detail-label">Detected Class</div><div class="detail-value">${getClassBadge(item.detected_class)}</div></div>
      <div class="detail-row"><div class="detail-label">Confidence Score</div><div class="detail-value font-mono" style="font-weight:700;">${item.confidence ? item.confidence.toFixed(4) : '0.00'} (${escapeHtml(item.confidence_level)})</div></div>
      <div class="detail-row"><div class="detail-label">Triage Flag</div><div class="detail-value">${item.review_required ? '<span class="badge badge-review">Human Review Required</span>' : '<span style="color:var(--color-success); font-weight:600;">Automated High-Confidence</span>'}</div></div>
      <div class="detail-row"><div class="detail-label">Declared Purpose</div><div class="detail-value">${safePurpose || '<em style="color:var(--text-muted);">Not declared (Evidence Gap)</em>'}</div></div>
      <div class="detail-row"><div class="detail-label">Retention Period</div><div class="detail-value">${safeRetention || '<em style="color:var(--text-muted);">Not declared (Evidence Gap)</em>'}</div></div>
      <div class="detail-row"><div class="detail-label">Metadata Owner</div><div class="detail-value">${safeOwner || '<em style="color:var(--text-muted);">Unassigned Governance Owner</em>'}</div></div>
      <div class="detail-row"><div class="detail-label">Governance Status</div><div class="detail-value">${getStatusBadge(item.overall_status)}</div></div>
      <div class="detail-row"><div class="detail-label">Missing Metadata</div><div class="detail-value font-mono" style="color:var(--color-warning);">${missingStr}</div></div>
      <div class="detail-row"><div class="detail-label">Detection Reason</div><div class="detail-value" style="font-size:0.8rem; color:var(--text-secondary); background:var(--bg-elevated); padding:0.6rem 0.85rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">${safeReason || 'N/A'}</div></div>
      <div class="detail-row"><div class="detail-label">Governance Note</div><div class="detail-value" style="font-size:0.8rem; color:var(--text-secondary); background:var(--bg-elevated); padding:0.6rem 0.85rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">${safeNote || 'N/A'}</div></div>
    `;
  }
  elements.detailModal.classList.add('active');
};

window.openGapDetails = function(sourceName, fieldName) {
  const decSource = decodeURIComponent(sourceName);
  const decField = decodeURIComponent(fieldName);
  const idx = state.inventory.findIndex(r => r.source_name === decSource && r.field_name === decField);
  if (idx !== -1) {
    window.openFieldDetails(idx);
  }
};

function closeModal() {
  if (elements.detailModal) elements.detailModal.classList.remove('active');
}

// ---------------------------------------------------------------------------
// 9. Actions: Run Full Scan & Run Pipeline
// ---------------------------------------------------------------------------
async function handleRunScan() {
  if (!elements.btnRunScan) return;
  elements.btnRunScan.disabled = true;
  elements.scanBtnLabel.textContent = 'Scanning Data...';
  elements.scanBtnIcon.innerHTML = '<span class="spinner"></span>';

  try {
    const res = await fetch('/api/scan', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(`Scan complete: ${data.detected_candidates_count} candidates discovered across ${data.scanned_fields_count} fields.`, 'success');
    await refreshAll();
  } catch (err) {
    console.error('Scan error:', err);
    showToast(`Scan failed: ${err.message}`, 'error');
  } finally {
    elements.btnRunScan.disabled = false;
    elements.scanBtnLabel.textContent = 'Run Full Scan';
    elements.scanBtnIcon.textContent = '▶';
  }
}

async function handleRunAnalyze() {
  if (!elements.btnRunAnalyze) return;
  elements.btnRunAnalyze.disabled = true;
  const originalHtml = elements.btnRunAnalyze.innerHTML;
  elements.btnRunAnalyze.innerHTML = '<span class="spinner"></span> <span>Running Pipeline...</span>';

  try {
    const res = await fetch('/api/analyze', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(`Pipeline complete: ${data.inventory_count} inventory records, ${data.total_gaps_count} evidence gaps evaluated.`, 'success');
    await refreshAll();
  } catch (err) {
    console.error('Analysis error:', err);
    showToast(`Pipeline failed: ${err.message}`, 'error');
  } finally {
    elements.btnRunAnalyze.disabled = false;
    elements.btnRunAnalyze.innerHTML = originalHtml;
  }
}

async function refreshAll() {
  await Promise.all([
    fetchSummary(),
    fetchInventory(),
    fetchGaps(),
    fetchEvaluation(),
    fetchRules(),
  ]);
}

// ---------------------------------------------------------------------------
// 10. Event Listeners Setup
// ---------------------------------------------------------------------------
function initEvents() {
  initTheme();
  initSidebar();
  initTabs();

  // Action Buttons
  if (elements.btnRunScan) elements.btnRunScan.addEventListener('click', handleRunScan);
  if (elements.btnRunAnalyze) elements.btnRunAnalyze.addEventListener('click', handleRunAnalyze);

  // Modal Close
  if (elements.modalCloseBtn) elements.modalCloseBtn.addEventListener('click', closeModal);
  if (elements.modalCloseBtnFooter) elements.modalCloseBtnFooter.addEventListener('click', closeModal);
  if (elements.detailModal) {
    elements.detailModal.addEventListener('click', (e) => {
      if (e.target === elements.detailModal) closeModal();
    });
  }

  // Keyboard accessibility: Escape to close modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  // Inventory Filters
  if (elements.invSearchInput) elements.invSearchInput.addEventListener('input', renderInventory);
  if (elements.invClassFilter) elements.invClassFilter.addEventListener('change', renderInventory);
  if (elements.invStatusFilter) elements.invStatusFilter.addEventListener('change', renderInventory);
  if (elements.invReviewFilter) elements.invReviewFilter.addEventListener('change', renderInventory);
  if (elements.btnResetInvFilter) {
    elements.btnResetInvFilter.addEventListener('click', () => {
      if (elements.invSearchInput) elements.invSearchInput.value = '';
      if (elements.invClassFilter) elements.invClassFilter.value = 'All';
      if (elements.invStatusFilter) elements.invStatusFilter.value = 'All';
      if (elements.invReviewFilter) elements.invReviewFilter.value = 'All';
      renderInventory();
      showToast('Inventory filters reset', 'info');
    });
  }

  // Evidence Gaps Filters
  if (elements.gapsSearchInput) elements.gapsSearchInput.addEventListener('input', renderGaps);
  if (elements.gapsStatusFilter) elements.gapsStatusFilter.addEventListener('change', renderGaps);
  if (elements.gapsClassFilter) elements.gapsClassFilter.addEventListener('change', renderGaps);
}

// ---------------------------------------------------------------------------
// 11. Authentication & User Session Management
// ---------------------------------------------------------------------------
const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

function setupPasswordToggle(btnId, inputId, iconId) {
  const btn = document.getElementById(btnId);
  const input = document.getElementById(inputId);
  const icon = document.getElementById(iconId);
  if (!btn || !input) return;

  btn.addEventListener('click', () => {
    const isPassword = input.getAttribute('type') === 'password';
    input.setAttribute('type', isPassword ? 'text' : 'password');
    if (icon) {
      icon.textContent = isPassword ? '🙈' : '👁️';
    }
  });
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById('authAlert');
  const alertMsg = document.getElementById('alertMessage');
  const emailInput = document.getElementById('loginEmail');
  const passwordInput = document.getElementById('loginPassword');
  const rememberCheckbox = document.getElementById('rememberMe');
  const submitBtn = document.getElementById('btnSubmitLogin');
  const spinner = document.getElementById('btnSubmitSpinner');
  const submitText = document.getElementById('btnSubmitText');
  const emailErr = document.getElementById('emailError');
  const passErr = document.getElementById('passwordError');

  // Reset errors
  if (alertBox) alertBox.classList.remove('show');
  if (emailErr) emailErr.classList.remove('visible');
  if (passErr) passErr.classList.remove('visible');

  const email = emailInput ? emailInput.value.trim() : '';
  const password = passwordInput ? passwordInput.value : '';
  const rememberMe = rememberCheckbox ? rememberCheckbox.checked : false;

  let hasError = false;
  if (!email || !EMAIL_REGEX.test(email)) {
    if (emailErr) emailErr.classList.add('visible');
    hasError = true;
  }
  if (!password) {
    if (passErr) passErr.classList.add('visible');
    hasError = true;
  }
  if (hasError) return;

  // Set loading state
  if (submitBtn) submitBtn.disabled = true;
  if (spinner) spinner.style.display = 'inline-block';
  if (submitText) submitText.textContent = 'Signing in...';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, remember_me: rememberMe })
    });
    const data = await res.json();
    if (!res.ok) {
      const errMsg = data.detail || 'Invalid email or password. Please verify your credentials.';
      if (alertBox && alertMsg) {
        alertMsg.textContent = errMsg;
        alertBox.className = 'auth-alert auth-alert-error show';
      }
      return;
    }

    // Success! Redirect to intended destination or /workspace
    const params = new URLSearchParams(window.location.search);
    let target = params.get('redirect') || '/workspace';
    if (!target.startsWith('/') || target.startsWith('//')) {
      target = '/workspace';
    }
    window.location.href = target;
  } catch (err) {
    if (alertBox && alertMsg) {
      alertMsg.textContent = 'Connection error. Please check your network and try again.';
      alertBox.className = 'auth-alert auth-alert-error show';
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (spinner) spinner.style.display = 'none';
    if (submitText) submitText.textContent = 'Sign In';
  }
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById('authAlert');
  const alertMsg = document.getElementById('alertMessage');
  const nameInput = document.getElementById('regFullName');
  const emailInput = document.getElementById('regEmail');
  const passwordInput = document.getElementById('regPassword');
  const confirmInput = document.getElementById('regConfirmPassword');
  const submitBtn = document.getElementById('btnSubmitRegister');
  const spinner = document.getElementById('btnSubmitSpinner');
  const submitText = document.getElementById('btnSubmitText');
  const nameErr = document.getElementById('nameError');
  const emailErr = document.getElementById('emailError');
  const passErr = document.getElementById('passwordError');
  const confirmErr = document.getElementById('confirmPasswordError');

  // Reset errors
  if (alertBox) alertBox.classList.remove('show');
  if (nameErr) nameErr.classList.remove('visible');
  if (emailErr) emailErr.classList.remove('visible');
  if (passErr) passErr.classList.remove('visible');
  if (confirmErr) confirmErr.classList.remove('visible');

  const fullName = nameInput ? nameInput.value.trim() : '';
  const email = emailInput ? emailInput.value.trim() : '';
  const password = passwordInput ? passwordInput.value : '';
  const confirmPassword = confirmInput ? confirmInput.value : '';

  let hasError = false;
  if (!fullName || fullName.length < 2) {
    if (nameErr) nameErr.classList.add('visible');
    hasError = true;
  }
  if (!email || !EMAIL_REGEX.test(email)) {
    if (emailErr) emailErr.classList.add('visible');
    hasError = true;
  }
  if (!password || password.length < 8) {
    if (passErr) passErr.classList.add('visible');
    hasError = true;
  }
  if (password !== confirmPassword) {
    if (confirmErr) confirmErr.classList.add('visible');
    hasError = true;
  }
  if (hasError) return;

  // Set loading state
  if (submitBtn) submitBtn.disabled = true;
  if (spinner) spinner.style.display = 'inline-block';
  if (submitText) submitText.textContent = 'Creating Account...';

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name: fullName, email, password })
    });
    const data = await res.json();
    if (!res.ok) {
      const errMsg = data.detail || 'Registration failed. Please check your details.';
      if (alertBox && alertMsg) {
        alertMsg.textContent = errMsg;
        alertBox.className = 'auth-alert auth-alert-error show';
      }
      return;
    }

    // Success! Redirect to workspace
    if (alertBox && alertMsg) {
      alertMsg.textContent = 'Account created successfully! Redirecting to workspace...';
      alertBox.className = 'auth-alert auth-alert-success show';
    }
    setTimeout(() => {
      window.location.href = '/workspace';
    }, 500);
  } catch (err) {
    if (alertBox && alertMsg) {
      alertMsg.textContent = 'Connection error. Please check your network and try again.';
      alertBox.className = 'auth-alert auth-alert-error show';
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (spinner) spinner.style.display = 'none';
    if (submitText) submitText.textContent = 'Create Account';
  }
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {
    console.error('Logout error:', e);
  }
  window.location.href = '/login';
}

async function checkCurrentUser() {
  try {
    const res = await fetch('/api/auth/me');
    if (!res.ok) {
      // If unauthenticated on a protected dashboard page, automatically redirect to login
      const isAuthPage = document.getElementById('loginForm') || document.getElementById('registerForm');
      if (!isAuthPage) {
        const currentPath = window.location.pathname;
        if (currentPath !== '/login' && currentPath !== '/register' && currentPath !== '/404') {
          window.location.href = '/login?redirect=' + encodeURIComponent(currentPath);
        }
      }
      return null;
    }
    const data = await res.json();
    if (data.authenticated && data.user) {
      state.currentUser = data.user;
      renderUserHeader(data.user);
      return data.user;
    }
    if (data.email) {
      state.currentUser = data;
      renderUserHeader(data);
      return data;
    }
  } catch (e) {
    console.warn('Auth status check skipped:', e);
  }
  return null;
}

function renderUserHeader(user) {
  const headerRight = document.querySelector('.header-right');
  if (headerRight && !document.getElementById('userProfileBadge')) {
    const profileWrap = document.createElement('div');
    profileWrap.className = 'user-profile-badge';
    profileWrap.id = 'userProfileBadge';
    const initial = (user.full_name || 'U').charAt(0).toUpperCase();
    profileWrap.innerHTML = `
      <span class="user-avatar-circle">${initial}</span>
      <span style="font-weight: 600; font-size: 0.8rem;">${escapeHtml(user.full_name)}</span>
      <button class="btn-signout" id="headerSignOutBtn" title="Sign Out">Sign Out</button>
    `;
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) {
      headerRight.insertBefore(profileWrap, themeBtn);
    } else {
      headerRight.appendChild(profileWrap);
    }
    const signOutBtn = document.getElementById('headerSignOutBtn');
    if (signOutBtn) {
      signOutBtn.addEventListener('click', handleLogout);
    }
  }
}

function initForgotPasswordModal() {
  const forgotBtn = document.getElementById('forgotPasswordBtn');
  const modal = document.getElementById('forgotPasswordModal');
  const closeBtn = document.getElementById('closeForgotModalBtn');
  const cancelBtn = document.getElementById('cancelForgotBtn');
  const sendBtn = document.getElementById('btnSendResetInstructions');
  const emailInput = document.getElementById('forgotEmail');
  const alertBox = document.getElementById('forgotAlert');
  const alertMsg = document.getElementById('forgotAlertMsg');
  const devSection = document.getElementById('devResetSection');
  const tokenInput = document.getElementById('resetTokenInput');
  const newPassInput = document.getElementById('newPasswordInput');
  const submitResetBtn = document.getElementById('btnSubmitReset');

  if (!forgotBtn || !modal) return;

  function openForgotModal() {
    modal.classList.add('show');
    if (alertBox) alertBox.classList.remove('show');
    if (devSection) devSection.style.display = 'none';
    if (emailInput) {
      const loginEmail = document.getElementById('loginEmail');
      emailInput.value = loginEmail ? loginEmail.value.trim() : '';
      emailInput.focus();
    }
  }

  function closeForgotModal() {
    modal.classList.remove('show');
  }

  forgotBtn.addEventListener('click', (e) => {
    e.preventDefault();
    openForgotModal();
  });
  if (closeBtn) closeBtn.addEventListener('click', closeForgotModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeForgotModal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeForgotModal();
  });

  if (sendBtn) {
    sendBtn.addEventListener('click', async () => {
      const email = emailInput ? emailInput.value.trim() : '';
      if (!email || !EMAIL_REGEX.test(email)) {
        if (alertBox && alertMsg) {
          alertMsg.textContent = 'Please enter a valid email address.';
          alertBox.className = 'auth-alert auth-alert-error show';
        }
        return;
      }

      sendBtn.disabled = true;
      sendBtn.textContent = 'Sending...';

      try {
        const res = await fetch('/api/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (alertBox && alertMsg) {
          alertMsg.textContent = data.message || 'Reset instructions sent.';
          alertBox.className = 'auth-alert auth-alert-success show';
        }
        if (data.dev_token_available && devSection) {
          devSection.style.display = 'block';
        }
      } catch (err) {
        if (alertBox && alertMsg) {
          alertMsg.textContent = 'Unable to contact server. Please try again.';
          alertBox.className = 'auth-alert auth-alert-error show';
        }
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send Instructions';
      }
    });
  }

  if (submitResetBtn) {
    submitResetBtn.addEventListener('click', async () => {
      const token = tokenInput ? tokenInput.value.trim() : '';
      const newPassword = newPassInput ? newPassInput.value : '';
      if (!token) {
        alert('Please enter the reset token.');
        return;
      }
      if (!newPassword || newPassword.length < 8) {
        alert('New password must be at least 8 characters long.');
        return;
      }

      submitResetBtn.disabled = true;
      submitResetBtn.textContent = 'Resetting...';

      try {
        const res = await fetch('/api/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, new_password: newPassword })
        });
        const data = await res.json();
        if (!res.ok) {
          alert(data.detail || 'Reset failed.');
          return;
        }
        alert('Password has been reset successfully! Please sign in with your new password.');
        closeForgotModal();
        const pwdInput = document.getElementById('loginPassword');
        if (pwdInput) pwdInput.value = '';
      } catch (err) {
        alert('Error resetting password. Please try again.');
      } finally {
        submitResetBtn.disabled = false;
        submitResetBtn.textContent = 'Apply New Password';
      }
    });
  }
}

function initAuthPages() {
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');

  if (loginForm) {
    loginForm.addEventListener('submit', handleLoginSubmit);
    setupPasswordToggle('togglePasswordBtn', 'loginPassword', 'togglePasswordIcon');
    initForgotPasswordModal();
  }

  if (registerForm) {
    registerForm.addEventListener('submit', handleRegisterSubmit);
    setupPasswordToggle('toggleRegPasswordBtn', 'regPassword', 'toggleRegPasswordIcon');
    setupPasswordToggle('toggleConfirmPasswordBtn', 'regConfirmPassword', 'toggleConfirmPasswordIcon');
  }
}

// Bootstrap on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initTheme();

  const isAuthPage = document.getElementById('loginForm') || document.getElementById('registerForm');
  if (isAuthPage) {
    initAuthPages();
  } else {
    initEvents();
    checkCurrentUser();
    refreshAll();
  }
});

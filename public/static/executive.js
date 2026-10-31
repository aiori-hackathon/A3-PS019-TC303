/**
 * frontend/executive.js
 * =====================
 * Frontend controller for Phase 5.2 - 5.7 Executive Intelligence Dashboard:
 * - Module 5.2: Intelligent Risk Assessment Explorer
 * - Module 5.3: AI Recommendations Action Board
 * - Module 5.4: Compliance & ROPA Intelligence
 * - Module 5.5: Continuous Monitoring Alerts Management
 * - Module 5.6: Executive Dashboard & Posture KPIs
 */

(function() {
  'use strict';

  // Global State
  let currentDashboardData = null;
  let currentRiskSnapshot = null;
  let currentRecommendations = [];
  let currentAlerts = [];
  let selectedRecId = null;
  let selectedAlertId = null;

  // DOM Elements
  const subtabBtns = document.querySelectorAll('.lineage-subtab-btn');
  const tabPanels = document.querySelectorAll('.enterprise-tab-panel');
  const btnRefresh = document.getElementById('btnRefreshEnterprise');

  // Modal Elements
  const recModal = document.getElementById('recModalBackdrop');
  const recModalTitle = document.getElementById('recModalTitle');
  const recModalDesc = document.getElementById('recModalDesc');
  const recModalStatusSelect = document.getElementById('recModalStatusSelect');
  const recModalNotes = document.getElementById('recModalNotes');
  const btnCancelRecModal = document.getElementById('btnCancelRecModal');
  const btnSubmitRecModal = document.getElementById('btnSubmitRecModal');

  const alertModal = document.getElementById('alertModalBackdrop');
  const alertModalMessage = document.getElementById('alertModalMessage');
  const alertModalNotes = document.getElementById('alertModalNotes');
  const btnCancelAlertModal = document.getElementById('btnCancelAlertModal');
  const btnSubmitAlertModal = document.getElementById('btnSubmitAlertModal');
  const btnSyncAlerts = document.getElementById('btnSyncAlerts');
  const btnExportROPA = document.getElementById('btnExportROPA');

  // Filters
  const riskSeverityFilter = document.getElementById('riskSeverityFilter');
  const riskFieldSearch = document.getElementById('riskFieldSearch');
  const recStatusFilter = document.getElementById('recStatusFilter');

  // Initialize
  document.addEventListener('DOMContentLoaded', init);

  function init() {
    setupTabSwitching();
    setupEventListeners();
    fetchAllEnterpriseData();
  }

  function setupTabSwitching() {
    subtabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        subtabBtns.forEach(b => b.classList.remove('active'));
        tabPanels.forEach(p => {
          p.classList.remove('active');
          p.style.display = 'none';
        });

        btn.classList.add('active');
        const targetId = btn.getAttribute('data-tab');
        const targetPanel = document.getElementById(targetId);
        if (targetPanel) {
          targetPanel.classList.add('active');
          targetPanel.style.display = 'block';
        }
      });
    });
  }

  function setupEventListeners() {
    if (btnRefresh) {
      btnRefresh.addEventListener('click', fetchAllEnterpriseData);
    }

    if (btnSyncAlerts) {
      btnSyncAlerts.addEventListener('click', syncAlertsNow);
    }

    if (btnExportROPA) {
      btnExportROPA.addEventListener('click', downloadROPAJSON);
    }

    if (riskSeverityFilter) {
      riskSeverityFilter.addEventListener('change', renderRiskTable);
    }
    if (riskFieldSearch) {
      riskFieldSearch.addEventListener('input', renderRiskTable);
    }
    if (recStatusFilter) {
      recStatusFilter.addEventListener('change', renderRecommendationsGrid);
    }

    // Modal listeners
    if (btnCancelRecModal) {
      btnCancelRecModal.addEventListener('click', () => {
        recModal.style.display = 'none';
      });
    }
    if (btnSubmitRecModal) {
      btnSubmitRecModal.addEventListener('click', submitRecommendationUpdate);
    }

    if (btnCancelAlertModal) {
      btnCancelAlertModal.addEventListener('click', () => {
        alertModal.style.display = 'none';
      });
    }
    if (btnSubmitAlertModal) {
      btnSubmitAlertModal.addEventListener('click', submitAlertResolution);
    }

    // Mobile sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('appSidebar');
    if (sidebarToggle && sidebar) {
      sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('active');
      });
    }
  }

  // =========================================================================
  // API Fetching
  // =========================================================================

  async function fetchAllEnterpriseData() {
    try {
      await Promise.all([
        fetchExecutiveDashboard(),
        fetchRiskAssessment(),
        fetchRecommendations(),
        fetchComplianceAndROPA(),
        fetchAlerts(),
      ]);
    } catch (err) {
      console.error('Error loading enterprise privacy data:', err);
    }
  }

  async function fetchExecutiveDashboard() {
    const res = await fetch('/api/enterprise/executive/dashboard', { credentials: 'include' });
    if (!res.ok) throw new Error('Failed to fetch executive dashboard');
    currentDashboardData = await res.json();
    renderExecutiveOverview();
  }

  async function fetchRiskAssessment() {
    const res = await fetch('/api/enterprise/risk', { credentials: 'include' });
    if (!res.ok) throw new Error('Failed to fetch risk assessment');
    currentRiskSnapshot = await res.json();
    renderRiskTable();
  }

  async function fetchRecommendations() {
    const res = await fetch('/api/enterprise/recommendations', { credentials: 'include' });
    if (!res.ok) throw new Error('Failed to fetch recommendations');
    currentRecommendations = await res.json();
    renderRecommendationsGrid();

    // Update badge
    const badge = document.getElementById('subtabRecsBadge');
    if (badge) {
      const openCount = currentRecommendations.filter(r => r.status === 'Pending' || r.status === 'In Progress').length;
      badge.textContent = openCount;
    }
  }

  async function fetchComplianceAndROPA() {
    const [compRes, ropaRes] = await Promise.all([
      fetch('/api/enterprise/compliance/frameworks', { credentials: 'include' }),
      fetch('/api/enterprise/compliance/ropa', { credentials: 'include' }),
    ]);
    if (compRes.ok && ropaRes.ok) {
      const frameworks = await compRes.json();
      const ropa = await ropaRes.json();
      renderComplianceSection(frameworks, ropa);
    }
  }

  async function fetchAlerts() {
    const res = await fetch('/api/enterprise/alerts', { credentials: 'include' });
    if (!res.ok) throw new Error('Failed to fetch alerts');
    currentAlerts = await res.json();
    renderAlertsTable();

    // Update badge
    const badge = document.getElementById('subtabAlertsBadge');
    if (badge) {
      const activeCount = currentAlerts.filter(a => a.status === 'Active').length;
      badge.textContent = activeCount;
    }
  }

  // =========================================================================
  // Rendering: Executive Overview (Module 5.6)
  // =========================================================================

  function renderExecutiveOverview() {
    if (!currentDashboardData) return;
    const k = currentDashboardData.kpis;

    // Header mini badge
    const hdrVal = document.getElementById('hdrPostureVal');
    const miniBadge = document.getElementById('postureMiniBadge');
    if (hdrVal) hdrVal.textContent = `${k.overall_privacy_posture_score}/100 (${k.posture_status})`;
    if (miniBadge) {
      if (k.overall_privacy_posture_score >= 80) {
        miniBadge.style.color = '#10B981';
        miniBadge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
      } else if (k.overall_privacy_posture_score >= 65) {
        miniBadge.style.color = 'var(--accent-gold)';
        miniBadge.style.borderColor = 'rgba(245, 158, 11, 0.4)';
      } else {
        miniBadge.style.color = '#EF4444';
        miniBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
      }
    }

    // Top KPIs
    setText('kpiPostureScore', `${k.overall_privacy_posture_score}/100`);
    setText('kpiPostureStatus', `Status: ${k.posture_status} (Multi-Factor)`);
    setText('kpiTotalAttrs', k.total_sensitive_attributes);
    setText('kpiCritHighCount', k.critical_and_high_risk_findings);
    setText('kpiEvidenceCov', `${k.evidence_coverage_pct}%`);

    // Secondary KPIs
    setText('kpiVerifiedEdges', k.verified_relationships_count);
    setText('kpiInferredEdges', k.unverified_relationships_count);
    setText('kpiMissingProofs', k.missing_proofs_count);
    setText('kpiOpenRecs', k.open_recommendations_count);
    setText('kpiActiveAlerts', k.active_critical_alerts_count);

    // Framework Readiness Bars
    const fwContainer = document.getElementById('frameworkProgressContainer');
    if (fwContainer && currentDashboardData.framework_readiness) {
      fwContainer.innerHTML = currentDashboardData.framework_readiness.map(fw => `
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.35rem;">
            <span style="font-weight: 700; color: var(--text-bright);">${escapeHtml(fw.name)}</span>
            <span style="font-weight: 700; color: var(--accent-gold);">${fw.readiness_pct}% Readiness (${fw.verified_controls}/${fw.total_controls} Controls)</span>
          </div>
          <div style="background: var(--bg-surface-elevated); height: 8px; border-radius: 4px; overflow: hidden; border: 1px solid var(--border-color);">
            <div style="background: linear-gradient(90deg, #10B981, var(--accent-gold)); height: 100%; width: ${Math.min(100, Math.max(5, fw.readiness_pct))}%;"></div>
          </div>
        </div>
      `).join('');
    }

    // Risk Distribution Bars
    const distContainer = document.getElementById('riskDistributionBars');
    if (distContainer && currentDashboardData.risk_distribution) {
      const d = currentDashboardData.risk_distribution;
      const total = (d.Critical || 0) + (d.High || 0) + (d.Medium || 0) + (d.Low || 0) || 1;
      
      const bars = [
        { label: 'Critical Risk (>=80)', count: d.Critical || 0, color: '#EF4444' },
        { label: 'High Risk (60-79)', count: d.High || 0, color: '#F97316' },
        { label: 'Medium Risk (40-59)', count: d.Medium || 0, color: '#F59E0B' },
        { label: 'Low Risk (1-39)', count: d.Low || 0, color: '#10B981' },
      ];

      distContainer.innerHTML = bars.map(b => {
        const pct = Math.round((b.count / total) * 100);
        return `
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.35rem;">
              <span style="color: var(--text-muted);">${b.label}</span>
              <span style="font-weight: 700; color: ${b.color};">${b.count} fields (${pct}%)</span>
            </div>
            <div style="background: var(--bg-surface-elevated); height: 8px; border-radius: 4px; overflow: hidden; border: 1px solid var(--border-color);">
              <div style="background: ${b.color}; height: 100%; width: ${pct}%;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    // Top Vulnerable Tables Body
    const tbody = document.getElementById('topVulnerableTablesBody');
    if (tbody && currentDashboardData.top_vulnerable_datasets) {
      if (currentDashboardData.top_vulnerable_datasets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No vulnerable datasets identified.</td></tr>';
      } else {
        tbody.innerHTML = currentDashboardData.top_vulnerable_datasets.map(t => `
          <tr>
            <td style="font-weight: 700; color: var(--text-bright);">${escapeHtml(t.dataset)} · <code>${escapeHtml(t.table_name)}</code></td>
            <td><span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #06B6D4;">${escapeHtml(t.entity)}</span></td>
            <td style="font-weight: 700; color: ${t.max_risk_score >= 80 ? '#EF4444' : (t.max_risk_score >= 60 ? '#F97316' : '#F59E0B')};">${t.max_risk_score}</td>
            <td><span class="badge" style="background: ${getSeverityBadgeBg(t.severity)}; color: ${getSeverityColor(t.severity)}; font-weight: 700;">${escapeHtml(t.severity)}</span></td>
            <td>${t.missing_proofs > 0 ? `<span style="color: #EF4444; font-weight: 700;">${t.missing_proofs} Gaps</span>` : '<span style="color: #10B981;">0</span>'}</td>
            <td style="color: var(--text-muted); font-size: 0.78rem;">${escapeHtml((t.critical_factors && t.critical_factors[0]) || 'Standard storage profile')}</td>
          </tr>
        `).join('');
      }
    }

    // Recent Audit Stream
    const auditContainer = document.getElementById('auditLogStream');
    if (auditContainer && currentDashboardData.recent_audit_events) {
      if (currentDashboardData.recent_audit_events.length === 0) {
        auditContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.82rem;">No audit events recorded yet.</div>';
      } else {
        auditContainer.innerHTML = currentDashboardData.recent_audit_events.map(ev => `
          <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.65rem 0.85rem; font-size: 0.78rem;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.2rem;">
              <span style="font-weight: 700; color: var(--accent-gold);">${escapeHtml(ev.action_type)}</span>
              <span style="color: var(--text-muted); font-size: 0.72rem;">${formatTime(ev.timestamp)}</span>
            </div>
            <div style="color: var(--text-bright);">${escapeHtml(ev.target_resource)} by <code style="font-size: 0.72rem;">${escapeHtml(ev.user_email)}</code></div>
          </div>
        `).join('');
      }
    }
  }

  // =========================================================================
  // Rendering: Risk Assessment (Module 5.2)
  // =========================================================================

  function renderRiskTable() {
    if (!currentRiskSnapshot) return;
    const tbody = document.getElementById('riskTableBody');
    if (!tbody) return;

    let records = currentRiskSnapshot.top_risk_fields || [];
    const sevFilter = (riskSeverityFilter && riskSeverityFilter.value) || '';
    const searchVal = (riskFieldSearch && riskFieldSearch.value.trim().toLowerCase()) || '';

    if (sevFilter) {
      records = records.filter(r => r.severity === sevFilter);
    }
    if (searchVal) {
      records = records.filter(r => 
        r.field_key.toLowerCase().includes(searchVal) ||
        r.table_name.toLowerCase().includes(searchVal) ||
        r.column_name.toLowerCase().includes(searchVal) ||
        r.pii_class.toLowerCase().includes(searchVal)
      );
    }

    const meta = document.getElementById('riskAssessmentMeta');
    if (meta) {
      meta.textContent = `Showing ${records.length} of ${currentRiskSnapshot.total_assessed_fields} assessed fields (Avg Score: ${currentRiskSnapshot.overall_risk_score}/100)`;
    }

    if (records.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No matching risk records found.</td></tr>';
      return;
    }

    tbody.innerHTML = records.map(r => `
      <tr>
        <td style="font-weight: 700; color: var(--text-bright);"><code>${escapeHtml(r.field_key)}</code></td>
        <td><span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #06B6D4;">${escapeHtml(r.entity_name)}</span></td>
        <td><span class="badge" style="background: rgba(245, 158, 11, 0.15); color: var(--accent-gold); font-weight: 700;">${escapeHtml(r.pii_class)}</span></td>
        <td style="font-weight: 700; color: ${getRiskScoreColor(r.risk_score)};">${r.risk_score}</td>
        <td><span class="badge" style="background: ${getSeverityBadgeBg(r.severity)}; color: ${getSeverityColor(r.severity)}; font-weight: 700;">${escapeHtml(r.severity)}</span></td>
        <td><span class="badge" style="background: ${r.evidence_status === 'Verified' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)'}; color: ${r.evidence_status === 'Verified' ? '#10B981' : '#EF4444'};">${escapeHtml(r.evidence_status)}</span></td>
        <td>${r.egress_observed ? '<span class="badge" style="background: rgba(244, 63, 94, 0.2); color: #F43F5E;">Egress Logged</span>' : '<span style="color: var(--text-muted);">None</span>'}</td>
        <td style="font-size: 0.78rem; color: var(--text-muted); max-width: 280px; white-space: normal;">${escapeHtml(r.rationale)}</td>
      </tr>
    `).join('');
  }

  // =========================================================================
  // Rendering: AI Recommendations Action Board (Module 5.3)
  // =========================================================================

  function renderRecommendationsGrid() {
    const container = document.getElementById('recommendationsGrid');
    if (!container) return;

    let recs = currentRecommendations || [];
    const statusFilter = (recStatusFilter && recStatusFilter.value) || '';
    if (statusFilter) {
      recs = recs.filter(r => r.status === statusFilter);
    }

    if (recs.length === 0) {
      container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 2rem 0;">No recommendations match the selected status filter.</div>';
      return;
    }

    container.innerHTML = recs.map(r => `
      <div class="card" style="padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between; border-left: 4px solid ${getSeverityColor(r.severity)};">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <span class="badge" style="background: rgba(245, 158, 11, 0.15); color: var(--accent-gold); font-size: 0.72rem; font-weight: 700;">${escapeHtml(r.id)}</span>
            <div style="display: flex; gap: 0.35rem;">
              <span class="badge" style="background: ${getSeverityBadgeBg(r.severity)}; color: ${getSeverityColor(r.severity)}; font-weight: 700;">${escapeHtml(r.severity)}</span>
              <span class="badge" style="background: ${getStatusBadgeBg(r.status)}; color: ${getStatusColor(r.status)}; font-weight: 700;">${escapeHtml(r.status)}</span>
            </div>
          </div>
          
          <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-bright); margin: 0 0 0.5rem 0;">${escapeHtml(r.title)}</h4>
          <p style="font-size: 0.82rem; color: var(--text-muted); line-height: 1.4; margin: 0 0 0.75rem 0;">${escapeHtml(r.description)}</p>
          
          <div style="background: var(--bg-surface-elevated); padding: 0.65rem 0.75rem; border-radius: var(--radius-sm); font-size: 0.78rem; margin-bottom: 0.85rem; border: 1px solid var(--border-color);">
            <div style="color: var(--text-bright); margin-bottom: 0.2rem;"><strong>Target:</strong> <code>${escapeHtml(r.target_dataset)}</code>${r.target_column ? ` ➔ <code>${escapeHtml(r.target_column)}</code>` : ''}</div>
            <div style="color: #10B981;"><strong>Impact:</strong> ${escapeHtml(r.expected_impact)}</div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; pt: 0.5rem; border-top: 1px solid var(--border-color); margin-top: 0.75rem;">
          <span style="font-size: 0.72rem; color: var(--text-muted);">Priority ${r.priority}</span>
          <button class="btn btn-secondary btn-sm btn-update-rec" data-rec-id="${escapeHtml(r.id)}" style="font-size: 0.75rem; padding: 0.25rem 0.65rem;">
            Update Status
          </button>
        </div>
      </div>
    `).join('');

    // Attach click listeners to update buttons
    container.querySelectorAll('.btn-update-rec').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-rec-id');
        openRecommendationModal(id);
      });
    });
  }

  function openRecommendationModal(recId) {
    selectedRecId = recId;
    const rec = currentRecommendations.find(r => r.id === recId);
    if (!rec) return;

    recModalTitle.textContent = `Update [${rec.id}]`;
    recModalDesc.textContent = rec.title;
    recModalStatusSelect.value = rec.status;
    recModalNotes.value = rec.resolution_notes || '';
    recModal.style.display = 'flex';
  }

  async function submitRecommendationUpdate() {
    if (!selectedRecId) return;
    const newStatus = recModalStatusSelect.value;
    const notes = recModalNotes.value.trim();

    try {
      btnSubmitRecModal.disabled = true;
      btnSubmitRecModal.textContent = 'Saving...';

      const res = await fetch(`/api/enterprise/recommendations/${selectedRecId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ status: newStatus, notes: notes }),
      });

      if (!res.ok) throw new Error('Failed to update recommendation');
      recModal.style.display = 'none';

      // Refresh list
      await fetchRecommendations();
      await fetchExecutiveDashboard();
    } catch (err) {
      alert(`Error updating recommendation: ${err.message}`);
    } finally {
      btnSubmitRecModal.disabled = false;
      btnSubmitRecModal.textContent = 'Save Status';
    }
  }

  // =========================================================================
  // Rendering: Compliance & ROPA (Module 5.4)
  // =========================================================================

  function renderComplianceSection(frameworks, ropa) {
    // ROPA Activities Table
    const ropaTbody = document.getElementById('ropaTableBody');
    if (ropaTbody && ropa && ropa.activities) {
      ropaTbody.innerHTML = ropa.activities.map(act => `
        <tr>
          <td>
            <div style="font-weight: 700; color: var(--text-bright);">${escapeHtml(act.activity_name)}</div>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${escapeHtml(act.business_purpose)}</div>
          </td>
          <td>${act.data_subjects.map(s => `<span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #06B6D4; font-size: 0.72rem; margin: 0.1rem;">${escapeHtml(s)}</span>`).join('')}</td>
          <td>${act.categories_of_personal_data.map(c => `<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: var(--accent-gold); font-size: 0.72rem; margin: 0.1rem;">${escapeHtml(c)}</span>`).join('')}</td>
          <td><code style="font-size: 0.75rem;">${escapeHtml(act.storage_locations.join(', '))}</code></td>
          <td style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(act.retention_policy)} (${escapeHtml(act.security_safeguards)})</td>
          <td><span class="badge" style="background: ${act.verification_status.includes('Verified') ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)'}; color: ${act.verification_status.includes('Verified') ? '#10B981' : 'var(--accent-gold)'}; font-weight: 700;">${escapeHtml(act.verification_status)}</span></td>
        </tr>
      `).join('');
    }

    // Framework Checklist Details
    const fwContainer = document.getElementById('frameworkDetailsContainer');
    if (fwContainer && frameworks) {
      fwContainer.innerHTML = frameworks.map(fw => `
        <div class="card" style="padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.65rem;">
            <div>
              <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-bright); margin: 0;">${escapeHtml(fw.framework_name)}</h4>
              <p style="font-size: 0.75rem; color: var(--text-muted); margin: 0.2rem 0 0 0;">${escapeHtml(fw.audit_disclaimer)}</p>
            </div>
            <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10B981; font-size: 0.85rem; font-weight: 700;">${fw.overall_readiness_pct}% Readiness</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 0.75rem;">
            ${fw.controls.map(c => `
              <div style="background: var(--bg-surface-elevated); padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <span style="font-weight: 700; color: var(--text-bright); font-size: 0.85rem;"><code>${escapeHtml(c.control_id)}</code> - ${escapeHtml(c.name)}</span>
                  <span class="badge" style="background: ${getComplianceBadgeBg(c.status)}; color: ${getComplianceColor(c.status)}; font-weight: 700;">${escapeHtml(c.status)}</span>
                </div>
                <p style="font-size: 0.78rem; color: var(--text-muted); margin: 0 0 0.35rem 0;">${escapeHtml(c.description)}</p>
                <div style="font-size: 0.75rem; color: #10B981;"><strong>Guidance:</strong> ${escapeHtml(c.remediation_guidance)}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `).join('');
    }
  }

  function downloadROPAJSON() {
    fetch('/api/enterprise/compliance/ropa', { credentials: 'include' })
      .then(res => res.json())
      .then(data => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `privsight_ropa_report_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(err => alert(`Error exporting ROPA: ${err.message}`));
  }

  // =========================================================================
  // Rendering: Continuous Monitoring & Alerts (Module 5.5)
  // =========================================================================

  function renderAlertsTable() {
    const tbody = document.getElementById('alertsTableBody');
    if (!tbody) return;

    if (!currentAlerts || currentAlerts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No active or historical alerts recorded.</td></tr>';
      return;
    }

    tbody.innerHTML = currentAlerts.map(a => `
      <tr>
        <td><span class="badge" style="background: ${getSeverityBadgeBg(a.severity)}; color: ${getSeverityColor(a.severity)}; font-weight: 700;">${escapeHtml(a.severity)}</span></td>
        <td><span class="badge" style="background: rgba(245, 158, 11, 0.15); color: var(--accent-gold); font-size: 0.72rem;">${escapeHtml(a.category)}</span></td>
        <td>
          <div style="font-weight: 700; color: var(--text-bright);">${escapeHtml(a.title)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted); max-width: 320px; white-space: normal;">${escapeHtml(a.message)}</div>
        </td>
        <td><code>${escapeHtml(a.source_dataset)}${a.source_column ? `:${escapeHtml(a.source_column)}` : ''}</code></td>
        <td><span class="badge" style="background: ${a.status === 'Active' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)'}; color: ${a.status === 'Active' ? '#EF4444' : '#10B981'}; font-weight: 700;">${escapeHtml(a.status)}</span></td>
        <td style="font-size: 0.75rem; color: var(--text-muted);">${formatTime(a.timestamp)}</td>
        <td>
          ${a.status === 'Active' ? `
            <div style="display: flex; gap: 0.35rem;">
              <button class="btn btn-secondary btn-sm btn-ack-alert" data-alert-id="${escapeHtml(a.id)}" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;">Ack</button>
              <button class="btn btn-primary btn-sm btn-resolve-alert" data-alert-id="${escapeHtml(a.id)}" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #10B981; border-color: #10B981; color: #fff;">Resolve</button>
            </div>
          ` : (a.status === 'Acknowledged' ? `
            <button class="btn btn-primary btn-sm btn-resolve-alert" data-alert-id="${escapeHtml(a.id)}" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #10B981; border-color: #10B981; color: #fff;">Resolve</button>
          ` : '<span style="color: var(--text-muted); font-size: 0.75rem;">Resolved</span>')}
        </td>
      </tr>
    `).join('');

    // Attach listeners
    tbody.querySelectorAll('.btn-ack-alert').forEach(btn => {
      btn.addEventListener('click', () => acknowledgeAlert(btn.getAttribute('data-alert-id')));
    });
    tbody.querySelectorAll('.btn-resolve-alert').forEach(btn => {
      btn.addEventListener('click', () => openAlertResolveModal(btn.getAttribute('data-alert-id')));
    });
  }

  async function syncAlertsNow() {
    try {
      if (btnSyncAlerts) {
        btnSyncAlerts.disabled = true;
        btnSyncAlerts.textContent = 'Scanning...';
      }
      const res = await fetch('/api/enterprise/alerts/sync', { method: 'POST', credentials: 'include' });
      if (!res.ok) throw new Error('Alert sync failed');
      await fetchAlerts();
      await fetchExecutiveDashboard();
    } catch (err) {
      alert(`Alert sync error: ${err.message}`);
    } finally {
      if (btnSyncAlerts) {
        btnSyncAlerts.disabled = false;
        btnSyncAlerts.innerHTML = '<span>⚡</span> <span>Scan &amp; Sync Alerts</span>';
      }
    }
  }

  async function acknowledgeAlert(alertId) {
    try {
      const res = await fetch(`/api/enterprise/alerts/${alertId}/acknowledge`, { method: 'POST', credentials: 'include' });
      if (!res.ok) throw new Error('Failed to acknowledge alert');
      await fetchAlerts();
      await fetchExecutiveDashboard();
    } catch (err) {
      alert(`Error acknowledging alert: ${err.message}`);
    }
  }

  function openAlertResolveModal(alertId) {
    selectedAlertId = alertId;
    const alertItem = currentAlerts.find(a => a.id === alertId);
    if (!alertItem) return;

    alertModalMessage.textContent = alertItem.title;
    alertModalNotes.value = '';
    alertModal.style.display = 'flex';
  }

  async function submitAlertResolution() {
    if (!selectedAlertId) return;
    const notes = alertModalNotes.value.trim();

    try {
      btnSubmitAlertModal.disabled = true;
      btnSubmitAlertModal.textContent = 'Resolving...';

      const res = await fetch(`/api/enterprise/alerts/${selectedAlertId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ status: 'Resolved', notes: notes }),
      });

      if (!res.ok) throw new Error('Failed to resolve alert');
      alertModal.style.display = 'none';

      await fetchAlerts();
      await fetchExecutiveDashboard();
    } catch (err) {
      alert(`Error resolving alert: ${err.message}`);
    } finally {
      btnSubmitAlertModal.disabled = false;
      btnSubmitAlertModal.textContent = 'Confirm Resolution';
    }
  }

  // =========================================================================
  // Helpers
  // =========================================================================

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoStr;
    }
  }

  function getSeverityColor(sev) {
    switch (sev) {
      case 'Critical': return '#EF4444';
      case 'High': return '#F97316';
      case 'Medium': return '#F59E0B';
      case 'Low': return '#10B981';
      default: return 'var(--text-muted)';
    }
  }

  function getSeverityBadgeBg(sev) {
    switch (sev) {
      case 'Critical': return 'rgba(239, 68, 68, 0.15)';
      case 'High': return 'rgba(249, 115, 22, 0.15)';
      case 'Medium': return 'rgba(245, 158, 11, 0.15)';
      case 'Low': return 'rgba(16, 185, 129, 0.15)';
      default: return 'rgba(255, 255, 255, 0.05)';
    }
  }

  function getRiskScoreColor(score) {
    if (score >= 80) return '#EF4444';
    if (score >= 60) return '#F97316';
    if (score >= 40) return '#F59E0B';
    return '#10B981';
  }

  function getStatusColor(status) {
    switch (status) {
      case 'Completed': return '#10B981';
      case 'In Progress': return '#06B6D4';
      case 'Accepted': return '#F59E0B';
      case 'Dismissed': return 'var(--text-muted)';
      default: return '#EF4444'; // Pending
    }
  }

  function getStatusBadgeBg(status) {
    switch (status) {
      case 'Completed': return 'rgba(16, 185, 129, 0.15)';
      case 'In Progress': return 'rgba(6, 182, 212, 0.15)';
      case 'Accepted': return 'rgba(245, 158, 11, 0.15)';
      case 'Dismissed': return 'rgba(255, 255, 255, 0.05)';
      default: return 'rgba(239, 68, 68, 0.15)'; // Pending
    }
  }

  function getComplianceColor(status) {
    switch (status) {
      case 'Verified': return '#10B981';
      case 'Partially Supported': return '#F59E0B';
      case 'Missing Evidence': return '#EF4444';
      default: return 'var(--text-muted)';
    }
  }

  function getComplianceBadgeBg(status) {
    switch (status) {
      case 'Verified': return 'rgba(16, 185, 129, 0.15)';
      case 'Partially Supported': return 'rgba(245, 158, 11, 0.15)';
      case 'Missing Evidence': return 'rgba(239, 68, 68, 0.15)';
      default: return 'rgba(255, 255, 255, 0.05)';
    }
  }

})();

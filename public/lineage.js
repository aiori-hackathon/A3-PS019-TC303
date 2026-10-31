/**
 * frontend/lineage.js
 * ===================
 * PrivSight Phase 5.1 — Directional Data Lineage DAG, Evidence Ledger & Egress Tracker.
 * 
 * Interactive capabilities:
 * - Directional DAG rendered with Cytoscape.js
 * - Color-coded lifecycle stages (Ingestion -> Storage -> Processing -> Egress)
 * - Solid / dashed edge styling for Verified vs Inferred
 * - Upstream origin and downstream egress path highlighting
 * - Real-time SHA-256 Evidence Integrity Ledger verification
 * - Observable cross-system data egress tracking
 */

(function () {
  'use strict';

  let cy = null;
  let rawDagData = null;
  let selectedNodeId = null;

  // Lifecycle Stage Palette
  const STAGE_COLORS = {
    Ingestion: '#06B6D4',   // Cyan
    Storage: '#10B981',     // Emerald
    Processing: '#D4A72C',  // Gold
    Egress: '#F97316',      // Orange
    Unknown: '#64748B',     // Slate
  };

  document.addEventListener('DOMContentLoaded', () => {
    initLineagePage();
  });

  async function initLineagePage() {
    setupEventListeners();
    await loadLineageDAG();
    await loadEvidenceLedger();
    await loadEgressEvents();
  }

  function setupEventListeners() {
    // Filter controls
    const entityFilter = document.getElementById('filterEntity');
    const stageFilter = document.getElementById('filterStage');
    const statusFilter = document.getElementById('filterStatus');
    const searchInput = document.getElementById('lineageSearchInput');

    if (entityFilter) entityFilter.addEventListener('change', applyFilters);
    if (stageFilter) stageFilter.addEventListener('change', applyFilters);
    if (statusFilter) statusFilter.addEventListener('change', applyFilters);
    if (searchInput) {
      searchInput.addEventListener('input', debounce(() => {
        applyFilters();
      }, 250));
    }

    // Graph Controls
    const btnResetGraph = document.getElementById('btnResetGraph');
    const btnFitGraph = document.getElementById('btnFitGraph');
    if (btnResetGraph) btnResetGraph.addEventListener('click', resetGraphView);
    if (btnFitGraph) btnFitGraph.addEventListener('click', () => cy && cy.fit(undefined, 40));

    // Ledger Verification Button
    const btnVerifyLedger = document.getElementById('btnVerifyLedger');
    if (btnVerifyLedger) {
      btnVerifyLedger.addEventListener('click', runLedgerVerification);
    }

    // Scan Egress Button
    const btnScanEgress = document.getElementById('btnScanEgress');
    if (btnScanEgress) {
      btnScanEgress.addEventListener('click', triggerEgressScan);
    }

    // Navigation Tab Switching if multiple tabs exist
    const subtabs = document.querySelectorAll('.lineage-subtab-btn');
    subtabs.forEach(btn => {
      btn.addEventListener('click', () => {
        subtabs.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const targetId = btn.getAttribute('data-target');
        document.querySelectorAll('.lineage-view-pane').forEach(p => p.style.display = 'none');
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.style.display = 'block';
        if (targetId === 'pane-dag' && cy) {
          setTimeout(() => cy.resize() && cy.fit(undefined, 30), 50);
        }
      });
    });
  }

  // -------------------------------------------------------------------------
  // 1. DIRECTIONAL LINEAGE DAG
  // -------------------------------------------------------------------------

  async function loadLineageDAG(focusEntity = null, focusField = null) {
    const loadingOverlay = document.getElementById('dagLoadingOverlay');
    if (loadingOverlay) loadingOverlay.style.display = 'flex';

    try {
      let url = '/api/lineage/dag';
      const params = new URLSearchParams();
      if (focusEntity) params.append('focus_entity', focusEntity);
      if (focusField) params.append('focus_field', focusField);
      if (params.toString()) url += '?' + params.toString();

      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      rawDagData = await res.json();

      updateDAGSummaryBadges(rawDagData);
      renderCytoscapeDAG(rawDagData);
    } catch (err) {
      console.error('Failed to load Lineage DAG:', err);
      showToast('Could not load directional lineage DAG: ' + err.message, 'error');
    } finally {
      if (loadingOverlay) loadingOverlay.style.display = 'none';
    }
  }

  function updateDAGSummaryBadges(dag) {
    const totalNodesEl = document.getElementById('badgeTotalNodes');
    const totalEdgesEl = document.getElementById('badgeTotalEdges');
    const originsEl = document.getElementById('badgeOrigins');
    const egressEl = document.getElementById('badgeEgress');

    if (totalNodesEl) totalNodesEl.textContent = dag.nodes.length;
    if (totalEdgesEl) totalEdgesEl.textContent = dag.edges.length;
    if (originsEl) originsEl.textContent = dag.origins ? dag.origins.length : 0;
    if (egressEl) egressEl.textContent = dag.egress_points ? dag.egress_points.length : 0;

    const summaryTextEl = document.getElementById('dagSummaryText');
    if (summaryTextEl) summaryTextEl.textContent = dag.summary || '';
  }

  function renderCytoscapeDAG(dag) {
    const container = document.getElementById('cyLineageContainer');
    if (!container || typeof cytoscape === 'undefined') return;

    const elements = [];

    // Stages X-rank ordering for directed left-to-right layout
    const stageRank = {
      Ingestion: 1,
      Storage: 2,
      Processing: 3,
      Egress: 4,
      Unknown: 5,
    };

    // Add Nodes
    dag.nodes.forEach(node => {
      elements.push({
        group: 'nodes',
        data: {
          id: node.id,
          label: node.label || node.column,
          dataset: node.dataset,
          table: node.table || '',
          column: node.column,
          stage: node.stage,
          entity: node.entity || '',
          data_class: node.data_class || 'Standard',
          is_pii: node.is_pii,
          is_origin: node.is_origin,
          is_egress: node.is_egress,
          masked_preview: node.masked_preview || 'None',
          rank: stageRank[node.stage] || 3,
          color: STAGE_COLORS[node.stage] || '#94A3B8',
        },
      });
    });

    // Add Edges
    dag.edges.forEach(edge => {
      elements.push({
        group: 'edges',
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          verification_status: edge.verification_status,
          edge_type: edge.edge_type,
          confidence: edge.confidence,
          evidence: edge.evidence,
          discovery_method: edge.discovery_method,
          evidence_hash: edge.evidence_hash || 'Unassigned',
          is_verified: edge.verification_status === 'Verified',
        },
      });
    });

    if (cy) {
      cy.destroy();
    }

    cy = cytoscape({
      container: container,
      elements: elements,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'font-family': 'Plus Jakarta Sans, sans-serif',
            'font-size': '10px',
            'font-weight': 600,
            'color': '#E2E8F0',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'background-color': 'data(color)',
            'border-width': 2,
            'border-color': '#0B0F17',
            'width': 28,
            'height': 28,
            'transition-property': 'background-color, border-color, border-width, width, height, opacity',
            'transition-duration': '0.2s',
          },
        },
        {
          selector: 'node[?is_pii]',
          style: {
            'border-width': 3,
            'border-color': '#F59E0B',
            'width': 32,
            'height': 32,
          },
        },
        {
          selector: 'node[?is_origin]',
          style: {
            'shape': 'round-rectangle',
            'border-width': 3,
            'border-color': '#38BDF8',
          },
        },
        {
          selector: 'node[?is_egress]',
          style: {
            'shape': 'diamond',
            'border-width': 3,
            'border-color': '#F97316',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#10B981',
            'line-color': '#10B981',
            'arrow-scale': 1.1,
            'opacity': 0.75,
            'transition-property': 'line-color, target-arrow-color, width, opacity',
            'transition-duration': '0.2s',
          },
        },
        {
          selector: 'edge[!is_verified]',
          style: {
            'line-style': 'dashed',
            'line-dash-pattern': [6, 4],
            'line-color': '#D4A72C',
            'target-arrow-color': '#D4A72C',
          },
        },
        {
          selector: 'edge[edge_type = "export_egress"]',
          style: {
            'line-style': 'dotted',
            'line-dash-pattern': [3, 3],
            'line-color': '#F97316',
            'target-arrow-color': '#F97316',
            'width': 2.5,
          },
        },
        // Highlighting styles
        {
          selector: 'node.highlighted',
          style: {
            'border-width': 4,
            'border-color': '#FFFFFF',
            'width': 36,
            'height': 36,
            'opacity': 1,
            'z-index': 99,
          },
        },
        {
          selector: 'node.upstream-origin',
          style: {
            'border-color': '#06B6D4',
            'border-width': 4,
            'opacity': 1,
          },
        },
        {
          selector: 'node.downstream-egress',
          style: {
            'border-color': '#F97316',
            'border-width': 4,
            'opacity': 1,
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'width': 4,
            'opacity': 1,
            'z-index': 98,
          },
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.18,
          },
        },
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        roots: dag.origins.length > 0 ? dag.origins : undefined,
        padding: 50,
        spacingFactor: 1.35,
        animate: false,
      },
    });

    // Node click handler
    cy.on('tap', 'node', function (evt) {
      const node = evt.target;
      highlightConnectedLineage(node);
      inspectNodeDetails(node.data());
    });

    // Edge click handler
    cy.on('tap', 'edge', function (evt) {
      const edge = evt.target;
      inspectEdgeDetails(edge.data());
    });

    // Background click handler
    cy.on('tap', function (evt) {
      if (evt.target === cy) {
        clearHighlights();
        resetInspectorPanel();
      }
    });

    // Initial fit
    cy.fit(undefined, 30);
  }

  function highlightConnectedLineage(targetNode) {
    selectedNodeId = targetNode.id();
    cy.elements().removeClass('highlighted faded upstream-origin downstream-egress');

    const successors = targetNode.successors();
    const predecessors = targetNode.predecessors();

    const connectedElements = targetNode.union(successors).union(predecessors);
    const nonConnected = cy.elements().difference(connectedElements);

    nonConnected.addClass('faded');
    targetNode.addClass('highlighted');
    successors.addClass('highlighted downstream-egress');
    predecessors.addClass('highlighted upstream-origin');
  }

  function clearHighlights() {
    selectedNodeId = null;
    if (cy) {
      cy.elements().removeClass('highlighted faded upstream-origin downstream-egress');
    }
  }

  function resetGraphView() {
    clearHighlights();
    const filterEntity = document.getElementById('filterEntity');
    const filterStage = document.getElementById('filterStage');
    const filterStatus = document.getElementById('filterStatus');
    const searchInput = document.getElementById('lineageSearchInput');

    if (filterEntity) filterEntity.value = '';
    if (filterStage) filterStage.value = '';
    if (filterStatus) filterStatus.value = '';
    if (searchInput) searchInput.value = '';

    if (rawDagData) {
      renderCytoscapeDAG(rawDagData);
    }
    resetInspectorPanel();
  }

  function applyFilters() {
    if (!cy || !rawDagData) return;

    const entityVal = (document.getElementById('filterEntity')?.value || '').toLowerCase();
    const stageVal = document.getElementById('filterStage')?.value || '';
    const statusVal = document.getElementById('filterStatus')?.value || '';
    const searchVal = (document.getElementById('lineageSearchInput')?.value || '').toLowerCase().trim();

    cy.batch(() => {
      cy.nodes().forEach(n => {
        const d = n.data();
        let visible = true;

        if (entityVal && !d.entity.toLowerCase().includes(entityVal)) {
          visible = false;
        }
        if (stageVal && d.stage !== stageVal) {
          visible = false;
        }
        if (searchVal) {
          const matchLabel = d.label.toLowerCase().includes(searchVal);
          const matchDataset = d.dataset.toLowerCase().includes(searchVal);
          const matchCol = d.column.toLowerCase().includes(searchVal);
          if (!matchLabel && !matchDataset && !matchCol) {
            visible = false;
          }
        }

        if (visible) {
          n.show();
        } else {
          n.hide();
        }
      });

      cy.edges().forEach(e => {
        const ed = e.data();
        let visible = true;
        if (statusVal && ed.verification_status !== statusVal) {
          visible = false;
        }
        if (e.source().hidden() || e.target().hidden()) {
          visible = false;
        }
        if (visible) {
          e.show();
        } else {
          e.hide();
        }
      });
    });

    cy.fit(undefined, 30);
  }

  // -------------------------------------------------------------------------
  // 2. INSPECTOR PANEL
  // -------------------------------------------------------------------------

  function inspectNodeDetails(data) {
    const panel = document.getElementById('lineageInspectorContent');
    if (!panel) return;

    const stageBadgeClass = `badge-stage-${data.stage.toLowerCase()}`;

    panel.innerHTML = `
      <div style="margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.85rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.4rem;">
          <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-primary); margin: 0;">${escapeHtml(data.label)}</h4>
          <span class="badge ${stageBadgeClass}">${escapeHtml(data.stage)}</span>
        </div>
        <div style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--accent-gold); word-break: break-all;">
          ${escapeHtml(data.id)}
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 0.75rem; font-size: 0.82rem;">
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Entity / Domain</span>
          <span style="color: var(--text-primary); font-weight: 600;">${escapeHtml(data.entity || 'General')}</span>
        </div>

        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Dataset &amp; Table</span>
          <span style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.76rem;">${escapeHtml(data.dataset)}</span>
        </div>

        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Privacy Classification</span>
          <div style="display: flex; align-items: center; gap: 0.4rem; margin-top: 0.2rem;">
            <span class="badge" style="background: ${data.is_pii ? 'rgba(245, 158, 11, 0.15)' : 'rgba(100, 116, 139, 0.15)'}; color: ${data.is_pii ? '#F59E0B' : '#94A3B8'};">
              ${escapeHtml(data.data_class)}
            </span>
            ${data.is_pii ? '<span style="font-size: 0.7rem; color: var(--accent-gold);">● Personal Data</span>' : ''}
          </div>
        </div>

        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Masked Sample Value</span>
          <span class="hash-pill" style="margin-top: 0.25rem;">${escapeHtml(data.masked_preview)}</span>
        </div>

        <div style="margin-top: 0.5rem; display: flex; gap: 0.5rem;">
          <button class="btn btn-sm btn-secondary-gold" onclick="window.traceFieldOrigin('${escapeHtml(data.id)}')">
            <span>🔍</span>
            <span>Trace Origin</span>
          </button>
          <button class="btn btn-sm btn-secondary" onclick="window.loadFieldLedgerChain('${escapeHtml(data.id)}')">
            <span>⛓️</span>
            <span>Evidence Chain</span>
          </button>
        </div>
      </div>
    `;
  }

  function inspectEdgeDetails(data) {
    const panel = document.getElementById('lineageInspectorContent');
    if (!panel) return;

    const isVerified = data.verification_status === 'Verified';

    panel.innerHTML = `
      <div style="margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.85rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
          <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-primary); margin: 0;">Directional Relational Flow</h4>
          <span class="badge ${isVerified ? 'badge-verified' : 'badge-inferred'}">
            ${escapeHtml(data.verification_status)}
          </span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted);">
          Flow ID: <span style="font-family: var(--font-mono); color: var(--text-secondary);">${escapeHtml(data.id)}</span>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 0.75rem; font-size: 0.82rem;">
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Upstream Source</span>
          <span style="font-family: var(--font-mono); color: #38BDF8; font-size: 0.76rem;">${escapeHtml(data.source)}</span>
        </div>

        <div style="text-align: center; color: var(--accent-gold); font-size: 1.1rem; line-height: 1;">
          ↓
        </div>

        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Downstream Target</span>
          <span style="font-family: var(--font-mono); color: #10B981; font-size: 0.76rem;">${escapeHtml(data.target)}</span>
        </div>

        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Discovery Method</span>
          <span style="color: var(--text-primary); font-weight: 600;">${escapeHtml(data.discovery_method)}</span>
        </div>

        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Technical Evidence</span>
          <div style="background: var(--bg-elevated); padding: 0.6rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color); color: var(--text-secondary); font-size: 0.76rem;">
            ${escapeHtml(data.evidence)}
          </div>
        </div>

        <div>
          <span style="color: var(--text-muted); display: block; font-size: 0.72rem; text-transform: uppercase; font-weight: 700;">Evidence Hash (SHA-256 Ledger)</span>
          <div class="hash-pill" style="margin-top: 0.25rem;">
            ${escapeHtml(data.evidence_hash)}
          </div>
        </div>
      </div>
    `;
  }

  function resetInspectorPanel() {
    const panel = document.getElementById('lineageInspectorContent');
    if (!panel) return;
    panel.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 3rem 1rem;">
        <span style="font-size: 2rem; display: block; margin-bottom: 0.5rem; opacity: 0.6;">🔀</span>
        <div style="font-size: 0.88rem; font-weight: 600; color: var(--text-secondary);">Select a Node or Edge</div>
        <p style="font-size: 0.76rem; margin-top: 0.25rem; line-height: 1.4;">
          Click any column node to highlight its upstream origins and downstream egress pathways, or click a connecting edge to inspect cryptographic evidence proof.
        </p>
      </div>
    `;
  }

  // -------------------------------------------------------------------------
  // 3. EVIDENCE INTEGRITY LEDGER
  // -------------------------------------------------------------------------

  async function loadEvidenceLedger() {
    const tbody = document.getElementById('ledgerTableBody');
    if (!tbody) return;

    try {
      const res = await fetch('/api/lineage/ledger?limit=50');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const entries = await res.json();

      if (!entries || entries.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No evidence ledger entries recorded yet.</td></tr>`;
        return;
      }

      tbody.innerHTML = entries.map(e => `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-gold);">#${e.sequence}</td>
          <td style="font-size: 0.75rem; color: var(--text-muted); white-space: nowrap;">${formatTimestamp(e.timestamp)}</td>
          <td>
            <div style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-primary);">${escapeHtml(e.source_ref)}</div>
            <div style="font-size: 0.68rem; color: var(--text-muted);">➔ ${escapeHtml(e.target_ref)}</div>
          </td>
          <td>
            <span class="badge" style="background: rgba(14, 165, 233, 0.12); color: #0EA5E9; font-size: 0.7rem;">
              ${escapeHtml(e.evidence_type)}
            </span>
          </td>
          <td>
            <span class="badge ${e.verification_status === 'Verified' ? 'badge-verified' : 'badge-inferred'}" style="font-size: 0.7rem;">
              ${escapeHtml(e.verification_status)}
            </span>
          </td>
          <td>
            <div class="hash-pill" title="Click to copy SHA-256 hash" onclick="window.copyToClipboard('${escapeHtml(e.current_hash)}')">
              ${escapeHtml(e.current_hash.slice(0, 16))}...
            </div>
          </td>
        </tr>
      `).join('');
    } catch (err) {
      console.error('Failed to load evidence ledger:', err);
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--color-danger); padding: 1rem;">Failed to load ledger: ${err.message}</td></tr>`;
    }
  }

  async function runLedgerVerification() {
    const btn = document.getElementById('btnVerifyLedger');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span><span>Auditing Chain...</span>';
    }

    try {
      const res = await fetch('/api/lineage/ledger/verify', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const audit = await res.json();

      const modal = document.getElementById('ledgerAuditModal');
      const body = document.getElementById('ledgerAuditModalBody');
      if (modal && body) {
        body.innerHTML = `
          <div style="display: flex; align-items: center; gap: 0.75rem; padding: 1rem; border-radius: var(--radius-sm); margin-bottom: 1rem; background: ${audit.is_valid ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)'}; border: 1px solid ${audit.is_valid ? '#10B981' : '#EF4444'};">
            <span style="font-size: 1.5rem;">${audit.is_valid ? '🛡️' : '⚠️'}</span>
            <div>
              <div style="font-size: 0.95rem; font-weight: 700; color: ${audit.is_valid ? '#10B981' : '#EF4444'};">
                ${audit.is_valid ? 'CHAIN INTEGRITY 100% VERIFIED' : 'INTEGRITY BREACH DETECTED'}
              </div>
              <div style="font-size: 0.78rem; color: var(--text-secondary);">${escapeHtml(audit.message)}</div>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem; font-size: 0.8rem; margin-bottom: 1rem;">
            <div style="background: var(--bg-elevated); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <span style="color: var(--text-muted); display: block; font-size: 0.7rem; text-transform: uppercase; font-weight: 700;">Audited Blocks</span>
              <span style="font-size: 1.1rem; font-weight: 800; color: var(--accent-gold);">${audit.total_records}</span>
            </div>
            <div style="background: var(--bg-elevated); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <span style="color: var(--text-muted); display: block; font-size: 0.7rem; text-transform: uppercase; font-weight: 700;">Verified Timestamp</span>
              <span style="font-size: 0.76rem; color: var(--text-secondary);">${formatTimestamp(audit.verified_at)}</span>
            </div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.78rem;">
            <div>
              <span style="color: var(--text-muted); display: block; font-size: 0.7rem; text-transform: uppercase; font-weight: 700;">Genesis Hash</span>
              <span class="hash-pill">${escapeHtml(audit.genesis_hash)}</span>
            </div>
            <div>
              <span style="color: var(--text-muted); display: block; font-size: 0.7rem; text-transform: uppercase; font-weight: 700;">Tip Block Hash</span>
              <span class="hash-pill">${escapeHtml(audit.tip_hash || 'None')}</span>
            </div>
          </div>
        `;
        modal.style.display = 'flex';
      }

      showToast(audit.is_valid ? 'Ledger verified: All SHA-256 blocks untampered' : 'Ledger audit failure: Tamper detected', audit.is_valid ? 'success' : 'error');
    } catch (err) {
      console.error('Ledger verification failed:', err);
      showToast('Ledger audit failed: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span>🛡️</span><span>Verify Ledger</span>';
      }
    }
  }

  // -------------------------------------------------------------------------
  // 4. CROSS-SYSTEM DATA EGRESS TRACKER
  // -------------------------------------------------------------------------

  async function loadEgressEvents() {
    const tbody = document.getElementById('egressTableBody');
    if (!tbody) return;

    try {
      const res = await fetch('/api/lineage/egress?limit=50');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const events = await res.json();

      const totalCountEl = document.getElementById('badgeTotalEgress');
      if (totalCountEl) totalCountEl.textContent = events.length;

      if (!events || events.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No observable data egress events recorded.</td></tr>`;
        return;
      }

      tbody.innerHTML = events.map(ev => `
        <tr>
          <td>
            <span class="badge badge-egress-op" style="font-size: 0.72rem;">${escapeHtml(ev.operation_type)}</span>
          </td>
          <td>
            <div style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-primary);">${escapeHtml(ev.source_dataset)}</div>
            <div style="font-size: 0.7rem; color: var(--text-muted);">Col: <span style="color: var(--accent-gold);">${escapeHtml(ev.source_column)}</span></div>
          </td>
          <td>
            <div style="font-family: var(--font-mono); font-size: 0.74rem; color: #F97316;">${escapeHtml(ev.destination_dataset)}</div>
            <div style="font-size: 0.68rem; color: var(--text-muted);">Target: ${escapeHtml(ev.destination_type)}</div>
          </td>
          <td>
            <div style="font-weight: 600; color: var(--text-primary); font-size: 0.78rem;">${escapeHtml(ev.entity_name)}</div>
            <div style="font-size: 0.7rem; color: var(--text-muted);">${ev.record_count} record(s)</div>
          </td>
          <td>
            <span class="badge badge-verified" style="font-size: 0.7rem;">${escapeHtml(ev.verification_status)}</span>
          </td>
          <td style="font-size: 0.72rem; color: var(--text-secondary); max-width: 240px; white-space: normal; line-height: 1.35;">
            ${escapeHtml(ev.evidence)}
          </td>
        </tr>
      `).join('');
    } catch (err) {
      console.error('Failed to load egress events:', err);
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--color-danger); padding: 1rem;">Failed to load egress events: ${err.message}</td></tr>`;
    }
  }

  async function triggerEgressScan() {
    const btn = document.getElementById('btnScanEgress');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span><span>Scanning...</span>';
    }

    try {
      const res = await fetch('/api/lineage/egress/scan', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      showToast(data.message, 'success');
      await loadEgressEvents();
      await loadLineageDAG();
    } catch (err) {
      console.error('Egress scan failed:', err);
      showToast('Egress scan failed: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span>⚡</span><span>Scan Observable Egress</span>';
      }
    }
  }

  // -------------------------------------------------------------------------
  // 5. GLOBAL HELPER UTILITIES
  // -------------------------------------------------------------------------

  window.traceFieldOrigin = async function (fieldId) {
    try {
      const res = await fetch(`/api/lineage/origin/${encodeURIComponent(fieldId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.origin_found && data.primary_origins.length > 0) {
        const orig = data.primary_origins[0];
        showToast(`Origin discovered: ${orig.dataset} · ${orig.column} (${orig.hop_distance} hops away)`, 'success');
        if (cy) {
          const originNode = cy.getElementById(orig.node_id);
          if (originNode.length > 0) {
            highlightConnectedLineage(originNode);
            cy.animate({
              center: { eles: originNode },
              zoom: 1.4,
              duration: 400,
            });
          }
        }
      } else {
        showToast('This node is an initial origin point or has no upstream sources.', 'info');
      }
    } catch (err) {
      showToast('Failed to trace field origin: ' + err.message, 'error');
    }
  };

  window.loadFieldLedgerChain = async function (fieldId) {
    try {
      const res = await fetch(`/api/lineage/evidence-chain/${encodeURIComponent(fieldId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blocks = await res.json();

      const modal = document.getElementById('ledgerAuditModal');
      const body = document.getElementById('ledgerAuditModalBody');
      if (modal && body) {
        body.innerHTML = `
          <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--accent-gold); margin-bottom: 0.5rem;">
            Evidence Chain for Field: <code>${escapeHtml(fieldId)}</code>
          </h4>
          <p style="font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 1rem;">
            Discovered <strong>${blocks.length}</strong> cryptographically hashed evidence block(s) securing this field.
          </p>
          <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 360px; overflow-y: auto;">
            ${blocks.map(b => `
              <div style="background: var(--bg-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.65rem; font-size: 0.78rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                  <span style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-gold);">Block #${b.sequence}</span>
                  <span class="badge ${b.verification_status === 'Verified' ? 'badge-verified' : 'badge-inferred'}" style="font-size: 0.68rem;">${b.verification_status}</span>
                </div>
                <div style="font-size: 0.74rem; color: var(--text-secondary); margin-bottom: 0.35rem;">${escapeHtml(b.proof_details)}</div>
                <div class="hash-pill" style="font-size: 0.68rem;">Hash: ${escapeHtml(b.current_hash)}</div>
              </div>
            `).join('')}
          </div>
        `;
        modal.style.display = 'flex';
      }
    } catch (err) {
      showToast('Failed to load field evidence chain: ' + err.message, 'error');
    }
  };

  window.copyToClipboard = function (text) {
    navigator.clipboard.writeText(text).then(() => {
      showToast('Copied SHA-256 hash to clipboard', 'info');
    }).catch(() => {
      showToast('Failed to copy to clipboard', 'error');
    });
  };

  function formatTimestamp(isoStr) {
    if (!isoStr) return '--';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoStr;
    }
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

  function debounce(fn, ms) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function showToast(message, type = 'info') {
    const hub = document.getElementById('toastContainer');
    if (!hub) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    hub.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('fade-out');
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

})();

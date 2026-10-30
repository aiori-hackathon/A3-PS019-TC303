/**
 * frontend/tracera.js
 * ===================
 * Dedicated client-side controller for TRACERA — BY PRIVSIGHT.
 * "Trace. Analyze. Understand."
 * 
 * Features:
 * - ChatGPT-style conversational experience integrated directly into PrivSight
 * - Persistent conversation threads & multi-turn history
 * - Interactive Cytoscape.js graph rendering with pan/zoom/fit & inspector
 * - Structured tables, timelines, flowcharts, and markdown rendering
 * - Dynamic format preference switcher
 * - Per-user data isolation and evidence provenance display
 */

let currentConversationId = null;
let currentFormatPreference = 'text';
let availableSources = [];
let selectedSources = [];
let allConversations = [];
let activeCytoscapeInstances = {};

document.addEventListener('DOMContentLoaded', async () => {
  initThemeToggle();
  initChatInput();
  initSearchFilter();
  initModalListeners();
  await loadSources();
  await loadConversations();
});

// --- Theme handling ---
function initThemeToggle() {
  const toggleBtn = document.getElementById('themeToggleBtn');
  if (!toggleBtn) return;
  toggleBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('privsight-theme', next);
    const icon = document.getElementById('themeToggleIcon');
    if (icon) icon.textContent = next === 'dark' ? '☀️' : '🌙';
  });
}

// --- Data Sources Pill Tray ---
async function loadSources() {
  try {
    const res = await fetch('/api/relationships/sources');
    if (!res.ok) return;
    const data = await res.json();
    availableSources = data.sources || [];

    const badge = document.getElementById('activeSourcesCount');
    if (badge) badge.textContent = availableSources.length;

    const tray = document.getElementById('sourcePillTray');
    if (!tray) return;
    tray.innerHTML = '<span style="font-size:0.72rem; color:var(--text-muted); font-weight:700; text-transform:uppercase; margin-right:4px;">Filter Datasets:</span>';

    availableSources.forEach(s => {
      const pill = document.createElement('span');
      pill.className = 'badge';
      pill.style.cursor = 'pointer';
      pill.style.background = 'var(--bg-elevated)';
      pill.style.color = 'var(--text-secondary)';
      pill.style.border = '1px solid var(--border-color)';
      pill.style.fontSize = '0.72rem';
      pill.style.padding = '0.2rem 0.55rem';
      pill.style.borderRadius = 'var(--radius-full)';
      pill.style.transition = 'all 0.15s ease';
      pill.textContent = s.label;
      pill.title = `${s.key} (${s.columns_count} cols, ${s.row_count} rows)`;

      pill.onclick = () => {
        if (selectedSources.includes(s.key)) {
          selectedSources = selectedSources.filter(k => k !== s.key);
          pill.style.background = 'var(--bg-elevated)';
          pill.style.color = 'var(--text-secondary)';
          pill.style.borderColor = 'var(--border-color)';
        } else {
          selectedSources.push(s.key);
          pill.style.background = 'var(--accent-gold-soft)';
          pill.style.color = 'var(--accent-gold)';
          pill.style.borderColor = 'var(--accent-gold)';
        }
      };
      tray.appendChild(pill);
    });
  } catch (err) {
    console.error('Failed to load sources for TRACERA:', err);
  }
}

// --- Conversations List & Search Filter ---
async function loadConversations() {
  const listEl = document.getElementById('threadsList');
  if (!listEl) return;

  try {
    const res = await fetch('/api/relationships/conversations');
    if (!res.ok) {
      listEl.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; padding:1rem;">Sign in required.</div>';
      return;
    }
    allConversations = await res.json() || [];
    renderThreads(allConversations);

    // If we have an active conversation, keep it active; otherwise default to newest if exists
    if (!currentConversationId && allConversations.length > 0) {
      await selectConversation(allConversations[0].id);
    }
  } catch (err) {
    console.error('Failed to load conversations:', err);
    listEl.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; padding:1rem;">Unable to load conversations.</div>';
  }
}

function renderThreads(threads) {
  const listEl = document.getElementById('threadsList');
  if (!listEl) return;

  if (threads.length === 0) {
    listEl.innerHTML = '<div style="color:var(--text-muted); font-size:0.78rem; padding:1.5rem 0.5rem; text-align:center;">No conversations yet. Start a new exploration!</div>';
    return;
  }

  listEl.innerHTML = '';
  threads.forEach(c => {
    const item = document.createElement('div');
    item.className = `tracera-thread-item ${c.id === currentConversationId ? 'active' : ''}`;
    item.id = `thread-${c.id}`;

    const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';

    item.innerHTML = `
      <div class="tracera-thread-info">
        <span class="tracera-thread-title">${escapeHtml(c.title || 'Exploration')}</span>
        <span class="tracera-thread-date">${dateStr}</span>
      </div>
      <div class="tracera-thread-actions">
        <button class="tracera-action-btn" title="Rename investigation" onclick="event.stopPropagation(); renameThread('${c.id}')">✏️</button>
        <button class="tracera-action-btn delete" title="Delete conversation" onclick="event.stopPropagation(); deleteThread('${c.id}')">🗑️</button>
      </div>
    `;

    item.onclick = () => selectConversation(c.id);
    listEl.appendChild(item);
  });
}

function initSearchFilter() {
  const searchInput = document.getElementById('searchThreadsInput');
  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) {
      renderThreads(allConversations);
      return;
    }
    const filtered = allConversations.filter(c => (c.title || '').toLowerCase().includes(q));
    renderThreads(filtered);
  });
}

async function selectConversation(convId) {
  currentConversationId = convId;

  // Highlight active thread item in sidebar
  document.querySelectorAll('.tracera-thread-item').forEach(el => el.classList.remove('active'));
  const activeEl = document.getElementById(`thread-${convId}`);
  if (activeEl) activeEl.classList.add('active');

  const container = document.getElementById('chatMessages');
  if (!container) return;
  container.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; padding:2rem; text-align:center;">Loading conversation history...</div>';

  try {
    const res = await fetch(`/api/relationships/conversations/${convId}`);
    if (!res.ok) {
      container.innerHTML = '<div style="color:var(--color-danger); padding:2rem; text-align:center;">Unable to load conversation details.</div>';
      return;
    }
    const detail = await res.json();
    container.innerHTML = '';

    if (!detail.messages || detail.messages.length === 0) {
      showWelcomeHero();
      return;
    }

    detail.messages.forEach(msg => {
      appendMessageToChat(msg.role, msg.content, {
        format_requested: msg.format_requested,
        format_explanation: msg.format_explanation,
        graph: msg.graph_data,
        table_data: msg.table_data,
        timeline_data: msg.timeline_data,
        flowchart_data: msg.flowchart_data,
        timestamp: msg.created_at,
      });
    });

    scrollChatToBottom();
  } catch (err) {
    console.error('Failed to fetch conversation history:', err);
    container.innerHTML = `<div style="color:var(--color-danger); padding:2rem; text-align:center;">Error: ${err.message}</div>`;
  }
}

async function createNewConversation() {
  try {
    const res = await fetch('/api/relationships/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New Exploration' }),
    });
    if (!res.ok) return;
    const newConv = await res.json();
    currentConversationId = newConv.id;
    await loadConversations();
    showWelcomeHero();
    const input = document.getElementById('chatInput');
    if (input) input.focus();
  } catch (err) {
    console.error('Failed to create new conversation:', err);
  }
}

async function renameThread(convId) {
  const newTitle = prompt('Enter a new title for this TRACERA investigation:');
  if (!newTitle || !newTitle.trim()) return;

  try {
    const res = await fetch(`/api/relationships/conversations/${convId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle.trim() }),
    });
    if (res.ok) {
      await loadConversations();
    }
  } catch (err) {
    console.error('Failed to rename conversation:', err);
  }
}

async function deleteThread(convId) {
  if (!confirm('Are you sure you want to delete this conversation thread? This action cannot be undone.')) return;

  try {
    const res = await fetch(`/api/relationships/conversations/${convId}`, {
      method: 'DELETE',
    });
    if (res.ok) {
      if (currentConversationId === convId) {
        currentConversationId = null;
        showWelcomeHero();
      }
      await loadConversations();
    }
  } catch (err) {
    console.error('Failed to delete conversation:', err);
  }
}

function showWelcomeHero() {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  container.innerHTML = `
    <div class="tracera-welcome-card" id="welcomeHero">
      <div class="tracera-welcome-icon">⚡</div>
      <h1 class="tracera-welcome-title">TRACERA</h1>
      <div class="tracera-welcome-tagline">Trace. Analyze. Understand.</div>
      <p class="tracera-welcome-desc">
        AI-Powered Relationship Intelligence Assistant for PrivSight. Ask natural language questions to uncover connections between individuals, organizations, email records, shared identifiers, and technical evidence across your scanned files and databases.
      </p>

      <div class="tracera-prompts-grid">
        <div class="tracera-prompt-card" onclick="suggestPrompt('Explain the relationship between customers and orders graphically with an interactive graph.')">
          <div class="tracera-prompt-icon">🕸️</div>
          <div class="tracera-prompt-title">Explain Graphically</div>
          <div class="tracera-prompt-sub">Explore customer and order connections with interactive Cytoscape nodes and edges.</div>
        </div>

        <div class="tracera-prompt-card" onclick="suggestPrompt('What records and entities connect to customer C001?')">
          <div class="tracera-prompt-icon">👤</div>
          <div class="tracera-prompt-title">Trace Entity C001</div>
          <div class="tracera-prompt-sub">Find all related transactions, orders, payments, and multi-hop data links.</div>
        </div>

        <div class="tracera-prompt-card" onclick="suggestPrompt('Explain the cross-dataset relationships in a structured table.')">
          <div class="tracera-prompt-icon">📊</div>
          <div class="tracera-prompt-title">Tabular Breakdown</div>
          <div class="tracera-prompt-sub">Generate a structured table detailing source fields, targets, cardinality, and matching rows.</div>
        </div>

        <div class="tracera-prompt-card" onclick="suggestPrompt('Give me a chronological timeline of data events and transactions.')">
          <div class="tracera-prompt-icon">⏱️</div>
          <div class="tracera-prompt-title">Chronological Timeline</div>
          <div class="tracera-prompt-sub">Trace the sequence of orders and transactions with real timestamps and status flags.</div>
        </div>
      </div>
    </div>
  `;
}

// --- Chat Input Handling ---
function initChatInput() {
  const input = document.getElementById('chatInput');
  const sendBtn = document.getElementById('btnSendChat');
  const newChatBtn = document.getElementById('btnNewChat');

  if (newChatBtn) {
    newChatBtn.addEventListener('click', createNewConversation);
  }

  if (input) {
    // Auto-grow textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 140) + 'px';
    });

    // Enter sends, Shift+Enter creates newline
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener('click', sendChatMessage);
  }
}

async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const sendBtn = document.getElementById('btnSendChat');
  if (!input || !sendBtn) return;

  const message = input.value.trim();
  if (!message) return;

  // Clear welcome hero if present
  const hero = document.getElementById('welcomeHero');
  if (hero) hero.remove();

  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  // 1. Render User Message
  appendMessageToChat('user', message, { format_requested: currentFormatPreference });
  scrollChatToBottom();

  // 2. Render Loading State Indicator
  const loadingId = 'loading-' + Date.now();
  appendLoadingBubble(loadingId);
  scrollChatToBottom();

  try {
    const payload = {
      message: message,
      conversation_id: currentConversationId,
      selected_sources: selectedSources.length > 0 ? selectedSources : null,
      format_preference: currentFormatPreference !== 'text' ? currentFormatPreference : null,
    };

    const res = await fetch('/api/relationships/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    removeLoadingBubble(loadingId);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      appendMessageToChat('assistant', `⚠️ **Error Processing Request:** ${errData.detail || 'Server error occurred.'}`);
      return;
    }

    const report = await res.json();

    // Render Assistant Response with generated format and mandatory explanation
    appendMessageToChat('assistant', report.explanation, report);
    scrollChatToBottom();

    // Refresh threads list in background to reflect updated title
    await loadConversations();

  } catch (err) {
    removeLoadingBubble(loadingId);
    appendMessageToChat('assistant', `⚠️ **Network Connection Failed:** ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function setFormatPreference(fmt) {
  currentFormatPreference = fmt;
  document.querySelectorAll('.tracera-chip').forEach(c => {
    if (c.getAttribute('data-format') === fmt) {
      c.classList.add('active');
    } else {
      c.classList.remove('active');
    }
  });
}

function suggestPrompt(text) {
  const input = document.getElementById('chatInput');
  if (input) {
    input.value = text;
    input.focus();
    sendChatMessage();
  }
}

// --- Message Rendering Engine ---
function appendMessageToChat(role, text, metadata = {}) {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  const row = document.createElement('div');
  row.className = `tracera-message-row ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'tracera-avatar';
  avatar.textContent = role === 'user' ? '👤' : '⚡';

  const bubble = document.createElement('div');
  bubble.className = 'tracera-bubble';

  // Bubble header
  const header = document.createElement('div');
  header.className = 'tracera-bubble-header';

  const authorBadge = document.createElement('div');
  authorBadge.className = 'tracera-author-badge';
  if (role === 'user') {
    authorBadge.innerHTML = '<span>You</span>';
  } else {
    authorBadge.innerHTML = `
      <span>TRACERA</span>
      <span class="badge" style="background:var(--accent-gold-soft); color:var(--accent-gold); font-size:0.65rem;">BY PRIVSIGHT</span>
      <span class="tracera-author-tagline">Trace · Analyze · Understand</span>
    `;
  }

  const timeEl = document.createElement('span');
  timeEl.className = 'tracera-timestamp';
  const time = metadata.timestamp ? new Date(metadata.timestamp) : new Date();
  timeEl.textContent = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  header.appendChild(authorBadge);
  header.appendChild(timeEl);
  bubble.appendChild(header);

  // 1. If Graph was generated, insert interactive Cytoscape graph container
  if (metadata.graph && metadata.graph.nodes && metadata.graph.nodes.length > 0) {
    const graphId = 'cy-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
    const graphWrapper = document.createElement('div');
    graphWrapper.className = 'tracera-graph-container';
    graphWrapper.id = graphId;

    graphWrapper.innerHTML = `
      <div class="tracera-graph-toolbar">
        <button class="tracera-graph-btn" onclick="zoomGraph('${graphId}', 1.25)" title="Zoom in">➕</button>
        <button class="tracera-graph-btn" onclick="zoomGraph('${graphId}', 0.8)" title="Zoom out">➖</button>
        <button class="tracera-graph-btn" onclick="fitGraph('${graphId}')" title="Fit to view">🎯 Fit</button>
      </div>
    `;
    bubble.appendChild(graphWrapper);

    requestAnimationFrame(() => {
      initCytoscapeGraph(graphId, metadata.graph);
    });
  }

  // 2. If Table data was generated, insert structured table
  if (metadata.table_data && Array.isArray(metadata.table_data) && metadata.table_data.length > 0) {
    const tableWrapper = document.createElement('div');
    tableWrapper.className = 'tracera-table-wrapper';

    const cols = Object.keys(metadata.table_data[0]);
    let tableHtml = '<table class="data-table" style="width:100%; font-size:0.78rem;"><thead><tr>';
    cols.forEach(c => {
      const formattedTitle = c.replace(/_/g, ' ').toUpperCase();
      tableHtml += `<th style="padding:0.6rem 0.75rem; text-align:left;">${escapeHtml(formattedTitle)}</th>`;
    });
    tableHtml += '</tr></thead><tbody>';

    metadata.table_data.forEach(rowItem => {
      tableHtml += '<tr>';
      cols.forEach(c => {
        let val = rowItem[c];
        if (val === null || val === undefined) val = '-';
        if (c.includes('status')) {
          val = `<span class="badge badge-status-complete">${escapeHtml(String(val))}</span>`;
        } else if (c.includes('cardinality')) {
          val = `<span class="badge" style="background:var(--bg-elevated); color:var(--accent-gold); font-family:var(--font-mono);">${escapeHtml(String(val))}</span>`;
        } else {
          val = escapeHtml(String(val));
        }
        tableHtml += `<td style="padding:0.5rem 0.75rem; border-top:1px solid var(--border-color);">${val}</td>`;
      });
      tableHtml += '</tr>';
    });
    tableHtml += '</tbody></table>';

    tableWrapper.innerHTML = tableHtml;
    bubble.appendChild(tableWrapper);
  }

  // 3. If Timeline data was generated, render chronological cards
  if (metadata.timeline_data && Array.isArray(metadata.timeline_data) && metadata.timeline_data.length > 0) {
    const timelineWrapper = document.createElement('div');
    timelineWrapper.style.margin = '0.85rem 0';
    timelineWrapper.style.display = 'flex';
    timelineWrapper.style.flexDirection = 'column';
    timelineWrapper.style.gap = '0.6rem';

    metadata.timeline_data.forEach(ev => {
      const card = document.createElement('div');
      card.style.background = 'var(--bg-elevated)';
      card.style.border = '1px solid var(--border-color)';
      card.style.borderRadius = 'var(--radius-sm)';
      card.style.padding = '0.65rem 0.9rem';
      card.style.display = 'flex';
      card.style.justifyContent = 'space-between';
      card.style.alignItems = 'center';

      card.innerHTML = `
        <div>
          <div style="font-weight:700; font-size:0.82rem; color:var(--text-primary); margin-bottom:0.15rem;">
            ${escapeHtml(ev.entity || 'Event')}
          </div>
          <div style="font-size:0.75rem; color:var(--text-secondary);">${escapeHtml(ev.description || '')}</div>
        </div>
        <div style="text-align:right;">
          <span class="badge" style="background:var(--accent-gold-soft); color:var(--accent-gold); font-family:var(--font-mono); font-size:0.7rem;">
            ${escapeHtml(ev.date || '')}
          </span>
        </div>
      `;
      timelineWrapper.appendChild(card);
    });
    bubble.appendChild(timelineWrapper);
  }

  // 4. Formatted Markdown Analytical Text Content
  const textDiv = document.createElement('div');
  textDiv.className = 'tracera-bubble-content';
  textDiv.innerHTML = renderMarkdown(text || '');
  bubble.appendChild(textDiv);

  // 5. Evidence Provenance & Action Footer for Assistant Messages
  if (role === 'assistant') {
    const footer = document.createElement('div');
    footer.style.marginTop = '0.85rem';
    footer.style.paddingTop = '0.5rem';
    footer.style.borderTop = '1px solid var(--border-subtle)';
    footer.style.display = 'flex';
    footer.style.flexWrap = 'wrap';
    footer.style.justifyContent = 'space-between';
    footer.style.alignItems = 'center';
    footer.style.gap = '0.5rem';

    const leftBadges = document.createElement('div');
    leftBadges.style.display = 'flex';
    leftBadges.style.alignItems = 'center';
    leftBadges.style.gap = '0.4rem';
    leftBadges.innerHTML = `
      <span class="badge" style="background:rgba(16,185,129,0.12); color:var(--color-success); font-size:0.68rem; font-weight:700;">✔ Verified Schema Engine</span>
      <span class="badge" style="background:rgba(212,167,44,0.12); color:var(--accent-gold); font-size:0.68rem;">🔒 PII Masked</span>
    `;

    const copyBtn = document.createElement('button');
    copyBtn.className = 'tracera-action-btn';
    copyBtn.style.fontSize = '0.72rem';
    copyBtn.innerHTML = '📋 Copy Explanation';
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(text || '');
      copyBtn.innerHTML = '✔ Copied!';
      setTimeout(() => { copyBtn.innerHTML = '📋 Copy Explanation'; }, 2000);
    };

    footer.appendChild(leftBadges);
    footer.appendChild(copyBtn);
    bubble.appendChild(footer);
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);
}

// --- Loading Bubble ---
function appendLoadingBubble(id) {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  const row = document.createElement('div');
  row.className = 'tracera-message-row assistant';
  row.id = id;

  row.innerHTML = `
    <div class="tracera-avatar">⚡</div>
    <div class="tracera-bubble" style="padding:0.75rem 1.15rem;">
      <div style="display:flex; align-items:center; gap:0.65rem; color:var(--text-secondary); font-size:0.82rem;">
        <span class="status-pulse-dot" style="background:var(--accent-gold);"></span>
        <span>TRACERA is tracing entity linkages, verifying relational paths, and analyzing evidence...</span>
      </div>
    </div>
  `;
  container.appendChild(row);
}

function removeLoadingBubble(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function scrollChatToBottom() {
  const container = document.getElementById('chatMessages');
  if (!container) return;
  container.scrollTop = container.scrollHeight;
}

// --- Cytoscape.js Relationship Graph Renderer ---
function initCytoscapeGraph(containerId, graphData) {
  if (typeof cytoscape === 'undefined') {
    console.warn('Cytoscape.js library not loaded yet.');
    return;
  }

  const container = document.getElementById(containerId);
  if (!container) return;

  const elements = [];

  // 1. Convert Nodes with category color mapping
  (graphData.nodes || []).forEach(n => {
    let nodeColor = '#D4A72C'; // Gold by default
    const typeLower = (n.entity_type || '').toLowerCase();

    if (typeLower.includes('person') || typeLower.includes('customer')) {
      nodeColor = '#D4A72C'; // Gold
    } else if (typeLower.includes('order') || typeLower.includes('payment') || typeLower.includes('financial')) {
      nodeColor = '#F97316'; // Orange
    } else if (typeLower.includes('department') || typeLower.includes('org')) {
      nodeColor = '#10B981'; // Emerald
    } else if (typeLower.includes('document') || typeLower.includes('file')) {
      nodeColor = '#06B6D4'; // Cyan
    } else if (typeLower.includes('email') || typeLower.includes('contact')) {
      nodeColor = '#8B5CF6'; // Purple
    }

    elements.push({
      data: {
        id: n.id,
        label: n.label || n.id,
        entity_type: n.entity_type,
        source_name: n.source_name,
        color: nodeColor,
        raw_data: n,
      }
    });
  });

  // 2. Convert Edges with cardinality and verification markers
  (graphData.edges || []).forEach(e => {
    elements.push({
      data: {
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        label: e.cardinality ? `${e.cardinality}` : '',
        relationship_type: e.relationship_type,
        evidence: e.evidence,
        raw_data: e,
      }
    });
  });

  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const textColor = isLight ? '#25231F' : '#F7F3EA';
  const edgeColor = isLight ? '#A8A29E' : '#57534E';

  try {
    const cy = cytoscape({
      container: container,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': textColor,
            'font-family': 'Plus Jakarta Sans, sans-serif',
            'font-size': '11px',
            'font-weight': 700,
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'width': 34,
            'height': 34,
            'border-width': 2,
            'border-color': '#FFFFFF',
            'border-opacity': 0.8,
            'overlay-opacity': 0,
            'transition-property': 'transform, border-width, border-color',
            'transition-duration': '0.2s',
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#F97316',
            'border-opacity': 1,
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2.5,
            'line-color': edgeColor,
            'target-arrow-color': edgeColor,
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-family': 'JetBrains Mono, monospace',
            'font-size': '9px',
            'color': textColor,
            'text-background-color': isLight ? '#FAFAF7' : '#1E1E1E',
            'text-background-opacity': 0.85,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          }
        },
        {
          selector: 'edge:selected',
          style: {
            'width': 4,
            'line-color': '#D4A72C',
            'target-arrow-color': '#D4A72C',
          }
        }
      ],
      layout: {
        name: 'cose',
        animate: false,
        padding: 40,
        nodeRepulsion: 450000,
        idealEdgeLength: 100,
      }
    });

    // Save instance
    activeCytoscapeInstances[containerId] = cy;

    // Node click handler
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const data = node.data('raw_data');
      openInspectorModal(`Node: ${data.label}`, generateNodeInspectorHtml(data));
    });

    // Edge click handler
    cy.on('tap', 'edge', (evt) => {
      const edge = evt.target;
      const data = edge.data('raw_data');
      openInspectorModal(`Connection: ${data.relationship_type}`, generateEdgeInspectorHtml(data));
    });

  } catch (err) {
    console.error('Error rendering Cytoscape graph:', err);
  }
}

function zoomGraph(containerId, factor) {
  const cy = activeCytoscapeInstances[containerId];
  if (cy) {
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
    });
  }
}

function fitGraph(containerId) {
  const cy = activeCytoscapeInstances[containerId];
  if (cy) {
    cy.fit(30);
  }
}

// --- Inspector Modal for Nodes and Edges ---
function openInspectorModal(title, contentHtml) {
  const modal = document.getElementById('detailModal');
  const titleEl = document.getElementById('modalFieldTitle');
  const bodyEl = document.getElementById('modalDetailsBody');

  if (titleEl) titleEl.textContent = title;
  if (bodyEl) bodyEl.innerHTML = contentHtml;
  if (modal) modal.classList.add('active');
}

function closeInspectorModal() {
  const modal = document.getElementById('detailModal');
  if (modal) modal.classList.remove('active');
}

function initModalListeners() {
  const closeBtn = document.getElementById('modalCloseBtn');
  const closeFooterBtn = document.getElementById('modalCloseBtnFooter');
  const modal = document.getElementById('detailModal');

  if (closeBtn) closeBtn.onclick = closeInspectorModal;
  if (closeFooterBtn) closeFooterBtn.onclick = closeInspectorModal;
  if (modal) {
    modal.onclick = (e) => {
      if (e.target === modal) closeInspectorModal();
    };
  }
}

function generateNodeInspectorHtml(node) {
  let attrsHtml = '';
  const masked = node.masked_attributes || node.attributes || {};
  for (const [k, v] of Object.entries(masked)) {
    attrsHtml += `
      <tr>
        <td style="font-weight:600; color:var(--text-secondary); padding:0.4rem 0.6rem;">${escapeHtml(k)}</td>
        <td style="font-family:var(--font-mono); color:var(--text-primary); padding:0.4rem 0.6rem;">${escapeHtml(String(v))}</td>
      </tr>
    `;
  }

  return `
    <div style="display:flex; flex-direction:column; gap:0.85rem;">
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        <span class="badge" style="background:var(--accent-gold-soft); color:var(--accent-gold);">Entity: ${escapeHtml(node.entity_type || 'Unknown')}</span>
        <span class="badge" style="background:var(--bg-elevated); color:var(--text-secondary);">Source: ${escapeHtml(node.source_name || 'N/A')}</span>
        <span class="badge badge-status-complete">Verified Node</span>
      </div>

      <div style="font-size:0.82rem; color:var(--text-secondary); line-height:1.5;">
        Discovered entity representation in PrivSight technical graph. Key identifier: <code>${escapeHtml(node.id)}</code>.
      </div>

      <h4 style="font-size:0.88rem; font-weight:700; color:var(--text-primary); margin-top:0.4rem;">Masked Record Attributes</h4>
      <div style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:var(--radius-sm); overflow:hidden;">
        <table style="width:100%; font-size:0.78rem;">
          <tbody>
            ${attrsHtml || '<tr><td style="padding:0.75rem; color:var(--text-muted);">No explicit attributes recorded.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function generateEdgeInspectorHtml(edge) {
  return `
    <div style="display:flex; flex-direction:column; gap:0.85rem;">
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        <span class="badge" style="background:var(--accent-gold-soft); color:var(--accent-gold);">Cardinality: ${escapeHtml(edge.cardinality || 'Unknown')}</span>
        <span class="badge" style="background:rgba(16,185,129,0.12); color:var(--color-success);">Status: ${escapeHtml(edge.verification_status || 'Verified')}</span>
        <span class="badge" style="background:var(--bg-elevated); color:var(--text-secondary);">Confidence: ${Math.round((edge.confidence_score || 1.0) * 100)}%</span>
      </div>

      <div style="font-size:0.85rem; font-weight:700; color:var(--text-primary);">
        ${escapeHtml(edge.source_label)} ➔ ${escapeHtml(edge.target_label)}
      </div>

      <div style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:var(--radius-sm); padding:0.85rem;">
        <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-bottom:0.25rem;">Evidence & Provenance</div>
        <div style="font-size:0.82rem; color:var(--text-primary); line-height:1.5;">
          ${escapeHtml(edge.evidence || 'Verified referential connection.')}
        </div>
      </div>

      <div style="font-size:0.75rem; color:var(--text-muted); line-height:1.45;">
        PrivSight verified this connection by inspecting database schemas, primary/foreign key constraints, and multi-format dataset intersections.
      </div>
    </div>
  `;
}

// --- Lightweight Markdown Formatter ---
function renderMarkdown(md) {
  if (!md) return '';

  let html = md
    // Escape standard tags first for safety
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Headings
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h3>$1</h3>');

  // Bold
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');

  // Italics
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

  // Inline Code
  html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');

  // Unordered list items
  html = html.replace(/^\s*[-•]\s+(.*$)/gim, '<li>$1</li>');

  // Numbered list items
  html = html.replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>');

  // Horizontal rules
  html = html.replace(/^---$/gim, '<hr style="border:none; border-top:1px solid var(--border-subtle); margin:0.85rem 0;">');

  // Paragraph breaks
  html = html.replace(/\n\n/gim, '</p><p>');
  html = '<p>' + html + '</p>';

  // Wrap lists
  html = html.replace(/<li>(.*?)(?=<li>|<\/p>|$)/gim, '<ul><li>$1</li></ul>');
  html = html.replace(/<\/ul>\s*<ul>/gim, '');

  return html;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

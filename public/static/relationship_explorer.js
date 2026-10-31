/**
 * frontend/relationship_explorer.js
 * =================================
 * Full interactive controller for the PrivSight AI Relationship Intelligence Assistant.
 * Handles:
 * - Real-time conversational interface with ChatGPT-like experience
 * - Persistent conversation threads & history retrieval
 * - Cytoscape.js interactive graph rendering inside chat messages
 * - Tabular, Timeline, and Flowchart visualization embedding
 * - Detailed node & edge inspection with privacy-masked PII
 * - Multi-turn follow-up queries and format switching
 */

let currentConversationId = null;
let currentFormatPreference = 'text';
let availableSources = [];
let selectedSources = [];
let activeCytoscapeInstances = {};

document.addEventListener('DOMContentLoaded', async () => {
  initThemeToggle();
  initChatInput();
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

// --- Source Selection ---
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
    tray.innerHTML = '<span style="font-size:0.72rem; color:var(--text-muted); line-height:22px; margin-right:4px;">Filter Sources:</span>';

    availableSources.forEach(s => {
      const pill = document.createElement('span');
      pill.className = 'source-pill';
      pill.textContent = s.label;
      pill.title = `${s.key} (${s.columns_count} cols, ${s.row_count} rows)`;
      pill.onclick = () => {
        if (selectedSources.includes(s.key)) {
          selectedSources = selectedSources.filter(k => k !== s.key);
          pill.classList.remove('selected');
        } else {
          selectedSources.push(s.key);
          pill.classList.add('selected');
        }
      };
      tray.appendChild(pill);
    });
  } catch (err) {
    console.error('Failed to load sources:', err);
  }
}

// --- Conversations List & Switcher ---
async function loadConversations() {
  const listEl = document.getElementById('threadsList');
  if (!listEl) return;

  try {
    const res = await fetch('/api/relationships/conversations');
    if (!res.ok) {
      listEl.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; padding:1rem;">Sign in required.</div>';
      return;
    }
    const convs = await res.json();
    if (!convs || convs.length === 0) {
      listEl.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; padding:1.5rem 0.5rem; text-align:center;">No previous chats yet. Start a new exploration!</div>';
      return;
    }

    listEl.innerHTML = '';
    convs.forEach(c => {
      const item = document.createElement('div');
      item.className = `thread-item ${c.id === currentConversationId ? 'active' : ''}`;
      item.id = `thread-${c.id}`;

      item.innerHTML = `
        <span class="thread-title" title="${escapeHtml(c.title)}">💬 ${escapeHtml(c.title)}</span>
        <div class="thread-actions">
          <button class="btn-thread-action" title="Rename" onclick="renameConversation(event, '${c.id}')">✏️</button>
          <button class="btn-thread-action" title="Delete" onclick="deleteConversation(event, '${c.id}')">🗑️</button>
        </div>
      `;

      item.onclick = (e) => {
        if (e.target.closest('.btn-thread-action')) return;
        selectConversation(c.id, c.title);
      };

      listEl.appendChild(item);
    });

    // Auto-select latest if none selected
    if (!currentConversationId && convs.length > 0) {
      selectConversation(convs[0].id, convs[0].title);
    }
  } catch (err) {
    console.error('Failed to load conversations:', err);
  }
}

document.getElementById('btnNewChat')?.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/relationships/conversations?title=New%20Exploration', { method: 'POST' });
    if (!res.ok) return;
    const newConv = await res.json();
    await loadConversations();
    selectConversation(newConv.id, newConv.title);
  } catch (err) {
    console.error('Failed to create new conversation:', err);
  }
});

async function selectConversation(convId, title) {
  currentConversationId = convId;
  const badge = document.getElementById('activeConvTitleBadge');
  if (badge) badge.textContent = title;

  document.querySelectorAll('.thread-item').forEach(el => el.classList.remove('active'));
  document.getElementById(`thread-${convId}`)?.classList.add('active');

  // Load message history
  const container = document.getElementById('chatMessages');
  if (!container) return;
  container.innerHTML = '<div style="color:var(--text-muted); padding:2rem; text-align:center;">Loading conversation messages...</div>';

  try {
    const res = await fetch(`/api/relationships/conversations/${convId}`);
    if (!res.ok) return;
    const detail = await res.json();
    container.innerHTML = '';

    if (!detail.messages || detail.messages.length === 0) {
      container.innerHTML = `
        <div class="message-row assistant">
          <div class="message-avatar">AI</div>
          <div class="message-bubble">
            <p><strong>Exploration Thread Started</strong></p>
            <p>Ask any relationship question about your entities, datasets, or individuals (e.g. <em>"Show the connection between customers and orders."</em>).</p>
          </div>
        </div>
      `;
      return;
    }

    detail.messages.forEach(msg => {
      appendMessageToChat(msg.role, msg.content, {
        format_requested: msg.format_requested,
        format_explanation: msg.format_explanation,
        graph: msg.graph_data,
        table_data: msg.table_data,
        timeline_data: msg.timeline_data,
        created_at: msg.created_at,
      });
    });

    scrollChatToBottom();
  } catch (err) {
    console.error('Failed to load conversation history:', err);
  }
}

async function renameConversation(e, convId) {
  e.stopPropagation();
  const currentTitle = prompt('Enter a new title for this conversation:');
  if (!currentTitle || !currentTitle.trim()) return;

  try {
    const res = await fetch(`/api/relationships/conversations/${convId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: currentTitle.trim() }),
    });
    if (res.ok) {
      await loadConversations();
    }
  } catch (err) {
    console.error('Failed to rename conversation:', err);
  }
}

async function deleteConversation(e, convId) {
  e.stopPropagation();
  if (!confirm('Are you sure you want to delete this conversation?')) return;

  try {
    const res = await fetch(`/api/relationships/conversations/${convId}`, { method: 'DELETE' });
    if (res.ok) {
      if (currentConversationId === convId) {
        currentConversationId = null;
      }
      await loadConversations();
    }
  } catch (err) {
    console.error('Failed to delete conversation:', err);
  }
}

// --- Chat Form & Input Handling ---
function initChatInput() {
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatInput');
  const sendBtn = document.getElementById('btnSendChat');

  if (!form || !input) return;

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event('submit'));
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    sendBtn.disabled = true;

    // 1. Render User Message immediately
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
  });
}

function setFormatPreference(fmt) {
  currentFormatPreference = fmt;
  document.querySelectorAll('.format-chip').forEach(c => {
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
  }
}

// --- Message Rendering Engine ---
function appendMessageToChat(role, text, metadata = {}) {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? 'U' : 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  // 1. If Graph was generated, insert interactive Cytoscape graph container
  if (metadata.graph && metadata.graph.nodes && metadata.graph.nodes.length > 0) {
    const graphId = 'cy-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
    const graphWrapper = document.createElement('div');
    graphWrapper.className = 'embedded-graph-container';
    graphWrapper.id = graphId;

    graphWrapper.innerHTML = `
      <div class="graph-controls-overlay">
        <button class="btn-graph-ctrl" onclick="zoomGraph('${graphId}', 1.25)">➕</button>
        <button class="btn-graph-ctrl" onclick="zoomGraph('${graphId}', 0.8)">➖</button>
        <button class="btn-graph-ctrl" onclick="fitGraph('${graphId}')">🎯 Fit</button>
      </div>
    `;
    bubble.appendChild(graphWrapper);

    // Initialize Cytoscape in next animation frame
    requestAnimationFrame(() => {
      initCytoscapeGraph(graphId, metadata.graph);
    });
  }

  // 2. If Table was generated, render structured HTML table
  if (metadata.table_data && metadata.table_data.length > 0) {
    const tableWrapper = document.createElement('div');
    tableWrapper.className = 'embedded-table-container';

    let tableHtml = `
      <table class="embedded-table">
        <thead>
          <tr>
            <th>Source Entity</th>
            <th>Field</th>
            <th>Target Entity</th>
            <th>Target Field</th>
            <th>Relationship</th>
            <th>Cardinality</th>
            <th>Status</th>
            <th>Match Count</th>
          </tr>
        </thead>
        <tbody>
    `;

    metadata.table_data.forEach(r => {
      const statusBadge = r.verification_status === 'Verified' ?
        '<span class="badge" style="background:var(--color-success-bg); color:var(--color-success);">Verified</span>' :
        '<span class="badge" style="background:var(--color-warning-bg); color:var(--color-warning);">Possible</span>';

      tableHtml += `
        <tr>
          <td><strong>${escapeHtml(r.source_entity)}</strong></td>
          <td><code>${escapeHtml(r.source_field)}</code></td>
          <td><strong>${escapeHtml(r.target_entity)}</strong></td>
          <td><code>${escapeHtml(r.target_field)}</code></td>
          <td>${escapeHtml(r.relationship)}</td>
          <td><code>${escapeHtml(r.cardinality)}</code></td>
          <td>${statusBadge}</td>
          <td>${r.matching_records || 0} records</td>
        </tr>
      `;
    });

    tableHtml += `</tbody></table>`;
    tableWrapper.innerHTML = tableHtml;
    bubble.appendChild(tableWrapper);
  }

  // 3. If Timeline was generated, render chronological timeline
  if (metadata.timeline_data && metadata.timeline_data.length > 0) {
    const timelineWrapper = document.createElement('div');
    timelineWrapper.className = 'embedded-timeline';

    metadata.timeline_data.forEach(t => {
      const node = document.createElement('div');
      node.className = 'timeline-node';
      node.innerHTML = `
        <div style="font-size:0.75rem; color:var(--gold-warm); font-weight:700;">${escapeHtml(t.date)} · ${escapeHtml(t.entity)}</div>
        <div style="font-size:0.85rem; color:var(--text-primary); margin-top:2px;">${escapeHtml(t.description)}</div>
      `;
      timelineWrapper.appendChild(node);
    });
    bubble.appendChild(timelineWrapper);
  }

  // 4. Render Markdown Content Body
  const contentEl = document.createElement('div');
  contentEl.innerHTML = formatMarkdown(text);
  bubble.appendChild(contentEl);

  // Time & Copy footer
  const footer = document.createElement('div');
  footer.className = 'message-time';
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  footer.innerHTML = `
    <span>${timeStr}</span>
    ${role === 'assistant' ? `· <button class="btn-copy-msg" onclick="copyMessageText(this)">Copy Response</button>` : ''}
  `;
  bubble.appendChild(footer);

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);
}

function appendLoadingBubble(id) {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.id = id;

  row.innerHTML = `
    <div class="message-avatar">AI</div>
    <div class="message-bubble" style="display:flex; align-items:center; gap:0.5rem; color:var(--text-muted);">
      <span class="spinner" style="width:16px; height:16px; border-width:2px;"></span>
      <span>Analyzing schemas, tracing primary/foreign keys & synthesizing explanation...</span>
    </div>
  `;
  container.appendChild(row);
}

function removeLoadingBubble(id) {
  document.getElementById(id)?.remove();
}

function scrollChatToBottom() {
  const container = document.getElementById('chatMessages');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// --- Cytoscape.js Relationship Graph Renderer ---
function initCytoscapeGraph(elementId, graphData) {
  const container = document.getElementById(elementId);
  if (!container || !window.cytoscape) return;

  const elements = [];

  // Add Nodes
  graphData.nodes.forEach(n => {
    let color = '#D4A72C'; // gold default
    if (n.entity_type === 'Person') color = '#3B82F6';
    if (n.entity_type === 'Department') color = '#8B5CF6';
    if (n.entity_type === 'Transaction') color = '#10B981';
    if (n.entity_type === 'Payment') color = '#F97316';
    if (n.entity_type === 'Document') color = '#6B7280';

    elements.push({
      data: {
        id: n.id,
        label: n.label,
        entity_type: n.entity_type,
        source_name: n.source_name,
        color: color,
        raw_attributes: n.attributes || {},
      },
    });
  });

  // Add Edges
  graphData.edges.forEach(e => {
    elements.push({
      data: {
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        label: `${e.source_field} (${e.cardinality})`,
        cardinality: e.cardinality,
        status: e.verification_status,
        evidence: e.evidence,
        source_field: e.source_field,
        target_field: e.target_field,
      },
    });
  });

  const cy = cytoscape({
    container: container,
    elements: elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'label': 'data(label)',
          'color': '#ffffff',
          'font-family': 'Plus Jakarta Sans, sans-serif',
          'font-size': '11px',
          'font-weight': 'bold',
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'width': '65px',
          'height': '65px',
          'border-width': 2,
          'border-color': 'rgba(255, 255, 255, 0.3)',
          'text-shadow-color': '#000000',
          'text-shadow-blur': 4,
          'text-shadow-opacity': 0.8,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 4,
          'border-color': '#F4B942',
          'box-shadow': '0 0 12px #F4B942',
        },
      },
      {
        selector: 'edge',
        style: {
          'width': 2.5,
          'line-color': '#777',
          'target-arrow-color': '#F97316',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'color': '#F4B942',
          'font-size': '9px',
          'font-family': 'JetBrains Mono, monospace',
          'text-background-color': '#111111',
          'text-background-opacity': 0.85,
          'text-background-padding': '2px',
        },
      },
      {
        selector: 'edge:selected',
        style: {
          'width': 4,
          'line-color': '#F97316',
        },
      },
    ],
    layout: {
      name: 'cose',
      idealEdgeLength: 100,
      nodeOverlap: 20,
      refresh: 20,
      fit: true,
      padding: 30,
      randomize: false,
      componentSpacing: 100,
      nodeRepulsion: 400000,
      edgeElasticity: 100,
    },
  });

  // Node Click -> Details Inspector
  cy.on('tap', 'node', (evt) => {
    const node = evt.target;
    showDetailOverlay(
      `Entity: ${node.data('label')}`,
      `
        <div><strong>Type:</strong> ${node.data('entity_type')}</div>
        <div><strong>Source:</strong> <code>${node.data('source_name')}</code></div>
        <div style="margin-top:0.4rem;"><strong>Attributes:</strong></div>
        <pre style="background:var(--bg-subtle); padding:6px; font-size:0.75rem; border-radius:4px; max-height:140px; overflow-y:auto;">${escapeHtml(JSON.stringify(node.data('raw_attributes'), null, 2))}</pre>
      `
    );
  });

  // Edge Click -> Relationship Evidence Inspector
  cy.on('tap', 'edge', (evt) => {
    const edge = evt.target;
    showDetailOverlay(
      `Relationship Connection`,
      `
        <div><strong>Source Field:</strong> <code>${edge.data('source_field')}</code></div>
        <div><strong>Target Field:</strong> <code>${edge.data('target_field')}</code></div>
        <div><strong>Cardinality:</strong> <code>${edge.data('cardinality')}</code></div>
        <div><strong>Status:</strong> <span class="badge" style="background:var(--color-success-bg); color:var(--color-success);">${edge.data('status')}</span></div>
        <div style="margin-top:0.5rem;"><strong>Supporting Evidence:</strong></div>
        <p style="font-size:0.78rem; color:var(--text-primary); margin-top:4px;">${escapeHtml(edge.data('evidence'))}</p>
      `
    );
  });

  activeCytoscapeInstances[elementId] = cy;
}

function zoomGraph(id, factor) {
  const cy = activeCytoscapeInstances[id];
  if (cy) {
    cy.zoom(cy.zoom() * factor);
  }
}

function fitGraph(id) {
  const cy = activeCytoscapeInstances[id];
  if (cy) {
    cy.fit();
  }
}

// --- Detail Inspector Overlay ---
function showDetailOverlay(title, htmlContent) {
  const overlay = document.getElementById('elementDetailOverlay');
  const titleEl = document.getElementById('overlayTitle');
  const contentEl = document.getElementById('overlayContent');

  if (!overlay || !titleEl || !contentEl) return;
  titleEl.textContent = title;
  contentEl.innerHTML = htmlContent;
  overlay.style.display = 'block';
}

function closeDetailOverlay() {
  const overlay = document.getElementById('elementDetailOverlay');
  if (overlay) overlay.style.display = 'none';
}

// --- Utility Functions ---
function formatMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

  // Inline Code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Line breaks to paragraphs
  const paragraphs = html.split('\n\n');
  return paragraphs.map(p => {
    p = p.trim();
    if (p.startsWith('<h4>') || p.startsWith('<h3>')) return p;
    if (p.startsWith('- ') || p.startsWith('• ') || p.startsWith('1. ')) {
      const items = p.split('\n').map(li => {
        return `<li>${li.replace(/^[-•\d.]+\s*/, '')}</li>`;
      }).join('');
      return `<ul>${items}</ul>`;
    }
    return `<p>${p.replace(/\n/g, '<br>')}</p>`;
  }).join('');
}

function escapeHtml(str) {
  if (typeof str !== 'string') return String(str || '');
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function copyMessageText(btn) {
  const bubble = btn.closest('.message-bubble');
  if (!bubble) return;
  const clone = bubble.cloneNode(true);
  clone.querySelectorAll('.message-time, .embedded-graph-container, .embedded-table-container').forEach(el => el.remove());
  const text = clone.innerText.trim();
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy Response'; }, 2000);
  });
}

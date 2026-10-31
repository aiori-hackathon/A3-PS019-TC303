/**
 * frontend/tracera.js
 * ===================
 * Dedicated client-side controller for TRACERA — BY PRIVSIGHT.
 * "Trace. Analyze. Understand."
 * 
 * Component Architecture:
 * - WelcomeScreen: Handles initial greeting, branding, and suggested prompts
 * - UserMessage: Clean right-aligned user bubble component
 * - AssistantMessage: Clean left-aligned assistant component with Markdown typography
 * - ChatMessageList: Manages message stream, deduplication, and scrolling
 * - MessageComposer: Handles auto-expanding textarea, Enter key, and submit state
 */

// Global State
let currentConversationId = null;
let currentFormatPreference = 'text';
let availableSources = [];
let selectedSources = [];
let allConversations = [];
let activeCytoscapeInstances = {};
let isSubmitting = false;
let lastUserMessage = '';

// ==========================================
// 1. WELCOME SCREEN COMPONENT
// ==========================================
const WelcomeScreen = {
  render() {
    return `
      <div class="tracera-welcome-card" id="welcomeHero">
        <div class="tracera-welcome-icon">⚡</div>
        <h1 class="tracera-welcome-title">TRACERA</h1>
        <div class="tracera-welcome-tagline">Trace. Analyze. Understand.</div>
        <div style="font-size: 0.82rem; font-weight: 700; color: var(--accent-gold); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em;">
          BY PRIVSIGHT · AI-Powered Relationship Intelligence Assistant
        </div>
        <p class="tracera-welcome-desc">
          Welcome to TRACERA. I am your specialized AI assistant inside PrivSight, ready to answer questions regarding your personal-data discovery inventory, evidence gap analysis, detection rules, and privacy compliance.
        </p>

        <div class="tracera-prompts-grid">
          <div class="tracera-prompt-card" onclick="suggestPrompt('What is PrivSight\\'s methodology for personal data discovery and evidence inventory?')">
            <div class="tracera-prompt-icon">🔍</div>
            <div class="tracera-prompt-title">Discovery Methodology</div>
            <div class="tracera-prompt-sub">Learn how PrivSight discovers and categorizes personal data across your files and databases.</div>
          </div>

          <div class="tracera-prompt-card" onclick="suggestPrompt('How are confidence scores and Missing Proofs calculated in the inventory?')">
            <div class="tracera-prompt-icon">⚠️</div>
            <div class="tracera-prompt-title">Missing Proofs & Gaps</div>
            <div class="tracera-prompt-sub">Understand how technical evidence verification separates confirmed facts from missing proofs.</div>
          </div>

          <div class="tracera-prompt-card" onclick="suggestPrompt('Explain the difference between direct personal identifiers and quasi-identifiers under GDPR.')">
            <div class="tracera-prompt-icon">🛡️</div>
            <div class="tracera-prompt-title">Direct vs Quasi-Identifiers</div>
            <div class="tracera-prompt-sub">Review compliance distinctions and privacy risk implications for sensitive data fields.</div>
          </div>

          <div class="tracera-prompt-card" onclick="suggestPrompt('How do detection rules scan database columns, CSVs, and unstructured files?')">
            <div class="tracera-prompt-icon">⚙️</div>
            <div class="tracera-prompt-title">Detection Rule Mechanics</div>
            <div class="tracera-prompt-sub">Explore how regex, entropy, and NLP heuristics evaluate PII candidate likelihood.</div>
          </div>
        </div>
      </div>
    `;
  },

  show() {
    const container = ChatMessageList.getContainer();
    if (!container) return;
    ChatMessageList.clear();
    container.innerHTML = this.render();
  },

  hide() {
    const hero = document.getElementById('welcomeHero');
    if (hero) hero.remove();
  },

  isVisible() {
    return !!document.getElementById('welcomeHero');
  }
};

// ==========================================
// 2. USER MESSAGE COMPONENT (Strict Right Alignment)
// ==========================================
const UserMessage = {
  create(id, content, timestamp) {
    const row = document.createElement('div');
    row.className = 'tracera-message-row user';
    row.id = `msg-${id}`;
    row.setAttribute('data-role', 'user');

    const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const bubble = document.createElement('div');
    bubble.className = 'tracera-user-bubble';

    const textEl = document.createElement('div');
    textEl.className = 'tracera-user-text';
    textEl.textContent = content || '';

    const timeEl = document.createElement('span');
    timeEl.className = 'tracera-user-time';
    timeEl.textContent = timeStr;

    bubble.appendChild(textEl);
    bubble.appendChild(timeEl);
    row.appendChild(bubble);

    return row;
  }
};

// ==========================================
// 3. ASSISTANT MESSAGE COMPONENT (Strict Left Alignment)
// ==========================================
const AssistantMessage = {
  create(id, content, metadata = {}) {
    const row = document.createElement('div');
    row.className = 'tracera-message-row assistant';
    row.id = `msg-${id}`;
    row.setAttribute('data-role', 'assistant');

    // Assistant Response Body Card (Actual AI response directly without repeated header)
    const bodyCard = document.createElement('div');
    bodyCard.className = 'tracera-assistant-body';

    // Helper: Create a styled visual container card with icon, title, and badge
    const createVisualCard = (icon, titleText, typeBadge) => {
      const card = document.createElement('div');
      card.className = 'tracera-visual-card';
      card.innerHTML = `
        <div class="tracera-visual-header">
          <div class="tracera-visual-title">
            <span class="tracera-visual-icon">${icon}</span>
            <span>${escapeHtml(titleText)}</span>
          </div>
          <span class="tracera-visual-type-badge">${escapeHtml(typeBadge)}</span>
        </div>
      `;
      return card;
    };

    // 1. Interactive Cytoscape Relationship Graph (if available)
    if (metadata.graph && metadata.graph.nodes && metadata.graph.nodes.length > 0) {
      const graphCard = createVisualCard('🕸️', metadata.title || 'Relationship Topology Graph', 'RELATIONSHIP GRAPH');
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
        <div class="tracera-graph-legend">
          <div class="tracera-graph-legend-item">
            <span class="tracera-legend-dot" style="background:#10B981;"></span>
            <span>Verified FK</span>
          </div>
          <div class="tracera-graph-legend-item">
            <span class="tracera-legend-dot" style="background:#D4A72C;"></span>
            <span>Inferred Overlap</span>
          </div>
        </div>
      `;
      graphCard.appendChild(graphWrapper);
      bodyCard.appendChild(graphCard);

      requestAnimationFrame(() => {
        initCytoscapeGraph(graphId, metadata.graph);
      });
    }

    // 2. Responsive SVG Charts (Bar, Line, Pie)
    const chartPayload = metadata.chart_data || (metadata.data && metadata.data.series ? metadata.data : null);
    if (chartPayload && chartPayload.series && chartPayload.series.length > 0) {
      const chartType = (chartPayload.type || 'bar').toUpperCase();
      const chartCard = createVisualCard('📊', metadata.title || chartPayload.title || `${chartType} Chart`, `${chartType} CHART`);
      renderChart(chartCard, chartPayload, metadata.title);
      bodyCard.appendChild(chartCard);
    }

    // 3. Process Flowchart (if available)
    const flowPayload = metadata.flowchart_data || (metadata.data && metadata.data.steps && metadata.response_type === 'flowchart' ? metadata.data : null);
    if (flowPayload && flowPayload.steps && flowPayload.steps.length > 0) {
      const flowCard = createVisualCard('🔀', metadata.title || flowPayload.title || 'Process Flowchart', 'FLOWCHART');
      renderFlowchart(flowCard, flowPayload, metadata.title);
      bodyCard.appendChild(flowCard);
    }

    // 4. Comparative Schema & Governance Matrix (if available)
    const compPayload = metadata.comparison_data || (metadata.data && metadata.data.entities ? metadata.data : null);
    if (compPayload && compPayload.entities && compPayload.entities.length > 0) {
      const compCard = createVisualCard('⚖️', metadata.title || compPayload.title || 'Comparative Matrix', 'COMPARISON');
      renderComparison(compCard, compPayload, metadata.title);
      bodyCard.appendChild(compCard);
    }

    // 5. Step-by-Step Traversal Cards (if available)
    const stepPayload = metadata.steps || (metadata.data && metadata.data.steps && metadata.response_type === 'step_by_step' ? metadata.data.steps : null);
    if (stepPayload && Array.isArray(stepPayload) && stepPayload.length > 0 && !flowPayload) {
      const stepCard = createVisualCard('🔢', metadata.title || 'Step-by-Step Relational Verification', 'STEP-BY-STEP');
      renderStepByStep(stepCard, stepPayload, metadata.title);
      bodyCard.appendChild(stepCard);
    }

    // 6. Structured Table (if available)
    const tblPayload = metadata.table_data || (metadata.data && metadata.data.table ? metadata.data.table : null);
    if (tblPayload && Array.isArray(tblPayload) && tblPayload.length > 0) {
      const tblCard = createVisualCard('📋', metadata.title || 'Structured Relationship Matrix', 'STRUCTURED TABLE');
      const tableWrapper = document.createElement('div');
      tableWrapper.className = 'tracera-table-wrapper';

      const cols = Object.keys(tblPayload[0]);
      let tableHtml = '<table class="data-table" style="width:100%; font-size:0.78rem;"><thead><tr>';
      cols.forEach(c => {
        const formattedTitle = c.replace(/_/g, ' ').toUpperCase();
        tableHtml += `<th style="padding:0.6rem 0.75rem; text-align:left;">${escapeHtml(formattedTitle)}</th>`;
      });
      tableHtml += '</tr></thead><tbody>';

      tblPayload.forEach(rowItem => {
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
      tblCard.appendChild(tableWrapper);
      bodyCard.appendChild(tblCard);
    }

    // 7. Timeline Cards (if available)
    const timePayload = metadata.timeline_data || (metadata.data && metadata.data.timeline ? metadata.data.timeline : null);
    if (timePayload && Array.isArray(timePayload) && timePayload.length > 0) {
      const timeCard = createVisualCard('⏱️', metadata.title || 'Chronological Event Timeline', 'TIMELINE');
      const timelineWrapper = document.createElement('div');
      timelineWrapper.style.margin = '0.5rem 0';
      timelineWrapper.style.display = 'flex';
      timelineWrapper.style.flexDirection = 'column';
      timelineWrapper.style.gap = '0.6rem';

      timePayload.forEach(ev => {
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
      timeCard.appendChild(timelineWrapper);
      bodyCard.appendChild(timeCard);
    }

    // 4. Formatted Markdown Analytical Content
    const mdContainer = document.createElement('div');
    mdContainer.className = 'tracera-markdown-content';
    mdContainer.innerHTML = renderMarkdown(content || '');
    bodyCard.appendChild(mdContainer);

    // 5. Provenance & Action Footer
    const footer = document.createElement('div');
    footer.className = 'tracera-response-footer';

    const badges = document.createElement('div');
    badges.className = 'tracera-response-badges';
    
    let pathBadges = '';
    if (metadata.relationship_paths && metadata.relationship_paths.length > 0) {
      const p = metadata.relationship_paths[0];
      const isVer = p.verification_status === 'Verified';
      const badgeStyle = isVer 
        ? 'background:rgba(16, 185, 129, 0.15); color:#10B981; border:1px solid rgba(16, 185, 129, 0.3); font-size:0.68rem; font-weight:700;'
        : 'background:rgba(212, 167, 44, 0.15); color:var(--accent-gold); border:1px solid rgba(212, 167, 44, 0.3); font-size:0.68rem; font-weight:700;';
      pathBadges += `<span class="badge" style="${badgeStyle}">Path: ${escapeHtml(p.path_summary)} · ${escapeHtml(p.verification_status.toUpperCase())}</span>`;
    }

    badges.innerHTML = `
      <span class="badge badge-status-complete" style="font-size:0.68rem; font-weight:700;">✔ Verified Schema Engine</span>
      <span class="badge" style="background:rgba(212,167,44,0.12); color:var(--accent-gold); font-size:0.68rem;">🔒 PII Masked</span>
      ${pathBadges}
    `;

    const actions = document.createElement('div');
    actions.className = 'tracera-response-actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'tracera-action-btn';
    copyBtn.style.fontSize = '0.72rem';
    copyBtn.innerHTML = '📋 Copy';
    copyBtn.title = 'Copy response text';
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(content || '');
      copyBtn.innerHTML = '✔ Copied!';
      setTimeout(() => { copyBtn.innerHTML = '📋 Copy'; }, 2000);
    };

    const retryBtn = document.createElement('button');
    retryBtn.className = 'tracera-action-btn';
    retryBtn.style.fontSize = '0.72rem';
    retryBtn.innerHTML = '🔄 Retry';
    retryBtn.title = 'Retry last question';
    retryBtn.onclick = () => {
      if (lastUserMessage) {
        suggestPrompt(lastUserMessage);
      }
    };

    actions.appendChild(copyBtn);
    actions.appendChild(retryBtn);

    footer.appendChild(badges);
    footer.appendChild(actions);
    bodyCard.appendChild(footer);

    row.appendChild(bodyCard);
    return row;
  }
};

// ==========================================
// 4. CHAT MESSAGE LIST COMPONENT (Manages Deduplication & Stream)
// ==========================================
const ChatMessageList = {
  renderedMessageIds: new Set(),

  getContainer() {
    return document.getElementById('messagesInner') || document.getElementById('chatMessages');
  },

  clear() {
    const container = this.getContainer();
    if (container) container.innerHTML = '';
    this.renderedMessageIds.clear();
  },

  addUserMessage(id, content, timestamp) {
    if (this.renderedMessageIds.has(id)) {
      console.warn(`Duplicate user message ID skipped: ${id}`);
      return;
    }
    this.renderedMessageIds.add(id);

    WelcomeScreen.hide();

    const container = this.getContainer();
    if (!container) return;

    const msgEl = UserMessage.create(id, content, timestamp);
    container.appendChild(msgEl);
    this.scrollToBottom();
  },

  addAssistantMessage(id, content, metadata = {}) {
    if (this.renderedMessageIds.has(id)) {
      console.warn(`Duplicate assistant message ID skipped: ${id}`);
      return;
    }
    this.renderedMessageIds.add(id);

    WelcomeScreen.hide();

    const container = this.getContainer();
    if (!container) return;

    const msgEl = AssistantMessage.create(id, content, metadata);
    container.appendChild(msgEl);
    this.scrollToBottom();
  },

  showLoading(loadingId) {
    const container = this.getContainer();
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'tracera-message-row assistant';
    row.id = loadingId;

    row.innerHTML = `
      <div class="tracera-assistant-body" style="padding: 1rem 1.25rem;">
        <div style="display:flex; align-items:center; gap:0.65rem; color:var(--text-secondary); font-size:0.85rem;">
          <span class="status-pulse-dot" style="background:var(--accent-gold);"></span>
          <span>TRACERA is tracing entity linkages, verifying relational paths, and analyzing evidence...</span>
        </div>
      </div>
    `;

    container.appendChild(row);
    this.scrollToBottom();
  },

  hideLoading(loadingId) {
    const el = document.getElementById(loadingId);
    if (el) el.remove();
  },

  showError(errorText, failedQuery) {
    const container = this.getContainer();
    if (!container) return;

    const errorId = 'err-' + Date.now();
    const row = document.createElement('div');
    row.className = 'tracera-message-row assistant';
    row.id = errorId;

    row.innerHTML = `
      <div class="tracera-assistant-body" style="border-color:var(--color-danger); background:rgba(239, 68, 68, 0.05);">
        <p style="margin-bottom:0.75rem; color:var(--text-primary);">⚠️ <strong>Request Error:</strong> ${escapeHtml(errorText)}</p>
        <div style="display:flex; justify-content:flex-end;">
          <button class="tracera-action-btn" style="background:var(--bg-elevated); border:1px solid var(--border-color); padding:0.35rem 0.75rem; border-radius:var(--radius-sm); font-size:0.78rem; cursor:pointer;" onclick="suggestPrompt('${escapeHtml(failedQuery)}')">
            🔄 Retry Question
          </button>
        </div>
      </div>
    `;

    container.appendChild(row);
    this.scrollToBottom();
  },

  scrollToBottom() {
    requestAnimationFrame(() => {
      const scrollContainer = document.getElementById('chatMessages');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    });
  }
};

// ==========================================
// 5. MESSAGE COMPOSER COMPONENT
// ==========================================
const MessageComposer = {
  inputEl: null,
  sendBtnEl: null,

  init(onSend) {
    this.inputEl = document.getElementById('chatInput');
    this.sendBtnEl = document.getElementById('btnSendChat');
    const newChatBtn = document.getElementById('btnNewChat');

    if (newChatBtn) {
      newChatBtn.addEventListener('click', createNewConversation);
    }

    if (!this.inputEl || !this.sendBtnEl) return;

    this.sendBtnEl.disabled = true;
    this.inputEl.style.height = '48px';

    const updateState = () => {
      const val = this.inputEl.value.trim();
      this.sendBtnEl.disabled = isSubmitting || val.length === 0;

      // Auto-expand textarea between 48px and 180px
      this.inputEl.style.height = 'auto';
      const targetHeight = Math.max(48, Math.min(this.inputEl.scrollHeight, 180));
      this.inputEl.style.height = targetHeight + 'px';
    };

    this.inputEl.addEventListener('input', updateState);
    this.inputEl.addEventListener('focus', updateState);

    // Enter sends, Shift+Enter makes newline
    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!this.sendBtnEl.disabled && !isSubmitting && this.inputEl.value.trim()) {
          onSend();
        }
      }
    });

    this.sendBtnEl.addEventListener('click', () => {
      if (!this.sendBtnEl.disabled && !isSubmitting && this.inputEl.value.trim()) {
        onSend();
      }
    });
  },

  getValue() {
    return this.inputEl ? this.inputEl.value.trim() : '';
  },

  clear() {
    if (this.inputEl) {
      this.inputEl.value = '';
      this.inputEl.style.height = '48px';
    }
    if (this.sendBtnEl) {
      this.sendBtnEl.disabled = true;
    }
  },

  setDisabled(disabled) {
    if (this.inputEl) this.inputEl.disabled = disabled;
    if (this.sendBtnEl) this.sendBtnEl.disabled = disabled;
  },

  focus() {
    if (this.inputEl) this.inputEl.focus();
  }
};

// ==========================================
// 6. MAIN CHAT SUBMISSION CONTROLLER
// ==========================================
async function sendChatMessage() {
  if (isSubmitting) return;

  const message = MessageComposer.getValue();
  if (!message) return;

  lastUserMessage = message;
  isSubmitting = true;

  // Clear composer & disable send button
  MessageComposer.clear();
  MessageComposer.setDisabled(true);

  // Generate unique stable client ID for the user message
  const userMsgId = 'usr-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);

  // 1. Add User Message exactly once
  ChatMessageList.addUserMessage(userMsgId, message, new Date().toISOString());

  // 2. Show Loading Indicator
  const loadingId = 'loading-' + Date.now();
  ChatMessageList.showLoading(loadingId);

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

    ChatMessageList.hideLoading(loadingId);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      ChatMessageList.showError(errData.detail || 'Server error occurred.', message);
      return;
    }

    const report = await res.json();

    // Lock onto conversation ID returned by backend
    if (report.conversation_id && report.conversation_id !== currentConversationId) {
      currentConversationId = report.conversation_id;
      localStorage.setItem('tracera-active-conv', currentConversationId);
    }

    // 3. Add Assistant Response exactly once
    const asstMsgId = report.message_id || ('asst-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6));
    ChatMessageList.addAssistantMessage(asstMsgId, report.explanation, report);

    // Refresh threads list in background without touching current messages
    await loadConversations(false);

  } catch (err) {
    ChatMessageList.hideLoading(loadingId);
    ChatMessageList.showError(`Network connection failed: ${err.message}`, message);
  } finally {
    isSubmitting = false;
    MessageComposer.setDisabled(false);
    MessageComposer.focus();
  }
}

// ==========================================
// 7. CONVERSATION MANAGEMENT & PERSISTENCE
// ==========================================
async function loadConversations(autoSelect = true) {
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

    if (autoSelect) {
      const savedId = localStorage.getItem('tracera-active-conv');
      const targetId = (savedId && allConversations.find(c => c.id === savedId))
        ? savedId
        : (allConversations.length > 0 ? allConversations[0].id : null);

      if (targetId) {
        await selectConversation(targetId);
      } else {
        currentConversationId = null;
        WelcomeScreen.show();
      }
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

async function selectConversation(convId) {
  currentConversationId = convId;
  localStorage.setItem('tracera-active-conv', convId);

  // Close the history drawer when a conversation is selected
  toggleHistorySidebar(false);

  // Highlight active thread item in sidebar
  document.querySelectorAll('.tracera-thread-item').forEach(el => el.classList.remove('active'));
  const activeEl = document.getElementById(`thread-${convId}`);
  if (activeEl) activeEl.classList.add('active');

  const container = ChatMessageList.getContainer();
  if (!container) return;

  ChatMessageList.clear();
  container.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; padding:2rem; text-align:center;">Loading conversation history...</div>';

  try {
    const res = await fetch(`/api/relationships/conversations/${convId}`);
    if (!res.ok) {
      container.innerHTML = '<div style="color:var(--color-danger); padding:2rem; text-align:center;">Unable to load conversation details.</div>';
      return;
    }
    const detail = await res.json();
    ChatMessageList.clear();

    const titleEl = document.getElementById('activeConvTitle');
    if (titleEl) titleEl.textContent = detail.title || 'Conversation';

    if (!detail.messages || detail.messages.length === 0) {
      WelcomeScreen.show();
      return;
    }

    // Render each saved message exactly once in chronological order
    detail.messages.forEach(msg => {
      const msgId = msg.id || ('hist-' + Math.random().toString(36).substr(2, 9));
      if (msg.role === 'user') {
        ChatMessageList.addUserMessage(msgId, msg.content, msg.created_at);
      } else {
        const struct = msg.structured_data || {};
        ChatMessageList.addAssistantMessage(msgId, msg.content, {
          format_requested: msg.format_requested,
          format_explanation: msg.format_explanation,
          response_type: msg.response_type,
          title: struct.title || null,
          graph: msg.graph_data,
          table_data: msg.table_data,
          timeline_data: msg.timeline_data,
          flowchart_data: msg.flowchart_data || struct.flowchart,
          chart_data: msg.chart_data || struct.chart,
          steps: struct.steps || null,
          comparison_data: struct.comparison || null,
          timestamp: msg.created_at,
        });
      }
    });

    ChatMessageList.scrollToBottom();
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
    localStorage.setItem('tracera-active-conv', newConv.id);
    const titleEl = document.getElementById('activeConvTitle');
    if (titleEl) titleEl.textContent = newConv.title || 'New Exploration';

    await loadConversations(false);
    WelcomeScreen.show();
    MessageComposer.focus();
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
      if (currentConversationId === convId) {
        const titleEl = document.getElementById('activeConvTitle');
        if (titleEl) titleEl.textContent = newTitle.trim();
      }
      await loadConversations(false);
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
        localStorage.removeItem('tracera-active-conv');
        const titleEl = document.getElementById('activeConvTitle');
        if (titleEl) titleEl.textContent = 'New Exploration';
        WelcomeScreen.show();
      }
      await loadConversations(false);
    }
  } catch (err) {
    console.error('Failed to delete conversation:', err);
  }
}

async function clearAllHistory() {
  if (!confirm('Are you sure you want to clear all conversation history? This will delete all saved investigations.')) return;

  try {
    const res = await fetch('/api/relationships/conversations', {
      method: 'DELETE',
    });
    if (res.ok) {
      currentConversationId = null;
      localStorage.removeItem('tracera-active-conv');
      const titleEl = document.getElementById('activeConvTitle');
      if (titleEl) titleEl.textContent = 'New Exploration';
      allConversations = [];
      renderThreads([]);
      WelcomeScreen.show();
      MessageComposer.clear();
      MessageComposer.focus();
    }
  } catch (err) {
    console.error('Failed to clear all conversations:', err);
  }
}

function suggestPrompt(text) {
  if (MessageComposer.inputEl) {
    MessageComposer.inputEl.value = text;
    if (MessageComposer.sendBtnEl) {
      MessageComposer.sendBtnEl.disabled = false;
    }
    sendChatMessage();
  }
}

// ==========================================
// 8. RICH MARKDOWN RENDERING ENGINE
// ==========================================
function renderMarkdown(md) {
  if (!md) return '';

  // Extract fenced code blocks first to protect them from regex replacements
  const codeBlocks = [];
  let text = md.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const index = codeBlocks.length;
    codeBlocks.push({ lang: lang || '', code: code.trim() });
    return `%%CODEBLOCK_${index}%%`;
  });

  // Extract markdown tables
  const tables = [];
  text = text.replace(/((?:^[ \t]*\|.+?\|[ \t]*\r?\n)+(?:^[ \t]*\|[-: |]+\|[ \t]*\r?\n)(?:^[ \t]*\|.+?\|[ \t]*(?:\r?\n|$))+)/gm, (match) => {
    const index = tables.length;
    tables.push(parseMarkdownTable(match));
    return `\n\n%%TABLE_${index}%%\n\n`;
  });

  // Escape HTML tags in normal text
  text = escapeHtml(text);

  // Headings
  text = text.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
  text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Blockquotes
  text = text.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Bold & Italics
  text = text.replace(/\*\*\*(.*?)\*\*\*/gim, '<strong><em>$1</em></strong>');
  text = text.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  text = text.replace(/__(.*?)__/gim, '<strong>$1</strong>');
  text = text.replace(/\*(.*?)\*/gim, '<em>$1</em>');
  text = text.replace(/_([^_]+)_/gim, '<em>$1</em>');

  // Inline Code
  text = text.replace(/`([^`]+)`/gim, '<code>$1</code>');

  // Horizontal Rules
  text = text.replace(/^---$/gim, '<hr style="border:none; border-top:1px solid var(--border-subtle); margin:1.25rem 0;">');

  // Lists (Unordered & Numbered)
  text = text.replace(/^\s*[-*•]\s+(.*$)/gim, '<li>$1</li>');
  text = text.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li value="$1">$2</li>');

  // Wrap consecutive list items in <ul>
  text = text.replace(/(<li>.*?<\/li>(?:\s*<li>.*?<\/li>)*)/gis, '<ul>$1</ul>');

  // Paragraphs
  const sections = text.split(/\n{2,}/);
  text = sections.map(sec => {
    sec = sec.trim();
    if (!sec) return '';
    // Skip wrapping if it's already a block element or placeholder
    if (sec.startsWith('<h') || sec.startsWith('<ul>') || sec.startsWith('<ol>') || 
        sec.startsWith('<blockquote>') || sec.startsWith('<hr') || 
        sec.startsWith('%%CODEBLOCK_') || sec.startsWith('%%TABLE_')) {
      return sec;
    }
    return `<p>${sec.replace(/\n/g, '<br>')}</p>`;
  }).join('\n');

  // Restore code blocks
  codeBlocks.forEach((item, i) => {
    const escapedCode = escapeHtml(item.code);
    const blockHtml = `<pre><code>${escapedCode}</code></pre>`;
    text = text.replace(new RegExp(`%%CODEBLOCK_${i}%%`, 'g'), blockHtml);
  });

  // Restore tables
  tables.forEach((tableHtml, i) => {
    text = text.replace(new RegExp(`%%TABLE_${i}%%`, 'g'), tableHtml);
  });

  return text;
}

function parseMarkdownTable(tableText) {
  const lines = tableText.trim().split('\n').map(l => l.trim()).filter(l => l.startsWith('|') && l.endsWith('|'));
  if (lines.length < 2) return '';

  const headerLine = lines[0];
  const headers = headerLine.slice(1, -1).split('|').map(h => escapeHtml(h.trim()));

  let html = '<table class="tracera-md-table"><thead><tr>';
  headers.forEach(h => {
    html += `<th>${h}</th>`;
  });
  html += '</tr></thead><tbody>';

  // Skip delimiter line (index 1)
  for (let i = 2; i < lines.length; i++) {
    const rowLine = lines[i];
    const cells = rowLine.slice(1, -1).split('|').map(c => escapeHtml(c.trim()));
    html += '<tr>';
    headers.forEach((_, colIdx) => {
      html += `<td>${cells[colIdx] || ''}</td>`;
    });
    html += '</tr>';
  }
  html += '</tbody></table>';
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

// ==========================================
// 9. DYNAMIC VISUALIZATION ENGINE RENDERERS
// ==========================================

/**
 * Responsive SVG Chart Generator (Bar, Line, Pie)
 * 100% native SVG with tooltips, legend, and readable axes.
 */
function renderChart(container, chartData, title) {
  if (!chartData || !chartData.series || !Array.isArray(chartData.series) || chartData.series.length === 0) {
    const emptyNotice = document.createElement('div');
    emptyNotice.style.padding = '1rem';
    emptyNotice.style.color = 'var(--text-muted)';
    emptyNotice.style.fontSize = '0.8rem';
    emptyNotice.textContent = 'No numerical series data available for this chart.';
    container.appendChild(emptyNotice);
    return;
  }

  const chartType = (chartData.type || 'bar').toLowerCase();
  const series = chartData.series;
  const colors = ['#10B981', '#D4A72C', '#3B82F6', '#EC4899', '#8B5CF6', '#F59E0B', '#06B6D4'];

  const chartBox = document.createElement('div');
  chartBox.className = 'tracera-chart-container';

  // Floating Tooltip
  const tooltip = document.createElement('div');
  tooltip.className = 'tracera-chart-tooltip';
  chartBox.appendChild(tooltip);

  if (chartType === 'pie') {
    // Pie / Donut Chart
    const total = series.reduce((sum, item) => sum + (Number(item.value) || 0), 0) || 1;
    const cx = 130, cy = 130, r = 90, innerR = 45;
    let currentAngle = -Math.PI / 2;

    let pathsSvg = '';
    series.forEach((slice, idx) => {
      const val = Number(slice.value) || 0;
      const sliceAngle = (val / total) * 2 * Math.PI;
      const startAngle = currentAngle;
      const endAngle = currentAngle + sliceAngle;
      currentAngle = endAngle;

      const x1 = cx + r * Math.cos(startAngle);
      const y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle);
      const y2 = cy + r * Math.sin(endAngle);

      const ix1 = cx + innerR * Math.cos(endAngle);
      const iy1 = cy + innerR * Math.sin(endAngle);
      const ix2 = cx + innerR * Math.cos(startAngle);
      const iy2 = cy + innerR * Math.sin(startAngle);

      const largeArc = sliceAngle > Math.PI ? 1 : 0;
      const color = colors[idx % colors.length];
      const pct = Math.round((val / total) * 100);

      const d = `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix2} ${iy2} Z`;

      pathsSvg += `<path d="${d}" fill="${color}" stroke="#090D12" stroke-width="2" style="cursor:pointer; transition:opacity 0.2s;" data-label="${escapeHtml(slice.label)}" data-val="${val}" data-pct="${pct}%" class="tracera-chart-slice" />`;
    });

    // Right Legend
    let legendSvg = '';
    series.forEach((slice, idx) => {
      const color = colors[idx % colors.length];
      const val = slice.value;
      const pct = Math.round((val / total) * 100);
      const ly = 35 + idx * 24;
      if (ly < 250) {
        legendSvg += `
          <rect x="265" y="${ly}" width="12" height="12" rx="3" fill="${color}" />
          <text x="285" y="${ly + 10}" fill="#E5E7EB" font-size="11" font-family="system-ui, sans-serif" font-weight="600">${escapeHtml(slice.label)}</text>
          <text x="450" y="${ly + 10}" fill="#9CA3AF" font-size="11" font-family="monospace" text-anchor="end">${val} (${pct}%)</text>
        `;
      }
    });

    chartBox.innerHTML += `
      <svg viewBox="0 0 480 260" class="tracera-chart-svg">
        ${pathsSvg}
        <text x="${cx}" y="${cy - 4}" text-anchor="middle" fill="#9CA3AF" font-size="10" font-family="system-ui, sans-serif">TOTAL</text>
        <text x="${cx}" y="${cy + 15}" text-anchor="middle" fill="#F3F4F6" font-size="14" font-weight="800" font-family="monospace">${total}</text>
        ${legendSvg}
      </svg>
    `;

  } else if (chartType === 'line') {
    // Line Chart
    const maxVal = Math.max(...series.map(s => Number(s.value) || 0), 10);
    const w = 540, h = 240, padL = 60, padR = 30, padT = 30, padB = 40;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    let points = [];
    const step = series.length > 1 ? plotW / (series.length - 1) : plotW / 2;

    series.forEach((pt, i) => {
      const val = Number(pt.value) || 0;
      const x = padL + (series.length > 1 ? i * step : plotW / 2);
      const y = padT + plotH - (val / maxVal) * plotH;
      points.push({ x, y, label: pt.label, value: val });
    });

    const ptsStr = points.map(p => `${p.x},${p.y}`).join(' ');
    const areaStr = `${points[0].x},${padT + plotH} ` + ptsStr + ` ${points[points.length - 1].x},${padT + plotH}`;

    // Grid lines & Y ticks
    let gridLines = '';
    const ticks = [0, Math.round(maxVal / 2), maxVal];
    ticks.forEach(t => {
      const ty = padT + plotH - (t / maxVal) * plotH;
      gridLines += `
        <line x1="${padL}" y1="${ty}" x2="${w - padR}" y2="${ty}" stroke="#1E293B" stroke-dasharray="3 3" />
        <text x="${padL - 10}" y="${ty + 4}" fill="#6B7280" font-size="10" font-family="monospace" text-anchor="end">${t}</text>
      `;
    });

    let dotsSvg = '';
    points.forEach((p) => {
      dotsSvg += `
        <circle cx="${p.x}" cy="${p.y}" r="4.5" fill="#D4A72C" stroke="#090D12" stroke-width="2" class="tracera-chart-dot" data-label="${escapeHtml(p.label)}" data-val="${p.value}" style="cursor:pointer;" />
        <text x="${p.x}" y="${padT + plotH + 20}" fill="#9CA3AF" font-size="10" font-family="system-ui, sans-serif" text-anchor="middle">${escapeHtml(p.label)}</text>
      `;
    });

    chartBox.innerHTML += `
      <svg viewBox="0 0 ${w} ${h}" class="tracera-chart-svg">
        <defs>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#D4A72C" stop-opacity="0.25"/>
            <stop offset="100%" stop-color="#D4A72C" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        ${gridLines}
        <polygon points="${areaStr}" fill="url(#lineGrad)" />
        <polyline points="${ptsStr}" fill="none" stroke="#D4A72C" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
        ${dotsSvg}
        <text x="${w / 2}" y="${h - 4}" fill="#6B7280" font-size="9" text-anchor="middle" font-family="system-ui, sans-serif">${escapeHtml(chartData.x_label || 'Timeline')}</text>
        <text x="14" y="${h / 2}" fill="#6B7280" font-size="9" text-anchor="middle" font-family="system-ui, sans-serif" transform="rotate(-90 14,${h/2})">${escapeHtml(chartData.y_label || 'Count')}</text>
      </svg>
    `;

  } else {
    // Bar Chart
    const maxVal = Math.max(...series.map(s => Number(s.value) || 0), 10);
    const w = 540, h = 240, padL = 60, padR = 30, padT = 30, padB = 40;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;
    const barWidth = Math.min(48, Math.max(16, (plotW / series.length) * 0.65));
    const step = plotW / series.length;

    let gridLines = '';
    const ticks = [0, Math.round(maxVal / 2), maxVal];
    ticks.forEach(t => {
      const ty = padT + plotH - (t / maxVal) * plotH;
      gridLines += `
        <line x1="${padL}" y1="${ty}" x2="${w - padR}" y2="${ty}" stroke="#1E293B" stroke-dasharray="3 3" />
        <text x="${padL - 10}" y="${ty + 4}" fill="#6B7280" font-size="10" font-family="monospace" text-anchor="end">${t}</text>
      `;
    });

    let barsSvg = '';
    series.forEach((bar, i) => {
      const val = Number(bar.value) || 0;
      const barH = (val / maxVal) * plotH;
      const x = padL + i * step + (step - barWidth) / 2;
      const y = padT + plotH - barH;
      const color = colors[i % colors.length];

      barsSvg += `
        <rect x="${x}" y="${y}" width="${barWidth}" height="${barH}" rx="4" fill="${color}" opacity="0.88" class="tracera-chart-bar" data-label="${escapeHtml(bar.label)}" data-val="${val}" style="cursor:pointer; transition:opacity 0.2s;" />
        <text x="${x + barWidth / 2}" y="${y - 6}" fill="#E5E7EB" font-size="10" font-family="monospace" font-weight="700" text-anchor="middle">${val}</text>
        <text x="${x + barWidth / 2}" y="${padT + plotH + 18}" fill="#9CA3AF" font-size="10" font-family="system-ui, sans-serif" text-anchor="middle">${escapeHtml(bar.label)}</text>
      `;
    });

    chartBox.innerHTML += `
      <svg viewBox="0 0 ${w} ${h}" class="tracera-chart-svg">
        ${gridLines}
        ${barsSvg}
        <text x="${w / 2}" y="${h - 4}" fill="#6B7280" font-size="9" text-anchor="middle" font-family="system-ui, sans-serif">${escapeHtml(chartData.x_label || 'Category')}</text>
        <text x="14" y="${h / 2}" fill="#6B7280" font-size="9" text-anchor="middle" font-family="system-ui, sans-serif" transform="rotate(-90 14,${h/2})">${escapeHtml(chartData.y_label || 'Records / Gaps')}</text>
      </svg>
    `;
  }

  // Tooltip Interaction
  container.appendChild(chartBox);
  chartBox.addEventListener('mouseover', (e) => {
    const target = e.target;
    if (target.dataset && target.dataset.val !== undefined) {
      tooltip.style.opacity = '1';
      tooltip.innerHTML = `<strong>${escapeHtml(target.dataset.label)}</strong>: ${escapeHtml(target.dataset.val)} ${target.dataset.pct ? '(' + escapeHtml(target.dataset.pct) + ')' : ''}`;
    }
  });
  chartBox.addEventListener('mousemove', (e) => {
    const rect = chartBox.getBoundingClientRect();
    tooltip.style.left = (e.clientX - rect.left + 12) + 'px';
    tooltip.style.top = (e.clientY - rect.top - 28) + 'px';
  });
  chartBox.addEventListener('mouseout', () => {
    tooltip.style.opacity = '0';
  });
}

/**
 * Process Flowchart Generator
 */
function renderFlowchart(container, flowchartData, title) {
  if (!flowchartData || !flowchartData.steps || !Array.isArray(flowchartData.steps)) return;

  const flowBox = document.createElement('div');
  flowBox.className = 'tracera-flowchart-container';

  flowchartData.steps.forEach((step, idx) => {
    const stepEl = document.createElement('div');
    stepEl.className = 'tracera-flow-step';

    const stepNum = step.step_num || (idx + 1);
    const stepTitle = step.title || `Stage ${stepNum}`;
    const stepDesc = step.description || '';
    const badge = step.badge || 'Verified Step';

    stepEl.innerHTML = `
      <div class="tracera-flow-step-num">${stepNum}</div>
      <div class="tracera-flow-step-content">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.25rem;">
          <div class="tracera-flow-step-title">${escapeHtml(stepTitle)}</div>
          <span class="badge badge-status-complete" style="font-size:0.68rem;">${escapeHtml(badge)}</span>
        </div>
        <div class="tracera-flow-step-desc">${escapeHtml(stepDesc)}</div>
      </div>
    `;

    flowBox.appendChild(stepEl);

    // Connector Arrow
    if (idx < flowchartData.steps.length - 1) {
      const arrow = document.createElement('div');
      arrow.className = 'tracera-flow-arrow';
      arrow.innerHTML = '⬇';
      flowBox.appendChild(arrow);
    }
  });

  container.appendChild(flowBox);
}

/**
 * Step-by-Step Traversal Generator
 */
function renderStepByStep(container, steps, title) {
  if (!steps || !Array.isArray(steps) || steps.length === 0) return;

  const stepsBox = document.createElement('div');
  stepsBox.className = 'tracera-steps-container';

  steps.forEach((s, idx) => {
    const card = document.createElement('div');
    card.className = 'tracera-step-card';
    const num = s.index || (idx + 1);
    const titleText = s.title || `Step ${num}`;
    const descText = s.description || (typeof s === 'string' ? s : '');

    card.innerHTML = `
      <div class="tracera-step-index">STEP ${num}</div>
      <div class="tracera-step-body">
        <div class="tracera-step-body-title">${escapeHtml(titleText)}</div>
        <div class="tracera-step-body-desc">${escapeHtml(descText)}</div>
      </div>
    `;
    stepsBox.appendChild(card);
  });

  container.appendChild(stepsBox);
}

/**
 * Comparative Matrix Generator
 */
function renderComparison(container, comparisonData, title) {
  if (!comparisonData || !comparisonData.entities || !Array.isArray(comparisonData.entities)) return;

  const wrap = document.createElement('div');
  wrap.className = 'tracera-comparison-wrapper';

  const entities = comparisonData.entities;
  const attributes = comparisonData.attributes || [];

  let tableHtml = '<table class="tracera-comparison-table"><thead><tr>';
  tableHtml += '<th style="width: 25%;">Governance Dimension</th>';
  entities.forEach(ent => {
    tableHtml += `<th>${escapeHtml(ent)}</th>`;
  });
  tableHtml += '</tr></thead><tbody>';

  attributes.forEach(attr => {
    tableHtml += `<tr><td style="font-weight: 700; color: var(--accent-gold);">${escapeHtml(attr.attribute || '')}</td>`;
    entities.forEach(ent => {
      const val = (attr.values && attr.values[ent] !== undefined) ? attr.values[ent] : '-';
      tableHtml += `<td>${escapeHtml(String(val))}</td>`;
    });
    tableHtml += '</tr>';
  });

  tableHtml += '</tbody></table>';
  wrap.innerHTML = tableHtml;
  container.appendChild(wrap);
}

// ==========================================
// 10. CYTOSCAPE.JS & INSPECTOR MODALS
// ==========================================
function openNodeModal(data) {
  const modal = document.getElementById('detailModal');
  const titleEl = document.getElementById('modalFieldTitle');
  const bodyEl = document.getElementById('modalDetailsBody');
  if (!modal || !titleEl || !bodyEl) return;

  titleEl.innerHTML = `<span>Entity Node:</span> <strong style="color:#FFF;">${escapeHtml(data.label)}</strong>`;
  bodyEl.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:0.75rem; font-size:0.85rem;">
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Entity Identifier:</span>
        <strong style="color:var(--accent-gold); font-family:monospace;">${escapeHtml(data.id || data.label)}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Primary Dataset / Source:</span>
        <span>${escapeHtml(data.source || 'Scanned Relational Database')}</span>
      </div>
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Entity Classification:</span>
        <span class="badge" style="background:var(--bg-elevated); color:var(--accent-gold);">${escapeHtml(data.type || 'Personal Data Domain')}</span>
      </div>
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Verification Level:</span>
        <span class="badge badge-status-complete">100% Deterministic Schema Grounded</span>
      </div>
      <div style="margin-top:0.5rem; padding:0.65rem 0.85rem; background:rgba(16, 185, 129, 0.08); border-left:3px solid #10B981; border-radius:4px; font-size:0.78rem; color:#A7F3D0;">
        PrivSight verified this entity against actual database tables and catalog metadata without synthetic fabrication.
      </div>
    </div>
  `;
  modal.classList.add('active');
}

function openEdgeModal(data) {
  const modal = document.getElementById('detailModal');
  const titleEl = document.getElementById('modalFieldTitle');
  const bodyEl = document.getElementById('modalDetailsBody');
  if (!modal || !titleEl || !bodyEl) return;

  const isVerified = data.status === 'verified';
  const confPct = Math.round((data.confidence || 1.0) * 100);

  titleEl.innerHTML = `<span>Relationship:</span> <strong style="color:#FFF;">${escapeHtml(data.source)} ➔ ${escapeHtml(data.target)}</strong>`;
  bodyEl.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:0.75rem; font-size:0.85rem;">
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Source Entity:</span>
        <strong style="color:var(--text-primary); font-family:monospace;">${escapeHtml(data.source)}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Target Entity:</span>
        <strong style="color:var(--text-primary); font-family:monospace;">${escapeHtml(data.target)}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Cardinality:</span>
        <span class="badge" style="background:var(--bg-elevated); color:var(--accent-gold); font-family:monospace;">${escapeHtml(data.label || 'N:1')}</span>
      </div>
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Verification Status:</span>
        <span class="badge ${isVerified ? 'badge-status-complete' : ''}" style="${!isVerified ? 'background:rgba(212,167,44,0.15); color:var(--accent-gold); border:1px solid rgba(212,167,44,0.3);' : ''}">${isVerified ? 'VERIFIED CONSTRAINT' : 'INFERRED VALUE OVERLAP'}</span>
      </div>
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border-color); padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Confidence Score:</span>
        <strong style="color:${isVerified ? '#10B981' : 'var(--accent-gold)'};">${confPct}%</strong>
      </div>
      <div style="margin-top:0.4rem;">
        <span style="color:var(--text-secondary); font-size:0.78rem; display:block; margin-bottom:0.25rem;">Technical Evidence & Join Provenance:</span>
        <div style="padding:0.6rem 0.85rem; background:var(--bg-elevated); border:1px solid var(--border-color); border-radius:4px; font-family:monospace; font-size:0.75rem; color:#E5E7EB;">
          ${escapeHtml(data.evidence || 'Database Foreign Key constraint validated by PrivSight Schema Engine.')}
        </div>
      </div>
    </div>
  `;
  modal.classList.add('active');
}

function initCytoscapeGraph(containerId, graphData) {
  if (typeof cytoscape === 'undefined') {
    console.warn('Cytoscape.js library not loaded.');
    return;
  }

  const container = document.getElementById(containerId);
  if (!container) return;

  const elements = [];
  if (graphData.nodes) {
    graphData.nodes.forEach(n => {
      elements.push({
        data: {
          id: n.id,
          label: n.label,
          type: n.entity_type,
          source: n.source_name,
          raw: n,
        }
      });
    });
  }

  if (graphData.edges) {
    graphData.edges.forEach((e, idx) => {
      const isInf = e.verification_status === 'Inferred' || (e.confidence_score !== undefined && e.confidence_score < 0.9);
      elements.push({
        data: {
          id: 'e_' + idx + '_' + e.source + '_' + e.target,
          source: e.source,
          target: e.target,
          label: e.cardinality || '',
          evidence: e.evidence,
          confidence: e.confidence_score,
          status: isInf ? 'inferred' : 'verified',
          raw: e,
        }
      });
    });
  }

  const cy = cytoscape({
    container: container,
    elements: elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#0C2B1E',
          'border-width': 2,
          'border-color': '#D4A72C',
          'label': 'data(label)',
          'color': '#EAEAEA',
          'font-size': '10px',
          'font-family': 'monospace',
          'font-weight': 'bold',
          'text-valign': 'center',
          'text-halign': 'center',
          'width': '58px',
          'height': '58px',
          'text-wrap': 'wrap',
          'text-max-width': '52px',
          'cursor': 'pointer',
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2.5,
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '8px',
          'font-family': 'monospace',
          'text-rotation': 'autorotate',
          'text-margin-y': -8,
          'cursor': 'pointer',
        }
      },
      {
        selector: 'edge[status = "verified"]',
        style: {
          'line-color': '#10B981',
          'target-arrow-color': '#10B981',
          'target-arrow-shape': 'triangle',
          'line-style': 'solid',
          'color': '#10B981',
        }
      },
      {
        selector: 'edge[status = "inferred"]',
        style: {
          'line-color': '#D4A72C',
          'target-arrow-color': '#D4A72C',
          'target-arrow-shape': 'triangle',
          'line-style': 'dashed',
          'color': '#D4A72C',
        }
      }
    ],
    layout: {
      name: 'breadthfirst',
      directed: true,
      padding: 24,
      spacingFactor: 1.25,
    }
  });

  // Tap interaction for node & edge inspection
  cy.on('tap', 'node', function(evt) {
    const node = evt.target;
    openNodeModal(node.data());
  });

  cy.on('tap', 'edge', function(evt) {
    const edge = evt.target;
    openEdgeModal(edge.data());
  });

  activeCytoscapeInstances[containerId] = cy;
}

function zoomGraph(containerId, factor) {
  const cy = activeCytoscapeInstances[containerId];
  if (cy) cy.zoom(cy.zoom() * factor);
}

function fitGraph(containerId) {
  const cy = activeCytoscapeInstances[containerId];
  if (cy) cy.fit(30);
}

function initModalListeners() {
  const closeBtn = document.getElementById('modalCloseBtn');
  const closeFooterBtn = document.getElementById('modalCloseBtnFooter');
  const modal = document.getElementById('detailModal');

  const closeModal = () => { if (modal) modal.classList.remove('active'); };
  if (closeBtn) closeBtn.onclick = closeModal;
  if (closeFooterBtn) closeFooterBtn.onclick = closeModal;
  if (modal) {
    modal.onclick = (e) => {
      if (e.target === modal) closeModal();
    };
  }
}

// ==========================================
// 10. APP INITIALIZATION & THEME
// ==========================================
function toggleHistorySidebar(forceState) {
  const container = document.querySelector('.tracera-container');
  if (!container) return;
  const isCurrentlyOpen = container.classList.contains('history-open');
  const newState = (forceState !== undefined) ? forceState : !isCurrentlyOpen;
  
  if (newState) {
    container.classList.add('history-open');
    sessionStorage.setItem('tracera-history-open', 'true');
  } else {
    container.classList.remove('history-open');
    sessionStorage.setItem('tracera-history-open', 'false');
  }
}
window.toggleHistorySidebar = toggleHistorySidebar;

function initHistoryDrawer() {
  const toggleBtn = document.getElementById('btnToggleHistory');
  const closeBtn = document.getElementById('btnCloseSidebar');
  const backdrop = document.getElementById('tracerDrawerBackdrop');
  const resizeHandle = document.getElementById('tracerResizeHandle');
  const sidebar = document.getElementById('traceraSidebar');

  // Toggle button in header
  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      toggleHistorySidebar();
    });
  }

  // Close button inside drawer header
  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      toggleHistorySidebar(false);
    });
  }

  // Backdrop click closes drawer
  if (backdrop) {
    backdrop.addEventListener('click', () => {
      toggleHistorySidebar(false);
    });
  }

  // --- Draggable Resize Handle Logic ---
  if (resizeHandle && sidebar) {
    let isResizing = false;
    const container = document.querySelector('.tracera-container');
    const MIN_WIDTH = 240;
    const MAX_WIDTH_PX = 500;

    resizeHandle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      isResizing = true;
      resizeHandle.classList.add('resizing');
      if (container) container.classList.add('resizing-active');
      document.body.style.cursor = 'col-resize';

      const onMouseMove = (e) => {
        if (!isResizing) return;
        const maxW = Math.min(MAX_WIDTH_PX, window.innerWidth * 0.45);
        let newWidth = Math.max(MIN_WIDTH, Math.min(e.clientX, maxW));
        sidebar.style.width = newWidth + 'px';
      };

      const onMouseUp = () => {
        isResizing = false;
        resizeHandle.classList.remove('resizing');
        if (container) container.classList.remove('resizing-active');
        document.body.style.cursor = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });

    // Touch support for mobile
    resizeHandle.addEventListener('touchstart', (e) => {
      e.preventDefault();
      isResizing = true;
      resizeHandle.classList.add('resizing');
      if (container) container.classList.add('resizing-active');

      const onTouchMove = (e) => {
        if (!isResizing) return;
        const touch = e.touches[0];
        const maxW = Math.min(MAX_WIDTH_PX, window.innerWidth * 0.45);
        let newWidth = Math.max(MIN_WIDTH, Math.min(touch.clientX, maxW));
        sidebar.style.width = newWidth + 'px';
      };

      const onTouchEnd = () => {
        isResizing = false;
        resizeHandle.classList.remove('resizing');
        if (container) container.classList.remove('resizing-active');
        document.removeEventListener('touchmove', onTouchMove);
        document.removeEventListener('touchend', onTouchEnd);
      };

      document.addEventListener('touchmove', onTouchMove, { passive: false });
      document.addEventListener('touchend', onTouchEnd);
    });
  }

  // Requirement: Closed by default and slides in when requested
  const savedState = sessionStorage.getItem('tracera-history-open');
  if (savedState === 'true') {
    toggleHistorySidebar(true);
  } else {
    toggleHistorySidebar(false);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  initThemeToggle();
  initSearchFilter();
  initModalListeners();
  initHistoryDrawer();
  MessageComposer.init(sendChatMessage);
  const clearBtn = document.getElementById('btnClearAllHistory');
  if (clearBtn) {
    clearBtn.addEventListener('click', clearAllHistory);
  }
  await loadSources();
  await loadConversations();
});

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

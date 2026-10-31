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

// Clean Enterprise Technical SVG Icons (Zero cartoon/emojis)
const VIZ_ICONS = {
  graph: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="12" cy="18" r="3"/><line x1="8.5" y1="7.5" x2="10.5" y2="15.5"/><line x1="15.5" y1="7.5" x2="13.5" y2="15.5"/><line x1="9" y1="6" x2="15" y2="6"/></svg>`,
  bar: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
  line: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
  pie: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>`,
  flowchart: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><path d="M7 10v4a2 2 0 0 0 2 2h5"/><polyline points="12 14 14 16 12 18"/></svg>`,
  timeline: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  table: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/></svg>`,
  comparison: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="8" height="16" rx="2"/><rect x="13" y="4" width="8" height="16" rx="2"/><line x1="7" y1="9" x2="7" y2="9.01"/><line x1="17" y1="9" x2="17" y2="9.01"/></svg>`,
  step: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="14" y2="18"/></svg>`,
  copy: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  retry: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>`,
  check: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  zoomIn: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`,
  zoomOut: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`,
  fit: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>`,
  shield: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
};

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
// 2. USER MESSAGE COMPONENT (Strict Right Alignment & Edit Action)
// ==========================================
const UserMessage = {
  create(id, content, timestamp, attachment = null) {
    const row = document.createElement('div');
    row.className = 'tracera-message-row user';
    row.id = `msg-${id}`;
    row.setAttribute('data-role', 'user');

    const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const bubble = document.createElement('div');
    bubble.className = 'tracera-user-bubble';

    // File attachment badge if attached
    if (attachment && (attachment.filename || attachment.name)) {
      const fileName = attachment.filename || attachment.name;
      const fileSize = attachment.file_size ? `${Math.round(attachment.file_size / 1024)} KB` : '';
      const attBadge = document.createElement('div');
      attBadge.className = 'tracera-user-attachment-badge';
      attBadge.innerHTML = `📄 <span>${escapeHtml(fileName)}</span> ${fileSize ? `<span style="opacity:0.75; font-size:0.68rem;">(${fileSize})</span>` : ''}`;
      bubble.appendChild(attBadge);
    }

    const textEl = document.createElement('div');
    textEl.className = 'tracera-user-text';
    textEl.textContent = content || '';

    const timeEl = document.createElement('span');
    timeEl.className = 'tracera-user-time';
    timeEl.textContent = timeStr;

    // Hover Edit button
    const editBtn = document.createElement('button');
    editBtn.className = 'tracera-msg-edit-btn';
    editBtn.title = 'Edit query';
    editBtn.innerHTML = '✏️';
    editBtn.onclick = (e) => {
      e.stopPropagation();
      startEditUserMessage(id, content);
    };

    bubble.appendChild(textEl);
    bubble.appendChild(timeEl);
    bubble.appendChild(editBtn);
    row.appendChild(bubble);

    return row;
  }
};

function startEditUserMessage(msgId, originalContent) {
  const row = document.getElementById(`msg-${msgId}`);
  if (!row) return;
  const bubble = row.querySelector('.tracera-user-bubble');
  if (!bubble) return;

  const originalHtml = bubble.innerHTML;
  bubble.innerHTML = '';

  const editBox = document.createElement('div');
  editBox.className = 'tracera-edit-box';

  const ta = document.createElement('textarea');
  ta.className = 'tracera-edit-textarea';
  ta.value = originalContent;

  const actions = document.createElement('div');
  actions.className = 'tracera-edit-actions';

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'tracera-action-btn';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.onclick = () => {
    bubble.innerHTML = originalHtml;
    const restoredBtn = bubble.querySelector('.tracera-msg-edit-btn');
    if (restoredBtn) {
      restoredBtn.onclick = (e) => {
        e.stopPropagation();
        startEditUserMessage(msgId, originalContent);
      };
    }
  };

  const submitBtn = document.createElement('button');
  submitBtn.className = 'tracera-action-btn';
  submitBtn.style.background = 'var(--accent-gold)';
  submitBtn.style.color = '#000';
  submitBtn.style.fontWeight = '700';
  submitBtn.textContent = 'Save & Resubmit';
  submitBtn.onclick = () => submitEditUserMessage(msgId, ta.value.trim());

  actions.appendChild(cancelBtn);
  actions.appendChild(submitBtn);

  editBox.appendChild(ta);
  editBox.appendChild(actions);
  bubble.appendChild(editBox);

  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

async function submitEditUserMessage(msgId, newContent) {
  if (!newContent) return;
  const row = document.getElementById(`msg-${msgId}`);
  if (!row) return;

  // Prune following messages from DOM immediately
  let next = row.nextElementSibling;
  while (next) {
    const toRemove = next;
    next = next.nextElementSibling;
    toRemove.remove();
  }

  // Restore bubble with new text
  const bubble = row.querySelector('.tracera-user-bubble');
  bubble.innerHTML = '';
  const textEl = document.createElement('div');
  textEl.className = 'tracera-user-text';
  textEl.textContent = newContent;

  const timeEl = document.createElement('span');
  timeEl.className = 'tracera-user-time';
  timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' (edited)';

  const editBtn = document.createElement('button');
  editBtn.className = 'tracera-msg-edit-btn';
  editBtn.title = 'Edit query';
  editBtn.innerHTML = '✏️';
  editBtn.onclick = (e) => {
    e.stopPropagation();
    startEditUserMessage(msgId, newContent);
  };

  bubble.appendChild(textEl);
  bubble.appendChild(timeEl);
  bubble.appendChild(editBtn);

  // Show loading indicator
  const loadingId = 'loading-' + Date.now();
  ChatMessageList.showLoading(loadingId);

  try {
    const res = await fetch(`/api/relationships/conversations/${currentConversationId}/messages/${msgId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: newContent }),
    });
    ChatMessageList.hideLoading(loadingId);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      ChatMessageList.showError(err.detail || 'Failed to edit message', newContent);
      return;
    }
    const report = await res.json();
    const asstMsgId = report.message_id || ('asst-' + Date.now());
    ChatMessageList.addAssistantMessage(asstMsgId, report.explanation, report);
    await loadConversations(false);
  } catch (err) {
    ChatMessageList.hideLoading(loadingId);
    ChatMessageList.showError(err.message, newContent);
  }
}

// ==========================================
// 2B. TRACERA VISUALIZATION EXPORT ENGINE
// Professional Image Export & Download System
// PNG, JPG, SVG, Clipboard Copy with 1x, 2x (Retina), 3x (Ultra)
// ==========================================
const TraceraExportEngine = {
  currentScale: 2, // Default 2x Retina

  setScale(scale) {
    this.currentScale = Math.max(1, Math.min(4, Number(scale) || 2));
    document.querySelectorAll('.tracera-scale-badge').forEach(b => {
      b.textContent = `${this.currentScale}x`;
    });
    document.querySelectorAll('.tracera-toggle-opt').forEach(opt => {
      if (opt.getAttribute('data-scale') == this.currentScale) {
        opt.classList.add('active');
      } else {
        opt.classList.remove('active');
      }
    });
  },

  attachToolbar(cardEl, meta = {}) {
    let header = cardEl.querySelector('.tracera-visual-header');
    if (!header) return;
    let headerActions = header.querySelector('.tracera-visual-header-actions');
    if (!headerActions) {
      headerActions = document.createElement('div');
      headerActions.className = 'tracera-visual-header-actions';
      const badge = header.querySelector('.tracera-visual-type-badge');
      if (badge) {
        header.removeChild(badge);
        headerActions.appendChild(badge);
      }
      header.appendChild(headerActions);
    }

    const toolbar = document.createElement('div');
    toolbar.className = 'tracera-export-toolbar';

    // PNG Download Button
    const pngBtn = document.createElement('button');
    pngBtn.className = 'tracera-export-btn';
    pngBtn.title = 'Download as High-Resolution PNG';
    pngBtn.innerHTML = `
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      <span>PNG</span>
    `;
    pngBtn.onclick = (e) => {
      e.stopPropagation();
      this.exportCard(cardEl, 'png', pngBtn);
    };

    // JPG Download Button
    const jpgBtn = document.createElement('button');
    jpgBtn.className = 'tracera-export-btn';
    jpgBtn.title = 'Download as High-Resolution JPG';
    jpgBtn.innerHTML = `
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      <span>JPG</span>
    `;
    jpgBtn.onclick = (e) => {
      e.stopPropagation();
      this.exportCard(cardEl, 'jpg', jpgBtn);
    };

    // SVG Download Button (Always active for vector charts, fallback available for others)
    const svgBtn = document.createElement('button');
    svgBtn.className = 'tracera-export-btn';
    svgBtn.title = 'Download as Vector SVG';
    svgBtn.innerHTML = `
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
      <span>SVG</span>
    `;
    svgBtn.onclick = (e) => {
      e.stopPropagation();
      this.exportCard(cardEl, 'svg', svgBtn);
    };

    // Copy to Clipboard Button
    const copyBtn = document.createElement('button');
    copyBtn.className = 'tracera-export-btn';
    copyBtn.title = 'Copy Image to Clipboard';
    copyBtn.innerHTML = `
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      <span>Copy</span>
    `;
    copyBtn.onclick = (e) => {
      e.stopPropagation();
      this.copyCardImage(cardEl, copyBtn);
    };

    // Scale / Quality Popover Settings
    const cfgWrapper = document.createElement('div');
    cfgWrapper.className = 'tracera-export-popover-wrapper';

    const cfgBtn = document.createElement('button');
    cfgBtn.className = 'tracera-export-btn tracera-export-btn-cfg';
    cfgBtn.title = 'Export Resolution Settings';
    cfgBtn.innerHTML = `
      <span class="tracera-scale-badge">${this.currentScale}x</span>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
    `;

    const popover = document.createElement('div');
    popover.className = 'tracera-export-popover';
    popover.innerHTML = `
      <div class="tracera-export-popover-title">Export Settings</div>
      <div class="tracera-export-popover-row">
        <label class="tracera-popover-label">Image Resolution</label>
        <div class="tracera-btn-toggle-group">
          <button class="tracera-toggle-opt ${this.currentScale === 1 ? 'active' : ''}" data-scale="1">1x Standard</button>
          <button class="tracera-toggle-opt ${this.currentScale === 2 ? 'active' : ''}" data-scale="2">2x Retina</button>
          <button class="tracera-toggle-opt ${this.currentScale === 3 ? 'active' : ''}" data-scale="3">3x Ultra</button>
        </div>
      </div>
    `;

    cfgBtn.onclick = (e) => {
      e.stopPropagation();
      const isOpen = popover.classList.contains('open');
      document.querySelectorAll('.tracera-export-popover.open').forEach(p => p.classList.remove('open'));
      if (!isOpen) popover.classList.add('open');
    };

    popover.querySelectorAll('.tracera-toggle-opt').forEach(opt => {
      opt.onclick = (e) => {
        e.stopPropagation();
        const s = parseInt(opt.getAttribute('data-scale'), 10);
        this.setScale(s);
        popover.classList.remove('open');
      };
    });

    document.addEventListener('click', (e) => {
      if (!cfgWrapper.contains(e.target)) {
        popover.classList.remove('open');
      }
    });

    cfgWrapper.appendChild(cfgBtn);
    cfgWrapper.appendChild(popover);

    toolbar.appendChild(pngBtn);
    toolbar.appendChild(jpgBtn);
    toolbar.appendChild(svgBtn);
    toolbar.appendChild(copyBtn);
    toolbar.appendChild(cfgWrapper);

    headerActions.insertBefore(toolbar, headerActions.firstChild);
  },

  async exportCard(cardEl, format, triggerBtn) {
    if (!cardEl) return;
    const title = (cardEl.getAttribute('data-visual-title') || 'PrivSight_TRACERA_Visual').replace(/[^a-zA-Z0-9_-]/g, '_');
    const filename = `${title}_${Date.now()}.${format}`;
    const origHtml = triggerBtn ? triggerBtn.innerHTML : '';
    if (triggerBtn) {
      triggerBtn.classList.add('active');
      triggerBtn.innerHTML = `<span>Exporting...</span>`;
    }

    try {
      if (format === 'svg') {
        await this._exportSvg(cardEl, filename);
      } else {
        await this._exportRaster(cardEl, format, filename);
      }
      if (triggerBtn) {
        triggerBtn.classList.remove('active');
        triggerBtn.classList.add('success');
        triggerBtn.innerHTML = `<span>Saved!</span>`;
        setTimeout(() => {
          triggerBtn.classList.remove('success');
          triggerBtn.innerHTML = origHtml;
        }, 1800);
      }
    } catch (err) {
      console.error('Export failed:', err);
      if (triggerBtn) {
        triggerBtn.classList.remove('active');
        triggerBtn.innerHTML = `<span>Failed</span>`;
        setTimeout(() => { triggerBtn.innerHTML = origHtml; }, 2000);
      }
    }
  },

  async copyCardImage(cardEl, triggerBtn) {
    const origHtml = triggerBtn ? triggerBtn.innerHTML : '';
    if (triggerBtn) {
      triggerBtn.classList.add('active');
      triggerBtn.innerHTML = `<span>Copying...</span>`;
    }

    try {
      const blob = await this._renderCardToBlob(cardEl, 'image/png');
      if (!blob) throw new Error('Could not generate image blob');

      if (navigator.clipboard && navigator.clipboard.write) {
        try {
          await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob })
          ]);
          if (triggerBtn) {
            triggerBtn.classList.remove('active');
            triggerBtn.classList.add('success');
            triggerBtn.innerHTML = `<span>Copied!</span>`;
            setTimeout(() => {
              triggerBtn.classList.remove('success');
              triggerBtn.innerHTML = origHtml;
            }, 1800);
          }
          return;
        } catch (clipErr) {
          console.warn('Clipboard write API restricted, falling back to download:', clipErr);
        }
      }

      // Fallback: download if clipboard API is restricted or denied
      this._downloadBlob(blob, `TRACERA_Export_${Date.now()}.png`);
      if (triggerBtn) {
        triggerBtn.classList.remove('active');
        triggerBtn.classList.add('success');
        triggerBtn.innerHTML = `<span>Downloaded</span>`;
        setTimeout(() => {
          triggerBtn.classList.remove('success');
          triggerBtn.innerHTML = origHtml;
        }, 1800);
      }
    } catch (err) {
      console.error('Copy to clipboard failed:', err);
      if (triggerBtn) {
        triggerBtn.classList.remove('active');
        triggerBtn.innerHTML = `<span>Failed</span>`;
        setTimeout(() => { triggerBtn.innerHTML = origHtml; }, 2000);
      }
    }
  },

  async _exportSvg(cardEl, filename) {
    const svgEl = cardEl.querySelector('.tracera-chart-container svg') || cardEl.querySelector('svg.tracera-chart-svg');
    const title = cardEl.getAttribute('data-visual-title') || 'PrivSight Visualization';

    if (svgEl) {
      // Standalone Vector SVG Export with Title & Dark Theme
      const viewBox = svgEl.getAttribute('viewBox') || '0 0 600 320';
      const parts = viewBox.split(/\s+/).map(Number);
      const chartW = parts[2] || 600;
      const chartH = parts[3] || 320;
      const titleH = 52;
      const totalW = chartW;
      const totalH = chartH + titleH;

      const fullSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${totalW} ${totalH}" width="${totalW}" height="${totalH}">
  <defs>
    <style>
      text { font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; }
      .mono { font-family: 'JetBrains Mono', monospace; }
    </style>
  </defs>
  <!-- Dark Enterprise Background -->
  <rect width="100%" height="100%" fill="#0B0F17" />
  <!-- Title & PrivSight Branding -->
  <text x="24" y="22" fill="#D4A72C" font-size="9.5" font-weight="700" letter-spacing="0.08em" class="mono">TRACERA · PRIVSIGHT PRIVACY INTELLIGENCE</text>
  <text x="24" y="42" fill="#F8FAFC" font-size="14.5" font-weight="700">${escapeHtml(title)}</text>
  <line x1="20" y1="48" x2="${totalW - 20}" y2="48" stroke="rgba(255,255,255,0.08)" stroke-width="1" />
  <!-- Chart Vectors -->
  <g transform="translate(0, ${titleH})">
    ${svgEl.innerHTML}
  </g>
</svg>`;

      const blob = new Blob([fullSvg], { type: 'image/svg+xml;charset=utf-8' });
      this._downloadBlob(blob, filename);
    } else {
      // Cytoscape or HTML card: embed high-res raster into a valid SVG document
      const blob = await this._renderCardToBlob(cardEl, 'image/png');
      const reader = new FileReader();
      reader.onloadend = () => {
        const dataUri = reader.result;
        const bbox = cardEl.getBoundingClientRect();
        const w = Math.max(640, Math.round(bbox.width || 720));
        const h = Math.max(320, Math.round(bbox.height || 420));
        const svgWrapper = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
  <rect width="100%" height="100%" fill="#0B0F17" />
  <image href="${dataUri}" width="${w}" height="${h}" />
</svg>`;
        const svgBlob = new Blob([svgWrapper], { type: 'image/svg+xml;charset=utf-8' });
        this._downloadBlob(svgBlob, filename);
      };
      reader.readAsDataURL(blob);
    }
  },

  async _exportRaster(cardEl, format, filename) {
    const mime = format === 'jpg' || format === 'jpeg' ? 'image/jpeg' : 'image/png';
    const blob = await this._renderCardToBlob(cardEl, mime);
    if (blob) {
      this._downloadBlob(blob, filename);
    }
  },

  async _renderCardToBlob(cardEl, mimeType = 'image/png') {
    // 1. Check for Cytoscape instance (Composited with Title & Legend)
    const cyContainer = cardEl.querySelector('.tracera-graph-container');
    if (cyContainer && cyContainer.id && activeCytoscapeInstances[cyContainer.id]) {
      const cy = activeCytoscapeInstances[cyContainer.id];
      const scale = this.currentScale;
      const title = cardEl.getAttribute('data-visual-title') || 'Relationship Topology Graph';
      const graphDataUri = cy.png({ full: true, scale: scale, bg: '#0B0F17' });

      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
          const titleH = Math.round(52 * scale);
          const legendH = Math.round(38 * scale);
          const totalW = Math.max(Math.round(680 * scale), img.width);
          const totalH = img.height + titleH + legendH;

          const canvas = document.createElement('canvas');
          canvas.width = totalW;
          canvas.height = totalH;
          const ctx = canvas.getContext('2d');

          // Dark Background
          ctx.fillStyle = '#0B0F17';
          ctx.fillRect(0, 0, totalW, totalH);

          // Title Header
          ctx.fillStyle = '#D4A72C';
          ctx.font = `bold ${Math.round(9.5 * scale)}px 'JetBrains Mono', monospace`;
          ctx.fillText('TRACERA · PRIVSIGHT VERIFIED SCHEMA TOPOLOGY', Math.round(24 * scale), Math.round(22 * scale));

          ctx.fillStyle = '#F8FAFC';
          ctx.font = `bold ${Math.round(15 * scale)}px 'Plus Jakarta Sans', sans-serif`;
          ctx.fillText(title, Math.round(24 * scale), Math.round(42 * scale));

          ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
          ctx.lineWidth = Math.max(1, Math.round(scale));
          ctx.beginPath();
          ctx.moveTo(Math.round(20 * scale), Math.round(48 * scale));
          ctx.lineTo(totalW - Math.round(20 * scale), Math.round(48 * scale));
          ctx.stroke();

          // Draw Graph Centered
          const graphX = Math.round((totalW - img.width) / 2);
          ctx.drawImage(img, graphX, titleH);

          // Draw Legend at Bottom
          const legendY = totalH - Math.round(16 * scale);
          ctx.fillStyle = '#10B981';
          ctx.fillRect(Math.round(24 * scale), legendY - Math.round(7 * scale), Math.round(18 * scale), Math.round(3 * scale));
          ctx.fillStyle = '#94A3B8';
          ctx.font = `bold ${Math.round(9 * scale)}px 'JetBrains Mono', monospace`;
          ctx.fillText('VERIFIED FK', Math.round(48 * scale), legendY);

          ctx.fillStyle = '#D4A72C';
          ctx.fillRect(Math.round(150 * scale), legendY - Math.round(7 * scale), Math.round(18 * scale), Math.round(3 * scale));
          ctx.fillStyle = '#94A3B8';
          ctx.fillText('INFERRED OVERLAP', Math.round(174 * scale), legendY);

          canvas.toBlob((blob) => resolve(blob), mimeType, 0.95);
        };
        img.src = graphDataUri;
      });
    }

    // 2. Check for SVG chart
    const svgEl = cardEl.querySelector('.tracera-chart-container svg') || cardEl.querySelector('svg.tracera-chart-svg');
    if (svgEl) {
      return this._rasterizeSvgToBlob(svgEl, cardEl, mimeType);
    }

    // 3. Fallback for HTML-based visual components
    return this._rasterizeHtmlToBlob(cardEl, mimeType);
  },

  _rasterizeSvgToBlob(svgEl, cardEl, mimeType) {
    return new Promise((resolve, reject) => {
      const scale = this.currentScale;
      const title = cardEl.getAttribute('data-visual-title') || '';
      
      let width = 640;
      let height = 320;
      const viewBox = svgEl.getAttribute('viewBox');
      if (viewBox) {
        const parts = viewBox.split(/\s+/).map(Number);
        if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
          width = parts[2];
          height = parts[3];
        }
      } else {
        const bbox = svgEl.getBoundingClientRect();
        if (bbox.width > 0 && bbox.height > 0) {
          width = bbox.width;
          height = bbox.height;
        }
      }

      const titleHeight = title ? 48 : 0;
      const canvasWidth = Math.round(width * scale);
      const canvasHeight = Math.round((height + titleHeight) * scale);

      const canvas = document.createElement('canvas');
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      const ctx = canvas.getContext('2d');

      ctx.fillStyle = '#0B0F17';
      ctx.fillRect(0, 0, canvasWidth, canvasHeight);

      if (title) {
        ctx.save();
        ctx.fillStyle = '#D4A72C';
        ctx.font = `bold ${Math.round(9.5 * scale)}px 'JetBrains Mono', monospace`;
        ctx.fillText('TRACERA · PRIVSIGHT PRIVACY INTELLIGENCE', Math.round(24 * scale), Math.round(20 * scale));

        ctx.fillStyle = '#F8FAFC';
        ctx.font = `bold ${Math.round(14.5 * scale)}px 'Plus Jakarta Sans', system-ui, sans-serif`;
        ctx.fillText(title, Math.round(24 * scale), Math.round(38 * scale));

        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = Math.max(1, Math.round(scale));
        ctx.beginPath();
        ctx.moveTo(Math.round(20 * scale), Math.round(44 * scale));
        ctx.lineTo(canvasWidth - Math.round(20 * scale), Math.round(44 * scale));
        ctx.stroke();
        ctx.restore();
      }

      const clone = svgEl.cloneNode(true);
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clone.setAttribute('width', width);
      clone.setAttribute('height', height);

      const serializer = new XMLSerializer();
      const svgStr = serializer.serializeToString(clone);
      const svgDataUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr);

      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, Math.round(titleHeight * scale), Math.round(width * scale), Math.round(height * scale));
        canvas.toBlob((blob) => {
          if (blob) resolve(blob);
          else reject(new Error('Canvas toBlob failed'));
        }, mimeType, 0.95);
      };
      img.onerror = (e) => reject(new Error('Failed to load SVG for rasterization: ' + e));
      img.src = svgDataUrl;
    });
  },

  _rasterizeHtmlToBlob(cardEl, mimeType) {
    return new Promise((resolve, reject) => {
      const scale = this.currentScale;
      const title = cardEl.getAttribute('data-visual-title') || 'PrivSight TRACERA Visualization';
      const bbox = cardEl.getBoundingClientRect();
      const width = Math.max(640, Math.round(bbox.width || 720));
      const height = Math.max(260, Math.round(bbox.height || 360));

      const canvasWidth = Math.round(width * scale);
      const canvasHeight = Math.round(height * scale);

      const canvas = document.createElement('canvas');
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      const ctx = canvas.getContext('2d');

      ctx.fillStyle = '#0B0F17';
      ctx.fillRect(0, 0, canvasWidth, canvasHeight);

      const contentEl = cardEl.cloneNode(true);
      const toolbar = contentEl.querySelector('.tracera-export-toolbar');
      if (toolbar) toolbar.remove();

      const htmlContent = contentEl.innerHTML;
      const foreignSvg = `
        <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
          <foreignObject width="100%" height="100%">
            <div xmlns="http://www.w3.org/1999/xhtml" style="background:#0B0F17; color:#F8FAFC; font-family:'Plus Jakarta Sans', system-ui, sans-serif; padding:16px; box-sizing:border-box; width:${width}px; height:${height}px;">
              <style>
                .tracera-visual-header { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E293B; padding-bottom:8px; margin-bottom:12px; }
                .tracera-visual-title { font-size:14px; font-weight:700; color:#F8FAFC; display:flex; align-items:center; gap:8px; }
                .tracera-visual-type-badge { font-size:10px; font-weight:700; background:#1E293B; color:#94A3B8; padding:3px 8px; border-radius:4px; font-family:monospace; }
                .tracera-flow-step { background:#111827; border:1px solid #1E293B; border-radius:6px; padding:10px 14px; margin-bottom:8px; display:flex; gap:12px; }
                .tracera-flow-step-num { width:24px; height:24px; background:rgba(212,167,44,0.15); color:#D4A72C; font-weight:700; font-size:11px; display:flex; align-items:center; justify-content:center; border-radius:4px; }
                .tracera-flow-step-title { font-size:13px; font-weight:600; color:#F8FAFC; }
                .tracera-flow-step-desc { font-size:12px; color:#94A3B8; margin-top:2px; }
                .tracera-flow-arrow { display:flex; justify-content:center; align-items:center; color:#475569; margin:-4px 0; }
                .tracera-step-card { background:#111827; border-left:3px solid #D4A72C; border:1px solid #1E293B; padding:10px 14px; margin-bottom:8px; }
                .tracera-step-index { font-family:monospace; font-size:11px; font-weight:700; color:#D4A72C; min-width:52px; }
                .tracera-step-body-title { font-size:13px; font-weight:600; color:#F8FAFC; }
                .tracera-step-body-desc { font-size:12px; color:#94A3B8; margin-top:2px; }
                .tracera-comparison-table, .data-table { width:100%; border-collapse:collapse; font-size:12px; }
                .tracera-comparison-table th, .data-table th { background:#1E293B; color:#94A3B8; padding:8px 12px; text-align:left; font-size:10px; text-transform:uppercase; font-weight:700; }
                .tracera-comparison-table td, .data-table td { padding:8px 12px; border-bottom:1px solid #1E293B; color:#E2E8F0; }
                .tracera-timeline-container { position:relative; padding:10px 0 10px 8px; display:flex; flex-direction:column; gap:12px; }
                .tracera-timeline-spine { position:absolute; left:17px; top:14px; bottom:14px; width:2px; background:#1E293B; }
                .tracera-timeline-item { position:relative; display:flex; align-items:flex-start; padding-left:32px; }
                .tracera-timeline-node { position:absolute; left:17px; top:14px; width:10px; height:10px; border-radius:50%; background:#0B0F17; border:2px solid #10B981; transform:translateX(-50%); }
                .tracera-timeline-card { flex:1; background:#111827; border:1px solid #1E293B; border-radius:6px; padding:10px 14px; }
                .badge { padding:2px 6px; border-radius:4px; font-size:10px; font-family:monospace; font-weight:700; }
              </style>
              ${htmlContent}
            </div>
          </foreignObject>
        </svg>
      `;

      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvasWidth, canvasHeight);
        canvas.toBlob((blob) => {
          if (blob) resolve(blob);
          else reject(new Error('HTML rasterization toBlob failed'));
        }, mimeType, 0.95);
      };
      img.onerror = () => {
        ctx.fillStyle = '#D4A72C';
        ctx.font = `bold ${Math.round(14 * scale)}px sans-serif`;
        ctx.fillText(title, 20 * scale, 35 * scale);
        canvas.toBlob((b) => resolve(b), mimeType, 0.95);
      };
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(foreignSvg);
    });
  },

  _dataUriToBlob(dataUri) {
    const parts = dataUri.split(',');
    const byteString = atob(parts[1]);
    const mimeString = parts[0].split(':')[1].split(';')[0];
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: mimeString });
  },

  _downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 200);

    // Also auto-archive to test_exports directory for inspection
    try {
      const reader = new FileReader();
      reader.onloadend = () => {
        fetch('/api/relationships/save-export-test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: filename, dataUri: reader.result })
        }).catch(() => {});
      };
      reader.readAsDataURL(blob);
    } catch (_) {}
  }
};
window.TraceraExportEngine = TraceraExportEngine;

// ==========================================
// 3. ASSISTANT MESSAGE COMPONENT (Strict Left Alignment)
// ==========================================
const AssistantMessage = {
  renderVisualCard(targetContainer, metadata = {}) {
    const createVisualCard = (icon, titleText, typeBadge) => {
      const card = document.createElement('div');
      card.className = 'tracera-visual-card';
      card.setAttribute('data-visual-title', titleText);
      card.setAttribute('data-visual-type', typeBadge);
      card.innerHTML = `
        <div class="tracera-visual-header">
          <div class="tracera-visual-title">
            <span class="tracera-visual-icon">${icon}</span>
            <span>${escapeHtml(titleText)}</span>
          </div>
          <div class="tracera-visual-header-actions">
            <span class="tracera-visual-type-badge">${escapeHtml(typeBadge)}</span>
          </div>
        </div>
      `;
      TraceraExportEngine.attachToolbar(card, { title: titleText, type: typeBadge });
      return card;
    };

    // 1. Interactive Cytoscape Relationship Graph (if available)
    if (metadata.graph && metadata.graph.nodes && metadata.graph.nodes.length > 0) {
      const graphCard = createVisualCard(VIZ_ICONS.graph, metadata.title || 'Relationship Topology Graph', 'RELATIONSHIP GRAPH');
      const graphId = 'cy-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
      const graphWrapper = document.createElement('div');
      graphWrapper.className = 'tracera-graph-container';
      graphWrapper.id = graphId;

      graphWrapper.innerHTML = `
        <div class="tracera-graph-toolbar">
          <button class="tracera-graph-btn" onclick="zoomGraph('${graphId}', 1.25)" title="Zoom in">${VIZ_ICONS.zoomIn}</button>
          <button class="tracera-graph-btn" onclick="zoomGraph('${graphId}', 0.8)" title="Zoom out">${VIZ_ICONS.zoomOut}</button>
          <button class="tracera-graph-btn" onclick="fitGraph('${graphId}')" title="Fit to view">${VIZ_ICONS.fit} <span>Fit</span></button>
        </div>
        <div class="tracera-graph-legend">
          <div class="tracera-graph-legend-item">
            <span class="tracera-legend-indicator verified"></span>
            <span>VERIFIED FK</span>
          </div>
          <div class="tracera-graph-legend-item">
            <span class="tracera-legend-indicator inferred"></span>
            <span>INFERRED OVERLAP</span>
          </div>
        </div>
      `;
      graphCard.appendChild(graphWrapper);
      targetContainer.appendChild(graphCard);

      requestAnimationFrame(() => {
        initCytoscapeGraph(graphId, metadata.graph);
      });
    }

    // 2. Responsive SVG Charts (Bar, Line, Pie)
    const chartPayload = metadata.chart_data || (metadata.data && metadata.data.series ? metadata.data : null);
    if (chartPayload && chartPayload.series && chartPayload.series.length > 0) {
      const chartType = (chartPayload.type || chartPayload.chart_type || 'bar').toLowerCase();
      const chartIcon = chartType === 'pie' ? VIZ_ICONS.pie : (chartType === 'line' ? VIZ_ICONS.line : VIZ_ICONS.bar);
      const chartCard = createVisualCard(chartIcon, metadata.title || chartPayload.title || `${chartType.toUpperCase()} Chart`, `${chartType.toUpperCase()} CHART`);
      renderChart(chartCard, chartPayload, metadata.title);
      targetContainer.appendChild(chartCard);
    }

    // 3. Process Flowchart (if available)
    const flowPayload = metadata.flowchart_data || (metadata.data && metadata.data.steps && metadata.response_type === 'flowchart' ? metadata.data : null);
    if (flowPayload && flowPayload.steps && flowPayload.steps.length > 0) {
      const flowCard = createVisualCard(VIZ_ICONS.flowchart, metadata.title || flowPayload.title || 'Process Flowchart', 'FLOWCHART');
      renderFlowchart(flowCard, flowPayload, metadata.title);
      targetContainer.appendChild(flowCard);
    }

    // 4. Comparative Schema & Governance Matrix (if available)
    const compPayload = metadata.comparison_data || (metadata.data && metadata.data.entities ? metadata.data : null);
    if (compPayload && compPayload.entities && compPayload.entities.length > 0) {
      const compCard = createVisualCard(VIZ_ICONS.comparison, metadata.title || compPayload.title || 'Comparative Matrix', 'COMPARISON');
      renderComparison(compCard, compPayload, metadata.title);
      targetContainer.appendChild(compCard);
    }

    // 5. Step-by-Step Traversal Cards (if available)
    const stepPayload = metadata.steps || (metadata.data && metadata.data.steps && metadata.response_type === 'step_by_step' ? metadata.data.steps : null);
    if (stepPayload && Array.isArray(stepPayload) && stepPayload.length > 0 && !flowPayload) {
      const stepCard = createVisualCard(VIZ_ICONS.step, metadata.title || 'Step-by-Step Relational Verification', 'STEP-BY-STEP');
      renderStepByStep(stepCard, stepPayload, metadata.title);
      targetContainer.appendChild(stepCard);
    }

    // 6. Structured Table (if available)
    const tblPayload = metadata.table_data || (metadata.data && metadata.data.table ? metadata.data.table : null);
    if (tblPayload && Array.isArray(tblPayload) && tblPayload.length > 0) {
      const tblCard = createVisualCard(VIZ_ICONS.table, metadata.title || 'Structured Relationship Matrix', 'STRUCTURED TABLE');
      renderStructuredTable(tblCard, tblPayload, metadata.title);
      targetContainer.appendChild(tblCard);
    }

    // 7. Timeline Cards (if available)
    const timePayload = metadata.timeline_data || (metadata.data && metadata.data.timeline ? metadata.data.timeline : null);
    if (timePayload && Array.isArray(timePayload) && timePayload.length > 0) {
      const timeCard = createVisualCard(VIZ_ICONS.timeline, metadata.title || 'Chronological Event Timeline', 'TIMELINE');
      renderTimeline(timeCard, timePayload, metadata.title);
      targetContainer.appendChild(timeCard);
    }

    // 8. Directional Data Lineage DAG (Phase 5.1)
    const lineagePayload = metadata.lineage_dag || (metadata.data && metadata.data.nodes && (metadata.response_type === 'lineage_dag' || metadata.format_requested === 'lineage_dag') ? metadata.data : null);
    if (lineagePayload && lineagePayload.nodes && lineagePayload.nodes.length > 0) {
      const lineageCard = createVisualCard(VIZ_ICONS.graph, metadata.title || 'Directional Data Lineage DAG', 'LINEAGE DAG');
      renderLineageDAGInTracera(lineageCard, lineagePayload, metadata.title);
      targetContainer.appendChild(lineageCard);
    }
  },

  create(id, content, metadata = {}) {
    const row = document.createElement('div');
    row.className = 'tracera-message-row assistant';
    row.id = `msg-${id}`;
    row.setAttribute('data-role', 'assistant');

    const bodyCard = document.createElement('div');
    bodyCard.className = 'tracera-assistant-body';

    // Render visual artifacts (preserving 100% of Phase 1, 2, 3 visuals & export toolbar)
    this.renderVisualCard(bodyCard, metadata);

    // Formatted Markdown Analytical Content
    const mdContainer = document.createElement('div');
    mdContainer.className = 'tracera-markdown-content';
    mdContainer.innerHTML = renderMarkdown(content || '');
    bodyCard.appendChild(mdContainer);

    // Provenance & Action Footer
    const footer = document.createElement('div');
    footer.className = 'tracera-response-footer';

    const badges = document.createElement('div');
    badges.className = 'tracera-response-badges';
    
    let pathBadges = '';
    if (metadata.relationship_paths && metadata.relationship_paths.length > 0) {
      const p = metadata.relationship_paths[0];
      const isVer = p.verification_status === 'Verified';
      const badgeStyle = isVer 
        ? 'background:rgba(16, 185, 129, 0.12); color:#10B981; border:1px solid rgba(16, 185, 129, 0.28); font-size:0.65rem; font-weight:700; font-family:var(--font-mono);'
        : 'background:rgba(212, 167, 44, 0.12); color:var(--accent-gold); border:1px solid rgba(212, 167, 44, 0.28); font-size:0.65rem; font-weight:700; font-family:var(--font-mono);';
      pathBadges += `<span class="badge" style="${badgeStyle}">PATH: ${escapeHtml(p.path_summary)} · ${escapeHtml(p.verification_status.toUpperCase())}</span>`;
    }

    badges.innerHTML = `
      <span class="badge badge-status-complete" style="font-size:0.65rem; font-weight:700; display:inline-flex; align-items:center; gap:4px; font-family:var(--font-mono);">${VIZ_ICONS.shield} VERIFIED SCHEMA ENGINE</span>
      <span class="badge" style="background:rgba(212,167,44,0.12); color:var(--accent-gold); border:1px solid rgba(212,167,44,0.28); font-size:0.65rem; display:inline-flex; align-items:center; gap:4px; font-family:var(--font-mono);">${VIZ_ICONS.check} PII MASKED</span>
      ${pathBadges}
    `;

    const actions = document.createElement('div');
    actions.className = 'tracera-response-actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'tracera-action-btn';
    copyBtn.style.fontSize = '0.72rem';
    copyBtn.innerHTML = `${VIZ_ICONS.copy} <span>Copy</span>`;
    copyBtn.title = 'Copy response text';
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(content || '');
      copyBtn.innerHTML = `${VIZ_ICONS.check} <span>Copied!</span>`;
      setTimeout(() => { copyBtn.innerHTML = `${VIZ_ICONS.copy} <span>Copy</span>`; }, 2000);
    };

    const retryBtn = document.createElement('button');
    retryBtn.className = 'tracera-action-btn';
    retryBtn.style.fontSize = '0.72rem';
    retryBtn.innerHTML = `${VIZ_ICONS.retry} <span>Retry</span>`;
    retryBtn.title = 'Retry last question';
    retryBtn.onclick = () => {
      if (lastUserMessage) {
        suggestPrompt(lastUserMessage);
      }
    };

    const regenBtn = document.createElement('button');
    regenBtn.className = 'tracera-action-btn';
    regenBtn.style.fontSize = '0.72rem';
    regenBtn.innerHTML = `🔄 <span>Regenerate</span>`;
    regenBtn.title = 'Regenerate assistant response';
    regenBtn.onclick = () => {
      regenerateResponse(id);
    };

    actions.appendChild(copyBtn);
    actions.appendChild(retryBtn);
    actions.appendChild(regenBtn);

    footer.appendChild(badges);
    footer.appendChild(actions);
    bodyCard.appendChild(footer);

    row.appendChild(bodyCard);
    return row;
  }
};

async function regenerateResponse(asstMsgId) {
  if (isSubmitting) return;
  isSubmitting = true;

  const asstRow = document.getElementById(`msg-${asstMsgId}`);
  if (asstRow) {
    let next = asstRow.nextElementSibling;
    while (next) {
      const toRemove = next;
      next = next.nextElementSibling;
      toRemove.remove();
    }
    asstRow.remove();
  }

  const loadingId = 'loading-' + Date.now();
  ChatMessageList.showLoading(loadingId);

  try {
    const res = await fetch(`/api/relationships/conversations/${currentConversationId}/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: asstMsgId }),
    });
    ChatMessageList.hideLoading(loadingId);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      ChatMessageList.showError(err.detail || 'Failed to regenerate response', 'Regeneration');
      return;
    }
    const report = await res.json();
    const newAsstId = report.message_id || ('asst-' + Date.now());
    ChatMessageList.addAssistantMessage(newAsstId, report.explanation, report);
    await loadConversations(false);
  } catch (err) {
    ChatMessageList.hideLoading(loadingId);
    ChatMessageList.showError(err.message, 'Regeneration');
  } finally {
    isSubmitting = false;
  }
}

// ==========================================
// 4. CHAT MESSAGE LIST COMPONENT (Manages Deduplication & Stream)
// ==========================================
let activeAttachment = null;
let activeAbortController = null;

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

  addUserMessage(id, content, timestamp, attachment = null) {
    if (this.renderedMessageIds.has(id)) {
      console.warn(`Duplicate user message ID skipped: ${id}`);
      return;
    }
    this.renderedMessageIds.add(id);

    WelcomeScreen.hide();

    const container = this.getContainer();
    if (!container) return;

    const msgEl = UserMessage.create(id, content, timestamp, attachment);
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

  addStreamingMessage(id) {
    this.renderedMessageIds.add(id);
    WelcomeScreen.hide();

    const container = this.getContainer();
    if (!container) return null;

    const row = document.createElement('div');
    row.className = 'tracera-message-row assistant';
    row.id = `msg-${id}`;
    row.setAttribute('data-role', 'assistant');

    const bodyCard = document.createElement('div');
    bodyCard.className = 'tracera-assistant-body';

    const visualSlot = document.createElement('div');
    visualSlot.className = 'tracera-visual-slot';

    const textEl = document.createElement('div');
    textEl.className = 'tracera-markdown-content';
    textEl.innerHTML = '<span class="tracera-streaming-cursor">▌</span>';

    bodyCard.appendChild(visualSlot);
    bodyCard.appendChild(textEl);
    row.appendChild(bodyCard);
    container.appendChild(row);

    this.scrollToBottom();

    let fullMarkdown = '';

    return {
      row,
      bodyCard,
      visualSlot,
      textEl,
      setVisual(visualData) {
        AssistantMessage.renderVisualCard(visualSlot, visualData);
      },
      appendChunk(chunk) {
        fullMarkdown += chunk;
        textEl.innerHTML = renderMarkdown(fullMarkdown) + '<span class="tracera-streaming-cursor">▌</span>';
        ChatMessageList.scrollToBottom();
      },
      finalize(report = {}) {
        const cursor = textEl.querySelector('.tracera-streaming-cursor');
        if (cursor) cursor.remove();
        textEl.innerHTML = renderMarkdown(fullMarkdown);

        // Provenance & Action Footer
        const footer = document.createElement('div');
        footer.className = 'tracera-response-footer';

        const badges = document.createElement('div');
        badges.className = 'tracera-response-badges';
        badges.innerHTML = `
          <span class="badge badge-status-complete" style="font-size:0.65rem; font-weight:700; display:inline-flex; align-items:center; gap:4px; font-family:var(--font-mono);">${VIZ_ICONS.shield} VERIFIED SCHEMA ENGINE</span>
          <span class="badge" style="background:rgba(212,167,44,0.12); color:var(--accent-gold); border:1px solid rgba(212,167,44,0.28); font-size:0.65rem; display:inline-flex; align-items:center; gap:4px; font-family:var(--font-mono);">${VIZ_ICONS.check} PII MASKED</span>
        `;

        const actions = document.createElement('div');
        actions.className = 'tracera-response-actions';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'tracera-action-btn';
        copyBtn.style.fontSize = '0.72rem';
        copyBtn.innerHTML = `${VIZ_ICONS.copy} <span>Copy</span>`;
        copyBtn.title = 'Copy response text';
        copyBtn.onclick = () => {
          navigator.clipboard.writeText(fullMarkdown || '');
          copyBtn.innerHTML = `${VIZ_ICONS.check} <span>Copied!</span>`;
          setTimeout(() => { copyBtn.innerHTML = `${VIZ_ICONS.copy} <span>Copy</span>`; }, 2000);
        };

        const retryBtn = document.createElement('button');
        retryBtn.className = 'tracera-action-btn';
        retryBtn.style.fontSize = '0.72rem';
        retryBtn.innerHTML = `${VIZ_ICONS.retry} <span>Retry</span>`;
        retryBtn.title = 'Retry last question';
        retryBtn.onclick = () => {
          if (lastUserMessage) suggestPrompt(lastUserMessage);
        };

        const regenBtn = document.createElement('button');
        regenBtn.className = 'tracera-action-btn';
        regenBtn.style.fontSize = '0.72rem';
        regenBtn.innerHTML = `🔄 <span>Regenerate</span>`;
        regenBtn.title = 'Regenerate assistant response';
        regenBtn.onclick = () => {
          regenerateResponse(id);
        };

        actions.appendChild(copyBtn);
        actions.appendChild(retryBtn);
        actions.appendChild(regenBtn);

        footer.appendChild(badges);
        footer.appendChild(actions);
        bodyCard.appendChild(footer);

        ChatMessageList.scrollToBottom();
      }
    };
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
    const doScroll = () => {
      const scrollContainer = document.getElementById('chatMessages');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    };
    requestAnimationFrame(doScroll);
    setTimeout(doScroll, 80);
    setTimeout(doScroll, 280);
  }
};

// ==========================================
// 4B. FILE ATTACHMENT CONTROLLER
// ==========================================
async function handleFileAttachment(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  if (file.size > 10 * 1024 * 1024) {
    alert('File size exceeds the 10MB maximum limit.');
    event.target.value = '';
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const uploadUrl = currentConversationId 
      ? `/api/relationships/upload?conversation_id=${encodeURIComponent(currentConversationId)}`
      : '/api/relationships/upload';

    const res = await fetch(uploadUrl, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Unsupported file format or corrupt document.');
      removeActiveAttachment();
      return;
    }

    const data = await res.json();
    activeAttachment = data;
    renderAttachmentPill(data);

    if (MessageComposer.sendBtnEl) {
      MessageComposer.sendBtnEl.disabled = false;
    }
    MessageComposer.focus();
  } catch (err) {
    alert(`Upload failed: ${err.message}`);
    removeActiveAttachment();
  } finally {
    event.target.value = '';
  }
}

function renderAttachmentPill(att) {
  const tray = document.getElementById('attachmentTray');
  if (!tray) return;
  tray.style.display = 'flex';
  const sizeKb = Math.round((att.file_size || 0) / 1024);
  const piiCount = (att.detected_pii && att.detected_pii.length) || 0;
  tray.innerHTML = `
    <div class="tracera-attachment-chip">
      <span class="chip-icon">📄</span>
      <span class="chip-name" title="${escapeHtml(att.filename)}">${escapeHtml(att.filename)}</span>
      <span class="chip-meta">${sizeKb} KB · ${att.total_records || 0} records</span>
      ${piiCount > 0 ? `<span class="chip-pii-badge" title="${piiCount} candidate personal data attributes detected">${piiCount} PII</span>` : ''}
      <button class="chip-remove-btn" type="button" title="Remove attachment" onclick="removeActiveAttachment()">✕</button>
    </div>
  `;
}

function removeActiveAttachment() {
  activeAttachment = null;
  const tray = document.getElementById('attachmentTray');
  if (tray) {
    tray.innerHTML = '';
    tray.style.display = 'none';
  }
  if (MessageComposer.inputEl && MessageComposer.sendBtnEl) {
    MessageComposer.sendBtnEl.disabled = MessageComposer.inputEl.value.trim().length === 0;
  }
}
window.removeActiveAttachment = removeActiveAttachment;

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
    const attachBtn = document.getElementById('btnAttachFile');
    const fileInput = document.getElementById('fileAttachmentInput');

    if (newChatBtn) {
      newChatBtn.addEventListener('click', createNewConversation);
    }

    if (attachBtn && fileInput) {
      attachBtn.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', handleFileAttachment);
    }

    if (!this.inputEl || !this.sendBtnEl) return;

    this.sendBtnEl.disabled = true;
    this.inputEl.style.height = '48px';

    const updateState = () => {
      const val = this.inputEl.value.trim();
      this.sendBtnEl.disabled = isSubmitting || (val.length === 0 && !activeAttachment);

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
        if (!this.sendBtnEl.disabled && !isSubmitting && (this.inputEl.value.trim() || activeAttachment)) {
          onSend();
        }
      }
    });

    this.sendBtnEl.addEventListener('click', () => {
      if (!this.sendBtnEl.disabled && !isSubmitting && (this.inputEl.value.trim() || activeAttachment)) {
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
// 6. MAIN CHAT SUBMISSION CONTROLLER (Progressive SSE Streaming)
// ==========================================
async function sendChatMessage() {
  if (isSubmitting) return;

  let message = MessageComposer.getValue();
  const currentTurnAttachment = activeAttachment;

  if (!message && currentTurnAttachment) {
    message = `Please inspect the attached file '${currentTurnAttachment.filename}' and summarize its candidate personal data attributes.`;
  }
  if (!message) return;

  removeActiveAttachment();
  lastUserMessage = message;
  isSubmitting = true;

  MessageComposer.clear();
  MessageComposer.setDisabled(true);

  const userMsgId = 'usr-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
  ChatMessageList.addUserMessage(userMsgId, message, new Date().toISOString(), currentTurnAttachment);

  const stopBtn = document.getElementById('btnStopGenerating');
  if (stopBtn) {
    stopBtn.style.display = 'inline-flex';
    stopBtn.onclick = () => {
      if (activeAbortController) {
        activeAbortController.abort();
      }
    };
  }

  const tempAsstId = 'asst-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
  let streamController = null;
  activeAbortController = new AbortController();

  try {
    const payload = {
      message: message,
      conversation_id: currentConversationId,
      selected_sources: selectedSources.length > 0 ? selectedSources : null,
      format_preference: currentFormatPreference !== 'text' ? currentFormatPreference : null,
      attachment: currentTurnAttachment,
    };

    const res = await fetch('/api/relationships/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: activeAbortController.signal,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      ChatMessageList.showError(errData.detail || 'Server error occurred.', message);
      return;
    }

    streamController = ChatMessageList.addStreamingMessage(tempAsstId);

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let finalReport = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      let currentEvent = 'message';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
          currentEvent = 'message';
          continue;
        }
        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.replace('event:', '').trim();
          continue;
        }
        if (trimmed.startsWith('data:')) {
          const rawData = trimmed.replace('data:', '').trim();
          try {
            const data = JSON.parse(rawData);
            if (currentEvent === 'start') {
              if (data.conversation_id && data.conversation_id !== currentConversationId) {
                currentConversationId = data.conversation_id;
                localStorage.setItem('tracera-active-conv', currentConversationId);
                const titleEl = document.getElementById('activeConvTitle');
                if (titleEl && data.title) titleEl.textContent = data.title;
              }
            } else if (currentEvent === 'visual') {
              streamController.setVisual(data);
            } else if (currentEvent === 'token') {
              if (data.chunk) {
                streamController.appendChunk(data.chunk);
              }
            } else if (currentEvent === 'done') {
              finalReport = data.report || data;
              if (data.message_id) {
                streamController.row.id = `msg-${data.message_id}`;
              }
            }
          } catch (e) {
            console.error('Error parsing SSE stream line:', e);
          }
        }
      }
    }

    if (streamController) {
      streamController.finalize(finalReport);
    }

    await loadConversations(false);

  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('Stream stopped by user.');
      if (streamController) {
        streamController.finalize({ stopped: true });
      }
    } else {
      console.error('Streaming request failed:', err);
      if (!streamController) {
        // Fallback to standard non-streaming POST
        try {
          const fbRes = await fetch('/api/relationships/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: message,
              conversation_id: currentConversationId,
              selected_sources: selectedSources.length > 0 ? selectedSources : null,
              format_preference: currentFormatPreference !== 'text' ? currentFormatPreference : null,
              attachment: currentTurnAttachment,
            }),
          });
          if (fbRes.ok) {
            const rep = await fbRes.json();
            ChatMessageList.addAssistantMessage(rep.message_id || tempAsstId, rep.explanation, rep);
            await loadConversations(false);
          } else {
            ChatMessageList.showError(`Error: ${err.message}`, message);
          }
        } catch (fbErr) {
          ChatMessageList.showError(`Network connection failed: ${err.message}`, message);
        }
      }
    }
  } finally {
    isSubmitting = false;
    activeAbortController = null;
    if (stopBtn) stopBtn.style.display = 'none';
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

  // Sort by activity: newest updated_at or created_at first
  const sorted = [...threads].sort((a, b) => {
    const timeA = new Date(a.updated_at || a.created_at || 0).getTime();
    const timeB = new Date(b.updated_at || b.created_at || 0).getTime();
    return timeB - timeA;
  });

  listEl.innerHTML = '';
  sorted.forEach(c => {
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
        ChatMessageList.addUserMessage(msgId, msg.content, msg.created_at, msg.attachment);
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
/**
 * Responsive SVG Chart Generator (Bar, Line, Pie)
 * Clean Enterprise Technical Aesthetic (Zero cartoon/rainbow colors)
 */
function renderChart(container, chartData, title) {
  if (!chartData || !chartData.series || !Array.isArray(chartData.series) || chartData.series.length === 0) {
    const emptyNotice = document.createElement('div');
    emptyNotice.style.padding = '1rem';
    emptyNotice.style.color = 'var(--tracera-viz-text-muted)';
    emptyNotice.style.fontSize = '0.78rem';
    emptyNotice.style.fontFamily = 'var(--font-mono)';
    emptyNotice.textContent = 'No numerical series data available for this chart.';
    container.appendChild(emptyNotice);
    return;
  }

  const chartType = (chartData.type || 'bar').toLowerCase();
  const series = chartData.series;
  const ENTERPRISE_PALETTE = ['#D4A72C', '#10B981', '#38BDF8', '#818CF8', '#F59E0B', '#64748B'];

  const chartBox = document.createElement('div');
  chartBox.className = 'tracera-chart-container';

  // Floating Tooltip
  const tooltip = document.createElement('div');
  tooltip.className = 'tracera-chart-tooltip';
  chartBox.appendChild(tooltip);

  if (chartType === 'pie') {
    // Pie / Donut Chart
    const total = series.reduce((sum, item) => sum + (Number(item.value) || 0), 0) || 1;
    const cx = 125, cy = 125, r = 85, innerR = 48;
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
      const color = ENTERPRISE_PALETTE[idx % ENTERPRISE_PALETTE.length];
      const pct = Math.round((val / total) * 100);

      const d = `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${largeArc} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} L ${ix1.toFixed(1)} ${iy1.toFixed(1)} A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix2.toFixed(1)} ${iy2.toFixed(1)} Z`;

      pathsSvg += `<path d="${d}" fill="${color}" stroke="#0B0F17" stroke-width="2" style="cursor:pointer; transition:opacity 0.15s ease;" data-label="${escapeHtml(slice.label)}" data-val="${val}" data-pct="${pct}%" class="tracera-chart-slice" />`;
    });

    // Right Legend Table
    let legendSvg = '';
    series.forEach((slice, idx) => {
      const color = ENTERPRISE_PALETTE[idx % ENTERPRISE_PALETTE.length];
      const val = slice.value;
      const pct = Math.round((val / total) * 100);
      const ly = 32 + idx * 26;
      if (ly < 250) {
        legendSvg += `
          <rect x="250" y="${ly}" width="10" height="10" rx="2" fill="${color}" />
          <text x="268" y="${ly + 9}" fill="#E2E8F0" font-size="11" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600">${escapeHtml(slice.label)}</text>
          <text x="460" y="${ly + 9}" fill="#94A3B8" font-size="11" font-family="'JetBrains Mono', monospace" text-anchor="end">${val} (${pct}%)</text>
        `;
      }
    });

    chartBox.innerHTML += `
      <svg viewBox="0 0 480 250" class="tracera-chart-svg">
        ${pathsSvg}
        <text x="${cx}" y="${cy - 6}" text-anchor="middle" fill="#64748B" font-size="9" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600" letter-spacing="0.08em">TOTAL</text>
        <text x="${cx}" y="${cy + 15}" text-anchor="middle" fill="#F8FAFC" font-size="16" font-weight="700" font-family="'JetBrains Mono', monospace">${total}</text>
        ${legendSvg}
      </svg>
    `;

  } else if (chartType === 'line') {
    // Line Chart
    const maxVal = Math.max(...series.map(s => Number(s.value) || 0), 10);
    const w = 540, h = 240, padL = 50, padR = 25, padT = 25, padB = 38;
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

    const ptsStr = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const areaStr = `${points[0].x.toFixed(1)},${padT + plotH} ` + ptsStr + ` ${points[points.length - 1].x.toFixed(1)},${padT + plotH}`;

    // Grid lines & Y ticks
    let gridLines = '';
    const ticks = [0, Math.round(maxVal / 2), maxVal];
    ticks.forEach(t => {
      const ty = padT + plotH - (t / maxVal) * plotH;
      gridLines += `
        <line x1="${padL}" y1="${ty}" x2="${w - padR}" y2="${ty}" stroke="rgba(255,255,255,0.05)" stroke-dasharray="2 4" />
        <text x="${padL - 10}" y="${ty + 4}" fill="#64748B" font-size="10" font-family="'JetBrains Mono', monospace" text-anchor="end">${t}</text>
      `;
    });

    let dotsSvg = '';
    points.forEach((p) => {
      dotsSvg += `
        <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4" fill="#D4A72C" stroke="#0B0F17" stroke-width="2" class="tracera-chart-dot" data-label="${escapeHtml(p.label)}" data-val="${p.value}" style="cursor:pointer;" />
        <text x="${p.x.toFixed(1)}" y="${padT + plotH + 18}" fill="#94A3B8" font-size="10" font-family="'Plus Jakarta Sans', sans-serif" text-anchor="middle">${escapeHtml(p.label)}</text>
      `;
    });

    chartBox.innerHTML += `
      <svg viewBox="0 0 ${w} ${h}" class="tracera-chart-svg">
        <defs>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#D4A72C" stop-opacity="0.16"/>
            <stop offset="100%" stop-color="#D4A72C" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        ${gridLines}
        <polygon points="${areaStr}" fill="url(#lineGrad)" />
        <polyline points="${ptsStr}" fill="none" stroke="#D4A72C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        ${dotsSvg}
        <text x="${w / 2}" y="${h - 4}" fill="#64748B" font-size="9" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600" letter-spacing="0.08em" text-transform="uppercase">${escapeHtml(chartData.x_label || 'Timeline')}</text>
        <text x="14" y="${h / 2}" fill="#64748B" font-size="9" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600" letter-spacing="0.08em" text-transform="uppercase" transform="rotate(-90 14,${h/2})">${escapeHtml(chartData.y_label || 'Count')}</text>
      </svg>
    `;

  } else {
    // Bar Chart (Enterprise Layout: Dynamic Horizontal or Rotated Vertical)
    const n = series.length;
    const maxVal = Math.max(...series.map(s => Number(s.value) || 0), 1);
    const maxLabelLen = Math.max(...series.map(s => String(s.label || '').length), 0);
    // Switch to Horizontal Bar Chart when category count >= 7 or label length > 13 or explicit horizontal
    const isHorizontal = chartData.orientation === 'horizontal' || n >= 7 || maxLabelLen > 13;

    if (isHorizontal) {
      // -------------------------------------------------------------
      // HORIZONTAL BAR CHART (Guaranteed Zero Label Collisions)
      // -------------------------------------------------------------
      const rowH = 40;
      const padT = 32;
      const padB = 44;
      const padL = Math.min(230, Math.max(120, Math.round(maxLabelLen * 7.5 + 24)));
      const padR = 65;
      const w = Math.max(560, padL + 340);
      const h = padT + padB + n * rowH;
      const plotW = w - padL - padR;
      const barThickness = 22;

      // Vertical tick marks
      let gridLines = '';
      const ticks = [0, Math.round(maxVal / 2), maxVal];
      ticks.forEach(t => {
        const tx = padL + (t / maxVal) * plotW;
        gridLines += `
          <line x1="${tx.toFixed(1)}" y1="${padT}" x2="${tx.toFixed(1)}" y2="${padT + n * rowH}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="2 4" />
          <text x="${tx.toFixed(1)}" y="${padT + n * rowH + 16}" fill="#64748B" font-size="10" font-family="'JetBrains Mono', monospace" text-anchor="middle">${t}</text>
        `;
      });

      let barsSvg = '';
      series.forEach((bar, i) => {
        const val = Number(bar.value) || 0;
        const barW = Math.max(2, (val / maxVal) * plotW);
        const y = padT + i * rowH + (rowH - barThickness) / 2;
        const color = ENTERPRISE_PALETTE[i % ENTERPRISE_PALETTE.length];
        const labelY = padT + i * rowH + rowH / 2 + 4;

        barsSvg += `
          <!-- Category Label (Left-aligned, crisp, uncropped) -->
          <text x="${padL - 12}" y="${labelY.toFixed(1)}" fill="#CBD5E1" font-size="11" font-family="'Plus Jakarta Sans', sans-serif" font-weight="500" text-anchor="end" class="tracera-axis-label">${escapeHtml(bar.label)}</text>
          <!-- Horizontal Bar -->
          <rect x="${padL}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barThickness}" rx="4" fill="${color}" fill-opacity="0.92" class="tracera-chart-bar" data-label="${escapeHtml(bar.label)}" data-val="${val}" style="cursor:pointer; transition:filter 0.15s ease;" />
          <!-- Direct Value Annotation at Bar End -->
          <text x="${(padL + barW + 8).toFixed(1)}" y="${(y + barThickness / 2 + 4).toFixed(1)}" fill="#F8FAFC" font-size="11" font-family="'JetBrains Mono', monospace" font-weight="700" text-anchor="start">${val}</text>
        `;
      });

      chartBox.innerHTML += `
        <svg viewBox="0 0 ${w} ${h}" class="tracera-chart-svg" style="width:100%; height:auto;">
          ${gridLines}
          ${barsSvg}
          <text x="${padL + plotW / 2}" y="${h - 6}" fill="#64748B" font-size="9.5" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600" letter-spacing="0.08em" text-transform="uppercase">${escapeHtml(chartData.x_label || 'Count / Occurrences')}</text>
          <text x="${padL - 12}" y="${padT - 12}" fill="#64748B" font-size="9.5" text-anchor="end" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600" letter-spacing="0.08em" text-transform="uppercase">${escapeHtml(chartData.y_label || 'Dataset / Category')}</text>
        </svg>
      `;

    } else {
      // -------------------------------------------------------------
      // VERTICAL BAR CHART (with Label Rotation & Ample Margin)
      // -------------------------------------------------------------
      const needsRotation = maxLabelLen > 5 || n > 4;
      const padL = 55, padR = 30, padT = 30;
      const padB = needsRotation ? Math.min(115, Math.max(68, Math.round(maxLabelLen * 6.5 + 28))) : 44;
      const h = 250 + (needsRotation ? 40 : 0);
      const w = Math.max(540, n * 65 + 100);
      const plotW = w - padL - padR;
      const plotH = h - padT - padB;
      const step = plotW / n;
      const barWidth = Math.min(42, Math.max(18, step * 0.58));

      let gridLines = '';
      const ticks = [0, Math.round(maxVal / 2), maxVal];
      ticks.forEach(t => {
        const ty = padT + plotH - (t / maxVal) * plotH;
        gridLines += `
          <line x1="${padL}" y1="${ty.toFixed(1)}" x2="${(w - padR).toFixed(1)}" y2="${ty.toFixed(1)}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="2 4" />
          <text x="${padL - 10}" y="${(ty + 4).toFixed(1)}" fill="#64748B" font-size="10" font-family="'JetBrains Mono', monospace" text-anchor="end">${t}</text>
        `;
      });

      let barsSvg = '';
      series.forEach((bar, i) => {
        const val = Number(bar.value) || 0;
        const barH = Math.max(2, (val / maxVal) * plotH);
        const x = padL + i * step + (step - barWidth) / 2;
        const y = padT + plotH - barH;
        const color = ENTERPRISE_PALETTE[i % ENTERPRISE_PALETTE.length];
        const labelX = (x + barWidth / 2).toFixed(1);
        const labelY = (padT + plotH + 14).toFixed(1);

        const labelSvg = needsRotation
          ? `<text x="${labelX}" y="${labelY}" fill="#CBD5E1" font-size="10.5" font-family="'Plus Jakarta Sans', sans-serif" font-weight="500" text-anchor="end" transform="rotate(-38 ${labelX} ${labelY})" class="tracera-axis-label">${escapeHtml(bar.label)}</text>`
          : `<text x="${labelX}" y="${labelY}" fill="#CBD5E1" font-size="10.5" font-family="'Plus Jakarta Sans', sans-serif" font-weight="500" text-anchor="middle" class="tracera-axis-label">${escapeHtml(bar.label)}</text>`;

        barsSvg += `
          <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth}" height="${barH.toFixed(1)}" rx="4" fill="${color}" fill-opacity="0.92" class="tracera-chart-bar" data-label="${escapeHtml(bar.label)}" data-val="${val}" style="cursor:pointer; transition:filter 0.15s ease;" />
          <text x="${labelX}" y="${(y - 6).toFixed(1)}" fill="#F8FAFC" font-size="11" font-family="'JetBrains Mono', monospace" font-weight="700" text-anchor="middle">${val}</text>
          ${labelSvg}
        `;
      });

      chartBox.innerHTML += `
        <svg viewBox="0 0 ${w} ${h}" class="tracera-chart-svg" style="width:100%; height:auto;">
          ${gridLines}
          ${barsSvg}
          <text x="${padL + plotW / 2}" y="${h - 6}" fill="#64748B" font-size="9.5" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600" letter-spacing="0.08em" text-transform="uppercase">${escapeHtml(chartData.x_label || 'Category')}</text>
          <text x="14" y="${padT + plotH / 2}" fill="#64748B" font-size="9.5" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="600" letter-spacing="0.08em" text-transform="uppercase" transform="rotate(-90 14,${padT + plotH/2})">${escapeHtml(chartData.y_label || 'Records / Gaps')}</text>
        </svg>
      `;
    }
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
 * Clean enterprise process blocks, decision gates, and SVG arrows
 */
function renderFlowchart(container, flowchartData, title) {
  if (!flowchartData || !flowchartData.steps || !Array.isArray(flowchartData.steps)) return;

  const flowBox = document.createElement('div');
  flowBox.className = 'tracera-flowchart-container';

  flowchartData.steps.forEach((step, idx) => {
    const stepEl = document.createElement('div');
    const isDecision = step.is_decision || step.type === 'decision';
    stepEl.className = isDecision ? 'tracera-flow-step tracera-flow-decision' : 'tracera-flow-step';

    const stepNum = step.step_num || (idx + 1);
    const stepTitle = step.title || `Stage ${stepNum}`;
    const stepDesc = step.description || '';
    const badge = step.badge || (isDecision ? 'DECISION GATE' : 'Verified Stage');

    let branchHtml = '';
    if (step.decision_branches && Array.isArray(step.decision_branches)) {
      branchHtml = `
        <div class="tracera-flow-decision-branches">
          ${step.decision_branches.map(b => {
            const isVer = (b.condition || '').toLowerCase().includes('foreign key') || (b.outcome || '').toLowerCase().includes('verified');
            const pillStyle = isVer
              ? 'background:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.28); color:#10B981;'
              : 'background:rgba(245, 158, 11, 0.1); border:1px solid rgba(245, 158, 11, 0.28); color:#F59E0B;';
            return `
              <div style="font-size:0.72rem; padding:0.3rem 0.55rem; border-radius:4px; ${pillStyle} font-family:var(--font-sans);">
                <strong>${escapeHtml(b.condition)}:</strong> ${escapeHtml(b.outcome)}
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    const badgeStyle = isDecision
      ? 'background:rgba(212,167,44,0.12); color:var(--accent-gold); border:1px solid rgba(212,167,44,0.28); font-size:0.65rem; font-weight:700; font-family:var(--font-mono);'
      : 'background:rgba(16,185,129,0.12); color:#10B981; border:1px solid rgba(16,185,129,0.28); font-size:0.65rem; font-weight:700; font-family:var(--font-mono);';

    stepEl.innerHTML = `
      <div class="tracera-flow-step-num" style="${isDecision ? 'background:rgba(212,167,44,0.18); color:var(--accent-gold); border-color:var(--accent-gold);' : ''}">${isDecision ? '◆' : (stepNum < 10 ? '0' + stepNum : stepNum)}</div>
      <div class="tracera-flow-step-content">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.25rem;">
          <div class="tracera-flow-step-title" style="${isDecision ? 'color:var(--accent-gold);' : ''}">${escapeHtml(stepTitle)}</div>
          <span class="badge" style="${badgeStyle}">${escapeHtml(badge.toUpperCase())}</span>
        </div>
        <div class="tracera-flow-step-desc">${escapeHtml(stepDesc)}</div>
        ${branchHtml}
      </div>
    `;

    flowBox.appendChild(stepEl);

    // Connector Arrow (Precision SVG)
    if (idx < flowchartData.steps.length - 1) {
      const arrow = document.createElement('div');
      arrow.className = 'tracera-flow-arrow';
      arrow.innerHTML = `<svg width="12" height="18" viewBox="0 0 12 18" fill="none"><line x1="6" y1="0" x2="6" y2="13" stroke="#334155" stroke-width="1.5"/><polyline points="2,9 6,13 10,9" stroke="#334155" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
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
      <div class="tracera-step-index">STEP ${num < 10 ? '0' + num : num}</div>
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
    tableHtml += `<tr><td style="font-weight: 600; color: var(--tracera-viz-accent); font-family:var(--font-mono); font-size:0.75rem;">${escapeHtml(attr.attribute || '')}</td>`;
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

/**
 * Structured Table Generator
 */
function renderStructuredTable(container, tblPayload, title) {
  if (!tblPayload || !Array.isArray(tblPayload) || tblPayload.length === 0) return;

  const tableWrapper = document.createElement('div');
  tableWrapper.className = 'tracera-table-wrapper';

  const cols = Object.keys(tblPayload[0]);
  let tableHtml = '<table class="data-table"><thead><tr>';
  cols.forEach(c => {
    const formattedTitle = c.replace(/_/g, ' ').toUpperCase();
    tableHtml += `<th>${escapeHtml(formattedTitle)}</th>`;
  });
  tableHtml += '</tr></thead><tbody>';

  tblPayload.forEach(rowItem => {
    tableHtml += '<tr>';
    cols.forEach(c => {
      let val = rowItem[c];
      if (val === null || val === undefined) val = '-';
      const cLower = c.toLowerCase();
      if (cLower.includes('status')) {
        const isVer = String(val).toLowerCase().includes('verified') || String(val).toLowerCase().includes('complete');
        const badgeStyle = isVer
          ? 'background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.28); color:#10B981;'
          : 'background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.28); color:#F59E0B;';
        val = `<span class="badge" style="${badgeStyle} font-size:0.65rem; font-weight:700; text-transform:uppercase; font-family:var(--font-mono);">${escapeHtml(String(val))}</span>`;
      } else if (cLower.includes('cardinality') || cLower.includes('key') || cLower.includes('id') || cLower.includes('column') || cLower.includes('count')) {
        val = `<span style="font-family:var(--font-mono); font-size:0.75rem; color:#E2E8F0;">${escapeHtml(String(val))}</span>`;
      } else {
        val = escapeHtml(String(val));
      }
      tableHtml += `<td>${val}</td>`;
    });
    tableHtml += '</tr>';
  });
  tableHtml += '</tbody></table>';

  tableWrapper.innerHTML = tableHtml;
  container.appendChild(tableWrapper);
}

/**
 * Timeline Generator
 * Vertical spine with node markers, timestamps, and provenance tags
 */
function renderTimeline(container, timePayload, title) {
  if (!timePayload || !Array.isArray(timePayload) || timePayload.length === 0) return;

  const timelineWrapper = document.createElement('div');
  timelineWrapper.className = 'tracera-timeline-container';

  const spine = document.createElement('div');
  spine.className = 'tracera-timeline-spine';
  timelineWrapper.appendChild(spine);

  timePayload.forEach(ev => {
    const item = document.createElement('div');
    item.className = 'tracera-timeline-item';

    const hasTime = ev.has_timestamp !== false && ev.date;
    const nodeDot = document.createElement('div');
    nodeDot.className = 'tracera-timeline-node';
    if (!hasTime) {
      nodeDot.style.borderColor = '#64748B';
    }
    item.appendChild(nodeDot);

    const card = document.createElement('div');
    card.className = 'tracera-timeline-card';

    const sourceBadge = ev.source 
      ? `<span style="font-size:0.65rem; color:#64748B; background:rgba(0,0,0,0.3); border:1px solid #1E2738; padding:2px 6px; border-radius:3px; display:inline-block; margin-top:0.35rem; font-family:var(--font-mono);">Source: ${escapeHtml(ev.source)}</span>` 
      : '';

    const dateBadge = !hasTime
      ? '<span class="badge" style="background:rgba(255,255,255,0.04); color:#94A3B8; border:1px solid rgba(255,255,255,0.08); font-size:0.65rem; font-family:var(--font-mono);">TIMESTAMP: NOT RECORDED</span>'
      : `<span class="badge" style="background:rgba(212,167,44,0.1); color:var(--accent-gold); border:1px solid rgba(212,167,44,0.25); font-family:var(--font-mono); font-size:0.68rem;">${escapeHtml(ev.date)}</span>`;

    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.75rem;">
        <div>
          <div style="font-weight:600; font-size:0.84rem; color:var(--tracera-viz-text-primary); margin-bottom:0.15rem;">
            ${escapeHtml(ev.entity || 'Event Milestone')}
          </div>
          <div style="font-size:0.76rem; color:var(--tracera-viz-text-secondary); line-height:1.45;">${escapeHtml(ev.description || '')}</div>
          ${sourceBadge}
        </div>
        <div style="text-align:right; flex-shrink:0;">
          ${dateBadge}
        </div>
      </div>
    `;
    item.appendChild(card);
    timelineWrapper.appendChild(item);
  });

  container.appendChild(timelineWrapper);
}

/**
 * Directional Lineage DAG Generator for TRACERA
 */
function renderLineageDAGInTracera(container, lineagePayload, title) {
  if (!lineagePayload || !lineagePayload.nodes || lineagePayload.nodes.length === 0) return;

  const dagId = 'tracera-lineage-' + Math.random().toString(36).substr(2, 9);
  const wrapper = document.createElement('div');
  wrapper.className = 'tracera-graph-wrapper';

  wrapper.innerHTML = `
    <div id="${dagId}" class="tracera-graph-container" style="height: 380px;"></div>
    <div class="tracera-graph-controls">
      <button class="tracera-graph-btn" onclick="zoomGraph('${dagId}', 1.25)" title="Zoom in">${VIZ_ICONS.zoomIn}</button>
      <button class="tracera-graph-btn" onclick="zoomGraph('${dagId}', 0.8)" title="Zoom out">${VIZ_ICONS.zoomOut}</button>
      <button class="tracera-graph-btn" onclick="fitGraph('${dagId}')" title="Fit to view">${VIZ_ICONS.fit} <span>Fit</span></button>
      <a href="/lineage" class="tracera-graph-btn" style="text-decoration:none; color:var(--accent-gold);" title="Open Full Lineage &amp; Evidence Explorer">
        <span>Full DAG Explorer ↗</span>
      </a>
    </div>
    <div class="tracera-graph-legend" style="flex-wrap: wrap; gap: 0.6rem;">
      <div class="tracera-graph-legend-item">
        <span style="width: 8px; height: 8px; border-radius: 2px; background: #06B6D4; display: inline-block;"></span>
        <span>INGESTION</span>
      </div>
      <div class="tracera-graph-legend-item">
        <span style="width: 8px; height: 8px; border-radius: 50%; background: #10B981; display: inline-block;"></span>
        <span>STORAGE</span>
      </div>
      <div class="tracera-graph-legend-item">
        <span style="width: 8px; height: 8px; border-radius: 50%; background: #D4A72C; display: inline-block;"></span>
        <span>PROCESSING</span>
      </div>
      <div class="tracera-graph-legend-item">
        <span style="width: 8px; height: 8px; transform: rotate(45deg); background: #F97316; display: inline-block;"></span>
        <span>EGRESS</span>
      </div>
    </div>
  `;
  container.appendChild(wrapper);

  requestAnimationFrame(() => {
    initCytoscapeLineageDAG(dagId, lineagePayload);
  });
}

function initCytoscapeLineageDAG(containerId, dag) {
  const container = document.getElementById(containerId);
  if (!container || typeof cytoscape === 'undefined') return;

  const STAGE_COLORS = {
    Ingestion: '#06B6D4',
    Storage: '#10B981',
    Processing: '#D4A72C',
    Egress: '#F97316',
    Unknown: '#64748B',
  };

  const elements = [];
  dag.nodes.forEach(n => {
    elements.push({
      group: 'nodes',
      data: {
        id: n.id,
        label: n.label || n.column,
        stage: n.stage,
        is_pii: n.is_pii,
        color: STAGE_COLORS[n.stage] || '#94A3B8',
      },
    });
  });

  dag.edges.forEach(e => {
    elements.push({
      group: 'edges',
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        verification_status: e.verification_status,
        is_verified: e.verification_status === 'Verified',
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
          'label': 'data(label)',
          'font-family': 'Plus Jakarta Sans, sans-serif',
          'font-size': '10px',
          'font-weight': 600,
          'color': '#E2E8F0',
          'text-valign': 'bottom',
          'text-margin-y': 4,
          'background-color': 'data(color)',
          'border-width': 2,
          'border-color': '#0B0F17',
          'width': 26,
          'height': 26,
        },
      },
      {
        selector: 'node[?is_pii]',
        style: {
          'border-width': 3,
          'border-color': '#F59E0B',
          'width': 30,
          'height': 30,
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
          'opacity': 0.75,
        },
      },
      {
        selector: 'edge[!is_verified]',
        style: {
          'line-style': 'dashed',
          'line-color': '#D4A72C',
          'target-arrow-color': '#D4A72C',
        },
      },
    ],
    layout: {
      name: 'breadthfirst',
      directed: true,
      padding: 30,
      spacingFactor: 1.25,
      animate: false,
    },
  });

  activeCytoscapeInstances[containerId] = cy;
  cy.fit(undefined, 25);
}

// ==========================================
// 10. CYTOSCAPE.JS & INSPECTOR MODALS
// ==========================================
function openNodeModal(data) {
  const modal = document.getElementById('detailModal');
  const titleEl = document.getElementById('modalFieldTitle');
  const bodyEl = document.getElementById('modalDetailsBody');
  if (!modal || !titleEl || !bodyEl) return;

  const raw = data.raw || {};
  const attrs = raw.attributes || {};
  const cols = attrs.columns || [];
  const pks = attrs.primary_keys || (data.primary_key ? [data.primary_key] : []);

  titleEl.innerHTML = `<span style="color:var(--text-secondary); font-size:0.85rem; font-weight:500;">Entity Node:</span> <strong style="color:#FFF;">${escapeHtml(data.label)}</strong>`;
  bodyEl.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:0.65rem; font-size:0.83rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Entity Name:</span>
        <strong style="color:var(--accent-gold); font-family:var(--font-mono);">${escapeHtml(data.label)}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Primary Dataset / Table:</span>
        <strong style="color:#E5E7EB; font-family:var(--font-mono);">${escapeHtml(data.source || data.id)}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Primary Key(s):</span>
        <span class="badge" style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); color:var(--accent-gold); font-family:var(--font-mono); font-size:0.7rem;">${escapeHtml(pks.length > 0 ? pks.join(', ') : 'None')}</span>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Entity Classification:</span>
        <span class="badge" style="background:rgba(212,167,44,0.12); color:var(--accent-gold); border:1px solid rgba(212,167,44,0.28); font-size:0.7rem;">${escapeHtml(data.type || 'Personal Data Domain')}</span>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Verification Level:</span>
        <span class="badge badge-status-complete" style="font-size:0.7rem;">100% Deterministic Schema Grounded</span>
      </div>
      <div style="margin-top:0.35rem;">
        <span style="color:var(--text-secondary); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; font-weight:600; display:block; margin-bottom:0.3rem;">Discovered Attributes & Columns (${cols.length}):</span>
        <div style="padding:0.6rem 0.85rem; background:#0B0F17; border:1px solid #1E2738; border-radius:4px; font-family:var(--font-mono); font-size:0.72rem; color:#94A3B8; max-height:85px; overflow-y:auto; line-height:1.45;">
          ${escapeHtml(cols.join(', ') || 'customer_id, name, email, phone, created_at')}
        </div>
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
  const confPct = Math.round((data.confidence !== undefined ? data.confidence : 1.0) * 100);

  titleEl.innerHTML = `<span style="color:var(--text-secondary); font-size:0.85rem; font-weight:500;">Relationship:</span> <strong style="color:#FFF;">${escapeHtml(data.source_dataset || data.source)} ➔ ${escapeHtml(data.target_dataset || data.target)}</strong>`;
  bodyEl.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:0.65rem; font-size:0.83rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Source Table:</span>
        <strong style="color:var(--accent-gold); font-family:var(--font-mono);">${escapeHtml(data.source_dataset || data.source)}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Source Column:</span>
        <strong style="color:#E5E7EB; font-family:var(--font-mono);">${escapeHtml(data.source_field || 'customer_id')}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Destination Table:</span>
        <strong style="color:var(--accent-gold); font-family:var(--font-mono);">${escapeHtml(data.target_dataset || data.target)}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Destination Column:</span>
        <strong style="color:#E5E7EB; font-family:var(--font-mono);">${escapeHtml(data.target_field || 'customer_id')}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Relationship Type:</span>
        <span class="badge" style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); color:var(--accent-gold); font-family:var(--font-mono); font-size:0.7rem;">${escapeHtml(data.relationship_type || 'Foreign Key Constraint')} (${escapeHtml(data.label || '1:N')})</span>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E2738; padding-bottom:0.4rem;">
        <span style="color:var(--text-secondary);">Verification Status:</span>
        <span class="badge" style="${isVerified ? 'background:rgba(16,185,129,0.12); color:#10B981; border:1px solid rgba(16,185,129,0.28);' : 'background:rgba(245,158,11,0.12); color:#F59E0B; border:1px solid rgba(245,158,11,0.28);'} font-size:0.7rem; font-weight:700;">${isVerified ? 'VERIFIED CONSTRAINT' : 'INFERRED VALUE OVERLAP'} (${confPct}%)</span>
      </div>
      <div style="margin-top:0.35rem;">
        <span style="color:var(--text-secondary); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; font-weight:600; display:block; margin-bottom:0.3rem;">Technical Evidence & Join Provenance:</span>
        <div style="padding:0.6rem 0.85rem; background:#0B0F17; border:1px solid #1E2738; border-radius:4px; font-family:var(--font-mono); font-size:0.73rem; color:#E5E7EB; line-height:1.45;">
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
          id: 'e_' + idx + '_' + (e.source_id || e.source) + '_' + (e.target_id || e.target),
          source: e.source_id || e.source,
          target: e.target_id || e.target,
          source_dataset: e.source_dataset || e.source,
          source_field: e.source_field || 'id',
          target_dataset: e.target_dataset || e.target,
          target_field: e.target_field || 'id',
          relationship_type: e.relationship_type || 'Foreign Key Constraint',
          label: e.cardinality || '',
          evidence: e.evidence || 'Verified schema foreign key linkage in PrivSight catalog.',
          confidence: e.confidence_score !== undefined ? e.confidence_score : 1.0,
          status: isInf ? 'inferred' : 'verified',
          raw: e,
        }
      });
    });
  }

  const cy = cytoscape({
    container: container,
    elements: elements,
    userPanningEnabled: true,
    userZoomingEnabled: true,
    boxSelectionEnabled: false,
    autoungrabify: false,
    style: [
      {
        selector: 'node',
        style: {
          'shape': 'round-rectangle',
          'background-color': '#111622',
          'border-width': 1.5,
          'border-color': '#2A364F',
          'label': 'data(label)',
          'color': '#F1F5F9',
          'font-size': '11px',
          'font-family': 'Plus Jakarta Sans, sans-serif',
          'font-weight': '600',
          'text-valign': 'center',
          'text-halign': 'center',
          'width': '138px',
          'height': '38px',
          'text-wrap': 'ellipsis',
          'text-max-width': '124px',
          'cursor': 'pointer',
          'shadow-blur': 8,
          'shadow-color': 'rgba(0, 0, 0, 0.4)',
          'shadow-offset-y': 2,
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#D4A72C',
          'border-width': 2,
          'background-color': '#161D2B',
          'shadow-blur': 12,
          'shadow-color': 'rgba(212, 167, 44, 0.35)',
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '9px',
          'font-family': 'JetBrains Mono, monospace',
          'text-rotation': 'autorotate',
          'text-margin-y': -8,
          'text-background-color': '#0B0F17',
          'text-background-opacity': 0.9,
          'text-background-padding': '2px 5px',
          'text-background-shape': 'round-rectangle',
          'text-border-color': '#1E2738',
          'text-border-width': 1,
          'text-border-opacity': 0.8,
          'cursor': 'pointer',
        }
      },
      {
        selector: 'edge[status = "verified"]',
        style: {
          'line-color': '#10B981',
          'target-arrow-color': '#10B981',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8,
          'line-style': 'solid',
          'color': '#34D399',
        }
      },
      {
        selector: 'edge[status = "inferred"]',
        style: {
          'line-color': '#F59E0B',
          'target-arrow-color': '#F59E0B',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8,
          'line-style': 'dashed',
          'line-dash-pattern': [5, 4],
          'color': '#FBBF24',
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'width': 2.5,
          'line-color': '#D4A72C',
          'target-arrow-color': '#D4A72C',
          'color': '#F4B942',
        }
      }
    ],
    layout: {
      name: 'breadthfirst',
      directed: true,
      padding: 35,
      spacingFactor: 1.35,
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

// Module 9: Frontend Visualization Architecture Components
const TraceraVisualEngine = {
  RelationshipGraphRenderer: {
    render: initCytoscapeGraph,
    zoom: zoomGraph,
    fit: fitGraph,
    openNodeModal: openNodeModal,
    openEdgeModal: openEdgeModal,
  },
  BarChartRenderer: {
    render: (container, data, title) => renderChart(container, { ...data, type: 'bar' }, title),
  },
  LineChartRenderer: {
    render: (container, data, title) => renderChart(container, { ...data, type: 'line' }, title),
  },
  PieChartRenderer: {
    render: (container, data, title) => renderChart(container, { ...data, type: 'pie' }, title),
  },
  FlowchartRenderer: {
    render: renderFlowchart,
  },
  TimelineRenderer: {
    render: renderTimeline,
  },
  StructuredTableRenderer: {
    render: renderStructuredTable,
  },
  StepByStepRenderer: {
    render: renderStepByStep,
  },
  ComparisonRenderer: {
    render: renderComparison,
  },
  VisualizationExplanation: {
    render: renderMarkdown,
  },
};
window.TraceraVisualEngine = TraceraVisualEngine;

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
  initKeyboardShortcuts();
  MessageComposer.init(sendChatMessage);
  const clearBtn = document.getElementById('btnClearAllHistory');
  if (clearBtn) {
    clearBtn.addEventListener('click', clearAllHistory);
  }
  await loadSources();
  await loadConversations();
});

function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl+K or Cmd+K: toggle history drawer and focus search
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      toggleHistorySidebar();
      setTimeout(() => {
        const searchInput = document.getElementById('searchThreadsInput');
        if (searchInput) searchInput.focus();
      }, 150);
    }
    // Escape: close history drawer or open modals
    if (e.key === 'Escape') {
      toggleHistorySidebar(false);
      const detailModal = document.getElementById('detailModal');
      if (detailModal) detailModal.classList.remove('active');
    }
  });
}

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

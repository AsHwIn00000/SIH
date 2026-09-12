/**
 * zero_egress.js — Zero-Egress Network Monitor + Multi-Document Cross-Reference
 *
 * Zero-Egress: Connects to /api/network-stats/stream (SSE) and displays a
 * live widget on the welcome screen showing bytes sent/received since the
 * app started. The key signal for the pitch: outbound bytes stay at 0 (or
 * near-zero) while the AI processes documents — proving no data leaves the machine.
 *
 * Multi-Doc: UI panel that lets users pick multiple uploaded attachments and
 * send them all to /api/multi-doc/analyze for cross-reference Q&A.
 */

// ─── Zero-Egress Monitor ──────────────────────────────────────────────────────

let _egressEventSource = null;
let _egressWidget = null;

function _createEgressWidget() {
  const w = document.createElement('div');
  w.id = 'egress-monitor';
  w.setAttribute('aria-label', 'Zero-Egress Network Monitor');
  w.innerHTML = `
    <div class="egress-header">
      <span class="egress-dot" id="egress-dot"></span>
      <span class="egress-title">Data Egress Monitor</span>
      <span class="egress-badge" id="egress-badge">LIVE</span>
    </div>
    <div class="egress-stats">
      <div class="egress-stat">
        <div class="egress-stat-label">Outbound (Sent)</div>
        <div class="egress-stat-value" id="egress-sent">— B</div>
        <div class="egress-stat-sub" id="egress-sent-delta"></div>
      </div>
      <div class="egress-divider"></div>
      <div class="egress-stat">
        <div class="egress-stat-label">Inbound (Received)</div>
        <div class="egress-stat-value" id="egress-recv">— B</div>
        <div class="egress-stat-sub" id="egress-recv-delta"></div>
      </div>
    </div>
    <div class="egress-status" id="egress-status">
      <span id="egress-status-icon">✅</span>
      <span id="egress-status-text">Zero Data Egress — All AI runs locally</span>
    </div>
    <div class="egress-proof">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.5;flex-shrink:0"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      <span>Verifiable air-gap — no cloud APIs, no telemetry, no data leaves this machine</span>
    </div>
  `;
  return w;
}

function _updateEgressWidget(data) {
  const sentEl = document.getElementById('egress-sent');
  const recvEl = document.getElementById('egress-recv');
  const sentDelta = document.getElementById('egress-sent-delta');
  const recvDelta = document.getElementById('egress-recv-delta');
  const statusIcon = document.getElementById('egress-status-icon');
  const statusText = document.getElementById('egress-status-text');
  const dot = document.getElementById('egress-dot');

  if (sentEl) sentEl.textContent = data.sent_fmt || '0 B';
  if (recvEl) recvEl.textContent = data.recv_fmt || '0 B';
  if (sentDelta && data.sent_delta > 0) sentDelta.textContent = `+${_fmtBytes(data.sent_delta)}/s`;
  else if (sentDelta) sentDelta.textContent = '';
  if (recvDelta && data.recv_delta > 0) recvDelta.textContent = `+${_fmtBytes(data.recv_delta)}/s`;
  else if (recvDelta) recvDelta.textContent = '';

  if (dot) dot.className = 'egress-dot egress-dot--live';

  if (data.egress_zero) {
    if (statusIcon) statusIcon.textContent = '✅';
    if (statusText) statusText.textContent = 'Zero Data Egress — All AI runs locally';
    if (statusText) statusText.style.color = 'var(--color-success, #10b981)';
  } else {
    if (statusIcon) statusIcon.textContent = '⚠️';
    if (statusText) statusText.textContent = `Network activity detected (${data.sent_fmt} sent)`;
    if (statusText) statusText.style.color = 'var(--color-warn, #f59e0b)';
  }
}

function _fmtBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function startEgressMonitor() {
  const welcomeScreen = document.getElementById('welcome-screen');
  if (!welcomeScreen) return;

  // Inject widget after welcome-sub
  if (!document.getElementById('egress-monitor')) {
    _egressWidget = _createEgressWidget();
    const tip = document.getElementById('welcome-tip');
    if (tip) {
      welcomeScreen.insertBefore(_egressWidget, tip);
    } else {
      welcomeScreen.appendChild(_egressWidget);
    }
  }

  // Connect SSE
  if (_egressEventSource) {
    _egressEventSource.close();
  }
  _egressEventSource = new EventSource('/api/network-stats/stream');
  _egressEventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      _updateEgressWidget(data);
    } catch (_) {}
  };
  _egressEventSource.onerror = () => {
    const dot = document.getElementById('egress-dot');
    if (dot) dot.className = 'egress-dot egress-dot--offline';
  };
}

function stopEgressMonitor() {
  if (_egressEventSource) {
    _egressEventSource.close();
    _egressEventSource = null;
  }
}

// Start when DOM is ready, stop when hidden (tab backgrounded)
document.addEventListener('DOMContentLoaded', () => {
  // Small delay so welcome screen renders first
  setTimeout(startEgressMonitor, 500);
});

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    stopEgressMonitor();
  } else {
    startEgressMonitor();
  }
});


// ─── Multi-Document Cross-Reference ──────────────────────────────────────────

function initMultiDocPanel() {
  // Inject the Multi-Doc button into the welcome screen
  const welcomeScreen = document.getElementById('welcome-screen');
  if (!welcomeScreen || document.getElementById('multidoc-panel')) return;

  const panel = document.createElement('div');
  panel.id = 'multidoc-panel';
  panel.innerHTML = `
    <div class="multidoc-header">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>
      <span>Multi-Document Analysis</span>
    </div>
    <div class="multidoc-sub">Upload multiple documents and ask questions across all of them</div>
    <div class="multidoc-drop" id="multidoc-drop">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.4"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      <span>Drop files here or <label for="multidoc-file-input" style="color:var(--accent,#10b981);cursor:pointer;text-decoration:underline">browse</label></span>
      <input type="file" id="multidoc-file-input" multiple accept=".pdf,.docx,.pptx,.xlsx,.txt,.md" style="display:none">
      <div id="multidoc-file-list" class="multidoc-file-list"></div>
    </div>
    <div class="multidoc-question-row">
      <input type="text" id="multidoc-question" class="multidoc-question-input"
        placeholder="e.g. What are the key differences between these documents?"
        value="Compare and summarize the key points across all these documents">
      <button class="multidoc-analyze-btn" id="multidoc-analyze-btn">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        Analyze
      </button>
    </div>
    <div id="multidoc-result" class="multidoc-result" style="display:none"></div>
  `;

  // Insert after egress monitor or after welcome-tip
  const egressMonitor = document.getElementById('egress-monitor');
  const incognitoBtn = document.querySelector('.incognito-btn');
  if (egressMonitor && egressMonitor.nextSibling) {
    welcomeScreen.insertBefore(panel, egressMonitor.nextSibling);
  } else if (incognitoBtn) {
    welcomeScreen.insertBefore(panel, incognitoBtn);
  } else {
    welcomeScreen.appendChild(panel);
  }

  // Wire up file input
  const fileInput = document.getElementById('multidoc-file-input');
  const dropZone = document.getElementById('multidoc-drop');
  const fileList = document.getElementById('multidoc-file-list');
  let _pendingFiles = [];

  function renderFileList() {
    if (!fileList) return;
    fileList.innerHTML = _pendingFiles.map((f, i) => `
      <div class="multidoc-file-chip">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span>${f.name}</span>
        <button class="multidoc-remove-file" data-idx="${i}" title="Remove" aria-label="Remove file">×</button>
      </div>
    `).join('');
    fileList.querySelectorAll('.multidoc-remove-file').forEach(btn => {
      btn.addEventListener('click', () => {
        _pendingFiles.splice(parseInt(btn.dataset.idx), 1);
        renderFileList();
      });
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      _pendingFiles = [..._pendingFiles, ...Array.from(fileInput.files)];
      fileInput.value = '';
      renderFileList();
    });
  }

  // Drag and drop
  if (dropZone) {
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('multidoc-drop--active'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('multidoc-drop--active'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('multidoc-drop--active');
      _pendingFiles = [..._pendingFiles, ...Array.from(e.dataTransfer.files)];
      renderFileList();
    });
  }

  // Analyze button
  const analyzeBtn = document.getElementById('multidoc-analyze-btn');
  const resultDiv = document.getElementById('multidoc-result');
  const questionInput = document.getElementById('multidoc-question');

  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', async () => {
      if (_pendingFiles.length === 0) {
        if (resultDiv) { resultDiv.style.display = 'block'; resultDiv.innerHTML = '<span style="color:var(--color-error,#ef4444)">Please add at least one document first.</span>'; }
        return;
      }

      analyzeBtn.disabled = true;
      analyzeBtn.textContent = 'Uploading...';
      if (resultDiv) { resultDiv.style.display = 'block'; resultDiv.innerHTML = '<span style="opacity:0.6">Uploading and extracting documents...</span>'; }

      try {
        // Upload all files first
        const uploadedIds = [];
        for (const file of _pendingFiles) {
          const fd = new FormData();
          fd.append('files', file);
          const upRes = await fetch('/api/upload', { method: 'POST', body: fd, credentials: 'same-origin' });
          if (upRes.ok) {
            const upData = await upRes.json();
            const ids = (upData.files || []).map(f => f.id).filter(Boolean);
            uploadedIds.push(...ids);
          }
        }

        if (uploadedIds.length === 0) {
          if (resultDiv) resultDiv.innerHTML = '<span style="color:var(--color-error,#ef4444)">Upload failed. Check file formats.</span>';
          return;
        }

        analyzeBtn.textContent = 'Analyzing...';
        if (resultDiv) resultDiv.innerHTML = `<span style="opacity:0.6">Extracting text from ${uploadedIds.length} document(s)...</span>`;

        const analyzeRes = await fetch('/api/multi-doc/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            attachment_ids: uploadedIds,
            question: questionInput?.value || 'Compare and summarize these documents'
          })
        });

        if (!analyzeRes.ok) {
          const err = await analyzeRes.json().catch(() => ({}));
          if (resultDiv) resultDiv.innerHTML = `<span style="color:var(--color-error,#ef4444)">Error: ${err.error || analyzeRes.status}</span>`;
          return;
        }

        const data = await analyzeRes.json();

        // Show summary and "Send to Chat" button
        if (resultDiv) {
          const docSummary = (data.documents || []).map(d =>
            `<span class="multidoc-file-chip"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> ${d.name} (${_fmtBytes(d.chars)})</span>`
          ).join('');
          resultDiv.innerHTML = `
            <div class="multidoc-summary">
              <strong>✅ ${data.document_count} document(s) extracted</strong> — ${_fmtBytes(data.total_chars)} total
            </div>
            <div class="multidoc-doc-chips">${docSummary}</div>
            <button class="multidoc-send-btn" id="multidoc-send-btn">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
              Send to Chat for AI Analysis
            </button>
          `;
          // Wire up send button
          const sendBtn = document.getElementById('multidoc-send-btn');
          if (sendBtn) {
            sendBtn.addEventListener('click', () => {
              _sendMultiDocToChat(data.suggested_prompt, uploadedIds);
            });
          }
        }
      } catch (e) {
        if (resultDiv) resultDiv.innerHTML = `<span style="color:var(--color-error,#ef4444)">Error: ${e.message}</span>`;
      } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Analyze';
      }
    });
  }
}

function _sendMultiDocToChat(suggestedPrompt, attachmentIds) {
  // Find the chat input and inject the suggested prompt
  const chatInput = document.getElementById('chat-input') ||
                    document.querySelector('textarea[name="message"]') ||
                    document.querySelector('.chat-input textarea') ||
                    document.querySelector('#message-input');

  if (chatInput) {
    chatInput.value = suggestedPrompt;
    chatInput.dispatchEvent(new Event('input', { bubbles: true }));
    chatInput.focus();

    // Scroll to input
    chatInput.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Hide welcome screen if visible
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) chatContainer.classList.remove('welcome-active');
    const welcomeScreen = document.getElementById('welcome-screen');
    if (welcomeScreen) welcomeScreen.style.display = 'none';
  } else {
    // Fallback: copy to clipboard
    navigator.clipboard?.writeText(suggestedPrompt).then(() => {
      alert('Analysis prompt copied to clipboard — paste it in the chat input.');
    });
  }
}

// Initialize multi-doc panel after DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(initMultiDocPanel, 600);
});

export { startEgressMonitor, stopEgressMonitor, initMultiDocPanel };

/**
 * zero_egress.js
 *
 * Zero-Egress Monitor: floating shield button (bottom-right) that opens
 * a clean popup panel showing live network I/O stats. The outbound counter
 * staying near 0 during AI inference proves no data leaves the machine.
 *
 * Multi-Document Cross-Reference: separate feature wired to the chat flow
 * via /api/multi-doc/analyze — keeps the welcome screen clean.
 */

// ─── Floating Panel Logic ─────────────────────────────────────────────────────

let _egressSSE = null;
let _panelOpen = false;

function _fmt(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function _updatePanel(data) {
  const sentEl        = document.getElementById('egress-sent');
  const recvEl        = document.getElementById('egress-recv');
  const sentDeltaEl   = document.getElementById('egress-sent-delta');
  const recvDeltaEl   = document.getElementById('egress-recv-delta');
  const statusIcon    = document.getElementById('egress-status-icon');
  const statusText    = document.getElementById('egress-status-text');
  const panelDot      = document.getElementById('egress-panel-dot');
  const fabDot        = document.getElementById('egress-fab-dot');
  const uptimeEl      = document.getElementById('egress-uptime');
  const statusBar     = document.getElementById('egress-panel-status');

  if (sentEl) sentEl.textContent = data.sent_fmt || '0 B';
  if (recvEl) recvEl.textContent = data.recv_fmt || '0 B';

  if (sentDeltaEl) {
    sentDeltaEl.textContent = data.sent_delta > 0
      ? `↑ ${_fmt(data.sent_delta)}/s` : '';
  }
  if (recvDeltaEl) {
    recvDeltaEl.textContent = data.recv_delta > 0
      ? `↓ ${_fmt(data.recv_delta)}/s` : '';
  }

  // Format uptime
  if (uptimeEl && data.uptime_s != null) {
    const s = data.uptime_s;
    const mm = Math.floor(s / 60);
    const ss = s % 60;
    uptimeEl.textContent = mm > 0 ? `${mm}m ${ss}s` : `${ss}s`;
  }

  // Dot animation
  if (panelDot) panelDot.className = 'epd epd--live';
  if (fabDot)   fabDot.className   = 'egress-fab-dot egress-fab-dot--live';

  // Status bar
  if (data.egress_zero) {
    if (statusIcon) statusIcon.textContent = '✅';
    if (statusText) statusText.textContent = 'Zero Data Egress — AI runs 100% locally';
    if (statusBar)  statusBar.className = 'egress-panel-status egress-panel-status--ok';
  } else {
    if (statusIcon) statusIcon.textContent = '⚠️';
    if (statusText) statusText.textContent = `Network activity detected (${data.sent_fmt} sent)`;
    if (statusBar)  statusBar.className = 'egress-panel-status egress-panel-status--warn';
  }
}

function _startSSE() {
  if (_egressSSE) return;
  _egressSSE = new EventSource('/api/network-stats/stream');
  _egressSSE.onmessage = (e) => {
    try { _updatePanel(JSON.parse(e.data)); } catch (_) {}
  };
  _egressSSE.onerror = () => {
    const d = document.getElementById('egress-panel-dot');
    if (d) d.className = 'epd epd--offline';
  };
}

function _stopSSE() {
  if (_egressSSE) { _egressSSE.close(); _egressSSE = null; }
}

function _openPanel() {
  const panel = document.getElementById('egress-panel');
  const fab   = document.getElementById('egress-fab');
  if (!panel) return;
  panel.classList.add('egress-panel--open');
  panel.setAttribute('aria-hidden', 'false');
  if (fab) fab.classList.add('egress-fab--active');
  _panelOpen = true;
  _startSSE();
}

function _closePanel() {
  const panel = document.getElementById('egress-panel');
  const fab   = document.getElementById('egress-fab');
  if (!panel) return;
  panel.classList.remove('egress-panel--open');
  panel.setAttribute('aria-hidden', 'true');
  if (fab) fab.classList.remove('egress-fab--active');
  _panelOpen = false;
}

function initEgressMonitor() {
  const fab = document.getElementById('egress-fab');
  if (!fab) return;

  // FAB click toggles panel
  fab.addEventListener('click', () => {
    _panelOpen ? _closePanel() : _openPanel();
  });

  // Close button
  const closeBtn = document.getElementById('egress-panel-close');
  if (closeBtn) closeBtn.addEventListener('click', _closePanel);

  // Click outside to close
  document.addEventListener('click', (e) => {
    const panel = document.getElementById('egress-panel');
    if (_panelOpen && panel && !panel.contains(e.target) && e.target !== fab && !fab.contains(e.target)) {
      _closePanel();
    }
  });

  // Keyboard close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && _panelOpen) _closePanel();
  });

  // Start a snapshot on load to show initial values even before panel opens
  fetch('/api/network-stats/snapshot')
    .then(r => r.json())
    .then(data => _updatePanel({ ...data, sent_delta: 0, recv_delta: 0, uptime_s: 0 }))
    .catch(() => {});

  // Tab visibility
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      _stopSSE();
    } else if (_panelOpen) {
      _startSSE();
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setTimeout(initEgressMonitor, 300);
});


// ─── Multi-Document Cross-Reference (API helper) ─────────────────────────────
// This is exposed as a window function so other JS modules can call it.

window.hexaMultiDocAnalyze = async function(attachmentIds, question) {
  const res = await fetch('/api/multi-doc/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ attachment_ids: attachmentIds, question }),
  });
  if (!res.ok) throw new Error(`multi-doc analyze: ${res.status}`);
  return res.json();
};

export { initEgressMonitor };

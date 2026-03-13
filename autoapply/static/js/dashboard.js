/* AutoApply Dashboard — Shared JS utilities */

// ─── Toast Notifications ─────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  const colors = {
    success: 'background:#166534;color:#bbf7d0;border:1px solid #16a34a',
    error: 'background:#7f1d1d;color:#fecaca;border:1px solid #dc2626',
    info: 'background:#1e3a5f;color:#bfdbfe;border:1px solid #3b82f6',
    warning: 'background:#78350f;color:#fde68a;border:1px solid #d97706',
  };
  toast.style.cssText = `padding:0.75rem 1.25rem;border-radius:0.5rem;font-size:0.875rem;min-width:260px;${colors[type] || colors.info}`;
  toast.textContent = message;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ─── API helpers ──────────────────────────────────────────────────────────────
async function apiPost(url, data = {}) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return resp.json();
}

async function apiGet(url) {
  const resp = await fetch(url);
  return resp.json();
}

// ─── Agent control ────────────────────────────────────────────────────────────
async function startAgent() {
  const d = await apiPost('/api/agent/start');
  showToast(d.message, d.status === 'success' ? 'success' : 'error');
  return d.status === 'success';
}

async function stopAgent() {
  const d = await apiPost('/api/agent/stop');
  showToast(d.message, 'info');
}

async function getAgentStatus() {
  return apiGet('/api/agent/status');
}

// ─── Job actions ──────────────────────────────────────────────────────────────
async function analyzeJob(id) {
  showToast('Analyzing job fit…', 'info');
  const d = await apiPost(`/api/jobs/${id}/analyze`);
  if (d.status === 'success') {
    showToast(`Fit score: ${(d.fit_score * 100).toFixed(0)}%`, 'success');
    return d;
  } else {
    showToast(d.message || 'Analysis failed', 'error');
    return null;
  }
}

async function applyToJob(id, dryRun = false) {
  if (!confirm('Apply to this job?')) return;
  const d = await apiPost(`/api/jobs/${id}/apply`, { dry_run: dryRun });
  showToast(d.message, d.status === 'success' ? 'success' : 'error');
  return d;
}

async function skipJob(id) {
  const d = await apiPost(`/api/jobs/${id}/skip`);
  if (d.status === 'success') {
    const row = document.getElementById(`job-${id}`);
    if (row) { row.style.opacity = '0.4'; row.style.pointerEvents = 'none'; }
    showToast('Job skipped', 'info');
  }
}

async function triggerScrape() {
  showToast('Scrape started…', 'info');
  const d = await apiPost('/api/jobs/scrape');
  showToast(d.message, d.status === 'success' ? 'success' : 'error');
}

// ─── Polling ──────────────────────────────────────────────────────────────────
function pollAgentStatus(intervalMs = 10000, onUpdate = null) {
  const poll = async () => {
    try {
      const status = await getAgentStatus();
      const dot = document.getElementById('status-dot');
      const text = document.getElementById('status-text');
      if (dot && text) {
        if (status.running) {
          dot.className = 'w-2 h-2 rounded-full bg-green-400 animate-pulse';
          text.className = 'text-green-400';
          text.textContent = 'Agent Running';
        } else {
          dot.className = 'w-2 h-2 rounded-full bg-slate-500';
          text.className = 'text-slate-400';
          text.textContent = 'Agent Idle';
        }
      }
      if (onUpdate) onUpdate(status);
    } catch (e) {}
  };
  poll();
  return setInterval(poll, intervalMs);
}

// Start polling automatically
pollAgentStatus();

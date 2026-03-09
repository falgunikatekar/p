/**
 * Sentiment Pulse - Frontend Application
 * Handles API calls, charts, navigation, and UI updates
 */

const API_BASE = 'http://localhost:8000';

// Navigation
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const viewId = 'view-' + btn.dataset.view;
    document.getElementById(viewId)?.classList.add('active');
    if (btn.dataset.view === 'analytics') refreshAnalytics();
    if (btn.dataset.view === 'pr-risks') refreshPRRisks();
    if (btn.dataset.view === 'report') refreshReport();
    if (btn.dataset.view === 'preprocessing') refreshPreprocessing();
    if (btn.dataset.view === 'categorization') refreshCategorization();
    if (btn.dataset.view === 'highlights') refreshHighlights();
  });
});

// Collect Comments
document.getElementById('btn-collect').addEventListener('click', async () => {
  const btn = document.getElementById('btn-collect');
  btn.classList.add('loading');
  btn.disabled = true;
  try {
    const postUrl = document.getElementById('input-post-url')?.value?.trim() || null;
    const useMock = document.getElementById('toggle-mock')?.checked ?? true;
    if (!useMock && !postUrl) {
      showToast('Paste an Instagram post link (or enable mock mode).');
      return;
    }
    const res = await fetch(`${API_BASE}/api/collect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_mock: useMock, post_url: postUrl }),
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Collected ${data.count} comments from Instagram`);
      refreshComments();
      refreshQuickStats();
    } else {
      showToast(data.error || data.detail || 'Collection failed');
    }
  } catch (e) {
    showToast('Error: ' + e.message);
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
});

// Download PDF
document.getElementById('btn-download-pdf')?.addEventListener('click', () => {
  window.open(`${API_BASE}/api/report/pdf`, '_blank');
  showToast('PDF report downloading...');
});

// Run Analysis
document.getElementById('btn-analyze').addEventListener('click', async () => {
  const btn = document.getElementById('btn-analyze');
  btn.classList.add('loading');
  btn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (data.success) {
      showToast('Analysis complete! Sentiment classified.');
      refreshQuickStats();
      refreshAnalytics();
    } else {
      showToast(data.error || 'Run Collect first');
    }
  } catch (e) {
    showToast('Error: ' + e.message);
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
});

function showToast(msg) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

async function refreshComments() {
  const list = document.getElementById('comments-list');
  try {
    const res = await fetch(`${API_BASE}/api/comments`);
    const data = await res.json();
    const comments = data.comments || [];
    if (comments.length === 0) {
      list.innerHTML = '<p class="empty-state">Collect comments first to see them here.</p>';
      return;
    }
    list.innerHTML = comments.map(c => `
      <div class="comment-card ${c.sentiment}">
        <div class="comment-header">
          <span class="comment-user">${escapeHtml(c.username)}</span>
          <span class="comment-sentiment ${c.sentiment}">${c.sentiment}</span>
        </div>
        <p class="comment-text">${escapeHtml(c.text)}</p>
        <div class="comment-meta">
          ${c.likes || 0} likes · ${c.replies || 0} replies · ${c.emotion || ''}
        </div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = '<p class="empty-state">Error loading comments.</p>';
  }
}

async function refreshQuickStats() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics`);
    const data = await res.json();
    if (data.error) {
      document.getElementById('stat-total').textContent = '0';
      document.getElementById('stat-positive').textContent = '0%';
      document.getElementById('stat-negative').textContent = '0%';
      document.getElementById('stat-neutral').textContent = '0%';
      return;
    }
    document.getElementById('stat-total').textContent = data.total || 0;
    document.getElementById('stat-positive').textContent = (data.percentages?.positive || 0) + '%';
    document.getElementById('stat-negative').textContent = (data.percentages?.negative || 0) + '%';
    document.getElementById('stat-neutral').textContent = (data.percentages?.neutral || 0) + '%';
  } catch (e) {
    document.getElementById('stat-total').textContent = '0';
  }
}

async function refreshAnalytics() {
  const donutEl = document.getElementById('donut-chart');
  const legendEl = document.getElementById('donut-legend');
  const barEl = document.getElementById('bar-chart');
  try {
    const res = await fetch(`${API_BASE}/api/analytics`);
    const data = await res.json();
    if (data.error) {
      donutEl.innerHTML = '<p class="empty-state">Run Collect & Analyze first.</p>';
      legendEl.innerHTML = '';
      barEl.innerHTML = '';
      return;
    }
    const dist = data.sentiment_distribution || [];
    const total = dist.reduce((s, d) => s + d.value, 0) || 1;
    // Donut chart (CSS conic-gradient)
    let acc = 0;
    const segments = dist.map((d) => {
      const start = acc;
      acc += (d.value / total) * 100;
      return `${d.color} ${start}% ${acc}%`;
    }).join(', ');
    donutEl.style.background = segments
      ? `radial-gradient(circle at center, white 0%, white 55%, transparent 55%), conic-gradient(${segments})`
      : 'rgba(0,0,0,0.06)';
    legendEl.innerHTML = dist.map(d => `
      <div class="legend-item">
        <span class="legend-dot" style="background:${d.color}"></span>
        <span>${d.label}: ${d.value} (${((d.value / total) * 100).toFixed(1)}%)</span>
      </div>
    `).join('');
    // Bar chart - emotions
    const emotions = data.emotion_breakdown || [];
    const maxVal = Math.max(...emotions.map(e => e.value), 1);
    barEl.innerHTML = emotions.map(e => `
      <div class="bar-row">
        <span class="bar-label">${e.label}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width:${(e.value / maxVal) * 100}%; background: var(--pastel-lavender);"></div>
        </div>
        <span style="font-size:0.85rem;color:var(--text-muted);min-width:40px">${e.value}</span>
      </div>
    `).join('') || '<p class="empty-state">No emotion data</p>';
  } catch (e) {
    donutEl.innerHTML = '<p class="empty-state">Error loading analytics.</p>';
    legendEl.innerHTML = '';
    barEl.innerHTML = '';
  }
}

async function refreshPRRisks() {
  const summaryEl = document.getElementById('risk-summary');
  const listEl = document.getElementById('risks-list');
  try {
    const res = await fetch(`${API_BASE}/api/pr-risks`);
    const data = await res.json();
    const risks = data.risks || [];
    summaryEl.innerHTML = `
      <div style="display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
        <span><strong>Risk Level:</strong> <span style="text-transform:capitalize;color:${data.risk_level==='elevated'?'var(--negative)':'var(--positive)'}">${data.risk_level || 'low'}</span></span>
        <span><strong>Negative Comments:</strong> ${data.negative_count || 0}</span>
      </div>
    `;
    if (risks.length === 0) {
      listEl.innerHTML = '<p class="empty-state">No PR risks detected. Run Collect & Analyze first.</p>';
    } else {
      listEl.innerHTML = risks.map(r => `
        <div class="risk-card ${r.severity}">
          <div class="risk-theme">${escapeHtml(r.theme)}</div>
          <div class="risk-meta">${r.count} mentions · Severity: ${r.severity}</div>
          <div class="risk-recommendation">${escapeHtml(r.recommendation)}</div>
        </div>
      `).join('');
    }
  } catch (e) {
    summaryEl.innerHTML = '<p>Error loading PR risks.</p>';
    listEl.innerHTML = '';
  }
}

async function refreshReport() {
  const el = document.getElementById('report-content');
  try {
    const res = await fetch(`${API_BASE}/api/report`);
    const data = await res.json();
    if (data.error) {
      el.innerHTML = '<p class="empty-state">Run Collect & Analyze first.</p>';
      return;
    }
    const s = data.summary || {};
    el.innerHTML = `
      <div class="report-section">
        <h3>📊 Overview</h3>
        <div class="report-summary">
          <div class="report-summary-item"><strong>${s.total_comments || 0}</strong> Total Comments</div>
          <div class="report-summary-item"><strong>${s.positive_pct || 0}%</strong> Positive</div>
          <div class="report-summary-item"><strong>${s.negative_pct || 0}%</strong> Negative</div>
          <div class="report-summary-item"><strong>${s.neutral_pct || 0}%</strong> Neutral</div>
        </div>
      </div>
      <div class="report-section">
        <h3>⚠️ Top 5 Key Customer Issues</h3>
        ${(data.top_5_issues || []).map(i => `
          <div class="issue-item">
            <strong>${escapeHtml(i.username)}</strong>: ${escapeHtml(i.text)}
            <br><small>${i.likes || 0} likes</small>
          </div>
        `).join('') || '<p>No issues identified.</p>'}
      </div>
      <div class="report-section">
        <h3>💚 Most Frequent Positive Feedback</h3>
        ${(data.most_frequent_positive_feedback || []).map(f => `
          <div class="feedback-item">
            <strong>${escapeHtml(f.theme)}</strong>: ${f.count} mentions
          </div>
        `).join('') || '<p>No positive themes yet.</p>'}
      </div>
      <div class="report-section">
        <h3>📈 Trend Analysis</h3>
        <p><strong>Overall Sentiment:</strong> ${(data.trend_analysis?.overall_sentiment || 'N/A')}</p>
        <p><strong>Recommendation:</strong> ${escapeHtml(data.trend_analysis?.recommendation || 'N/A')}</p>
      </div>
    `;
  } catch (e) {
    el.innerHTML = '<p class="empty-state">Error loading report.</p>';
  }
}

function escapeHtml(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

async function refreshPreprocessing() {
  const el = document.getElementById('preprocessing-content');
  try {
    const res = await fetch(`${API_BASE}/api/preprocessing`);
    const data = await res.json();
    if (data.error) {
      el.innerHTML = '<p class="empty-state">Collect and run analysis first.</p>';
      return;
    }
    el.innerHTML = (data.samples || []).map(s => `
      <div class="preprocess-sample">
        <div class="raw"><strong>Raw:</strong> ${escapeHtml(s.raw)}</div>
        <div class="cleaned"><strong>Cleaned:</strong> ${escapeHtml(s.cleaned)}</div>
      </div>
    `).join('') || '<p class="empty-state">No data.</p>';
  } catch (e) {
    el.innerHTML = '<p class="empty-state">Error loading preprocessing.</p>';
  }
}

async function refreshCategorization() {
  const gridEl = document.getElementById('category-grid');
  const listEl = document.getElementById('categorized-comments');
  try {
    const res = await fetch(`${API_BASE}/api/categorization`);
    const data = await res.json();
    if (data.error) {
      gridEl.innerHTML = '';
      listEl.innerHTML = '<p class="empty-state">Collect first.</p>';
      return;
    }
    const counts = data.counts || {};
    const cats = ['Pricing', 'Delivery', 'Complaints', 'Enquiries', 'Other'];
    gridEl.innerHTML = cats.map(c => `
      <div class="category-badge ${c.toLowerCase()}">
        <span class="count">${counts[c] || 0}</span>
        <span class="label">${c}</span>
      </div>
    `).join('');
    const byCat = data.by_category || {};
    listEl.innerHTML = cats.map(cat => {
      const items = byCat[cat] || [];
      if (!items.length) return '';
      return `
        <div class="cat-group">
          <h4>${cat} (${items.length})</h4>
          ${items.map(c => `
            <div class="comment-card ${c.sentiment}">
              <div class="comment-header">
                <span class="comment-user">${escapeHtml(c.username)}</span>
                <span class="comment-sentiment ${c.sentiment}">${c.sentiment}</span>
              </div>
              <p class="comment-text">${escapeHtml(c.text)}</p>
            </div>
          `).join('')}
        </div>
      `;
    }).join('') || '<p class="empty-state">No categorized comments.</p>';
  } catch (e) {
    gridEl.innerHTML = '';
    listEl.innerHTML = '<p class="empty-state">Error loading.</p>';
  }
}

async function refreshHighlights() {
  const highlightsEl = document.getElementById('positive-highlights');
  const feedbackEl = document.getElementById('feedback-summary');
  const opinionsEl = document.getElementById('expert-opinions');
  if (!highlightsEl || !feedbackEl || !opinionsEl) return;
  try {
    const [hRes, oRes] = await Promise.all([
      fetch(`${API_BASE}/api/positive-highlights`),
      fetch(`${API_BASE}/api/expert-opinions`),
    ]);
    const hData = await hRes.json();
    const oData = await oRes.json();
    if (hData.error) {
      highlightsEl.innerHTML = '<p class="empty-state">Collect first.</p>';
      feedbackEl.innerHTML = '';
    } else {
      highlightsEl.innerHTML = (hData.highlights || []).map(h => `
        <div class="highlight-item">
          <strong>${escapeHtml(h.username)}</strong>: ${escapeHtml(h.text)}
          <br><small>${h.likes || 0} likes</small>
        </div>
      `).join('') || '<p class="empty-state">No positive highlights yet.</p>';
      const themes = hData.feedback_themes || {};
      feedbackEl.innerHTML = Object.entries(themes).map(([k, v]) => `
        <div class="feedback-item"><strong>${escapeHtml(k)}</strong>: ${v} mentions</div>
      `).join('') || '<p class="empty-state">No feedback themes.</p>';
    }
    if (oData.error) {
      opinionsEl.innerHTML = '<p class="empty-state">Run analysis first.</p>';
    } else {
      opinionsEl.innerHTML = (oData.opinions || []).map(o => `
        <div class="expert-opinion-item">${escapeHtml(o)}</div>
      `).join('');
    }
  } catch (e) {
    highlightsEl.innerHTML = feedbackEl.innerHTML = opinionsEl.innerHTML = '<p class="empty-state">Error loading.</p>';
  }
}

// Initial load
refreshComments();
refreshQuickStats();

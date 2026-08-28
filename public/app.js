const $ = (id) => document.getElementById(id);
const money = (value) => `$${Number(value || 0).toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
let selectedDecision = null;

async function api(path, options) {
  const response = await fetch(path, options);
  return response.json();
}
function regimeLabel(value) { return value.replace('_', ' ').toUpperCase(); }
function renderMarket(rows) {
  $('market').innerHTML = `<div class="market-row head"><span>ASSET</span><span class="price">PRICE</span><span class="change">24H CHANGE</span><span class="regime">REGIME</span></div>` + rows.map(a => `<div class="market-row"><span class="asset-name">${a.symbol}</span><span class="price">${money(a.price)}</span><span class="change ${a.change24h >= 0 ? 'up' : 'down'}">${a.change24h >= 0 ? '+' : ''}${a.change24h}%</span><span class="regime">${regimeLabel(a.regime)}</span></div>`).join('');
}
function renderFeed(decisions) {
  $('feed').innerHTML = decisions.slice(0, 8).map(d => `<div class="feed-item" data-id="${d.id}"><span class="feed-num">#${String(d.id).padStart(3, '0')}</span><div class="feed-main"><strong>${d.asset} · ${d.direction.toUpperCase()}</strong><p>${d.thesis}</p></div><div class="feed-side ${d.accepted ? 'accepted' : 'rejected'}">${d.accepted ? 'ACCEPTED' : 'REJECTED'}<br><span>${d.accepted ? money(d.size) : d.reason}</span></div></div>`).join('') || '<p class="receipt-empty">Waiting for the first cycle...</p>';
  document.querySelectorAll('.feed-item').forEach(item => item.addEventListener('click', () => loadReceipt(item.dataset.id)));
}
async function loadReceipt(id) {
  selectedDecision = id; const data = await api(`/agent/decisions/${id}/receipt`); const d = data.decision;
  $('receipt-title').textContent = `Decision #${String(id).padStart(3, '0')} · ${d.asset}`; $('receipt-regime').textContent = regimeLabel(d.regime);
  const checks = Object.entries(data.checks).map(([key, value]) => `<div class="receipt-row"><span>${key.replaceAll('_', ' ')}</span><b class="${value ? 'pass' : 'fail'}">${value ? 'PASS' : 'FAIL'}</b></div>`).join('');
  $('receipt').innerHTML = `<div class="receipt-block"><h3>THESIS PROPOSAL</h3><p class="receipt-thesis">${d.thesis}</p><div class="receipt-row"><span>direction / confidence</span><b>${d.direction} / ${d.confidence}</b></div><div class="receipt-row"><span>expected edge</span><b>${d.expectedEdgeBps} bps</b></div></div><div class="receipt-block"><h3>DETERMINISTIC CONTROL</h3>${checks}</div><div class="receipt-block"><h3>SIZING RATIONALE</h3><div class="receipt-row"><span>kelly base</span><b>${money(data.sizing.baseKelly)}</b></div><div class="receipt-row"><span>regime throttle</span><b>${data.sizing.throttleMultiplier}x</b></div><div class="receipt-row"><span>final allocation</span><b class="${d.accepted ? 'pass' : 'fail'}">${money(data.sizing.finalSize)}</b></div></div><div class="receipt-block"><h3>MEMORY CONTEXT</h3><p class="receipt-thesis">${data.memory.priorOutcome}</p></div>`;
}
function drawChart(history) {
  const canvas = $('chart'); const ctx = canvas.getContext('2d'); const width = canvas.clientWidth * devicePixelRatio; const height = 220 * devicePixelRatio; canvas.width = width; canvas.height = height; ctx.scale(devicePixelRatio, devicePixelRatio);
  const w = canvas.clientWidth, h = 220; ctx.clearRect(0, 0, w, h); ctx.strokeStyle = '#e3e0d8'; ctx.lineWidth = 1; for (let y = 30; y < h; y += 45) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
  if (!history.length) return; const values = history.map(x => x.equity); const min = Math.min(...values) - 3, max = Math.max(...values) + 3; ctx.beginPath(); history.forEach((item, i) => { const x = history.length === 1 ? 0 : i / (history.length - 1) * w; const y = h - 25 - ((item.equity - min) / (max - min || 1)) * (h - 50); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.strokeStyle = '#d94c35'; ctx.lineWidth = 2.5; ctx.stroke();
}
async function refresh() {
  const [status, market, portfolio, metrics, decisions] = await Promise.all([api('/agent/status'), api('/market'), api('/portfolio'), api('/metrics'), api('/agent/decisions')]);
  $('agent-status').textContent = `${status.killed ? 'HALTED' : 'LIVE'} / CYCLE ${status.cycle}`; document.querySelector('.dot').style.background = status.killed ? '#c15442' : '#46a477';
  $('equity').textContent = money(portfolio.equity); $('pnl').textContent = `${portfolio.pnl >= 0 ? '+' : ''}${money(portfolio.pnl)} / ${((portfolio.pnl / portfolio.capital) * 100).toFixed(1)}%`; $('pnl').className = portfolio.pnl >= 0 ? 'positive' : 'down'; $('exposure').textContent = money(portfolio.exposure); $('exposure-pct').textContent = `${portfolio.exposurePct}% of capital`; $('dph').textContent = metrics.decisionsPerHour; $('accepted').textContent = metrics.accepted; $('rejected').textContent = metrics.rejected; $('shifts').textContent = metrics.regimeShifts;
  renderMarket(market); renderFeed(decisions); drawChart(metrics.history);
  if (selectedDecision) loadReceipt(selectedDecision);
}
$('kill').addEventListener('click', async () => { const status = await api('/agent/status'); if (status.killed) { await api('/agent/resume', { method: 'POST' }); $('kill').textContent = 'Kill switch'; } else { await api('/agent/kill', { method: 'POST' }); $('kill').textContent = 'Resume agent'; } refresh(); });
$('stress').addEventListener('click', async () => { const asset = prompt('Asset for synthetic volatility/liquidity shock:', 'SOL-USD'); if (asset) { await api('/stress-test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ asset }) }); $('stress').textContent = `${asset} shock active`; setTimeout(() => $('stress').textContent = 'Inject shock', 9000); } });
refresh(); setInterval(refresh, 2500); window.addEventListener('resize', () => api('/metrics').then(x => drawChart(x.history)));

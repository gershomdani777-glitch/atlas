const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const PORT = process.env.PORT || 3000;
const ASSETS = [
  { symbol: 'BTC-USD', price: 104820, baseVol: 0.010, depth: 920000 },
  { symbol: 'ETH-USD', price: 3825, baseVol: 0.014, depth: 510000 },
  { symbol: 'SOL-USD', price: 184.2, baseVol: 0.024, depth: 180000 },
  { symbol: 'AVAX-USD', price: 36.8, baseVol: 0.031, depth: 92000 },
  { symbol: 'LINK-USD', price: 24.6, baseVol: 0.020, depth: 140000 },
  { symbol: 'XRP-USD', price: 2.48, baseVol: 0.028, depth: 110000 }
];
const state = {
  running: true, killed: false, cycle: 0, startedAt: Date.now(), stress: null,
  capital: 100000, equity: 100000, peakEquity: 100000, pnl: 0,
  assets: Object.fromEntries(ASSETS.map(asset => [asset.symbol, { ...asset, change24h: (Math.random() - .45) * 8, volatility: asset.baseVol, regime: 'normal', trend: 0.5, liquidity: 1, updatedAt: Date.now() }])),
  positions: [], decisions: [], receipts: {}, history: [], throttle: {}, config: {
    maxPositionPct: 0.12, maxExposurePct: 0.45, maxAssetExposurePct: 0.20, drawdownStopPct: 0.08, minEdgeOverCostBps: 8, kellyFraction: 0.25
  }
};
for (const asset of ASSETS) state.throttle[asset.symbol] = { trending: .92, mean_reverting: 1.04, high_volatility: .48, illiquid: .32, normal: .78 };

function round(value, digits = 2) { return Number(value.toFixed(digits)); }
function now() { return new Date().toISOString(); }
function clamp(value, low, high) { return Math.min(high, Math.max(low, value)); }
function exposure() { return state.positions.reduce((sum, p) => sum + p.size * p.entryPrice, 0); }
function regimeFor(asset) {
  const stress = state.stress === asset.symbol;
  const volatility = asset.volatility;
  if (stress || volatility > .038) return 'high_volatility';
  if (asset.depth < 105000) return 'illiquid';
  if (asset.trend > .68) return 'trending';
  if (asset.trend < .32) return 'mean_reverting';
  return 'normal';
}
function tickMarket() {
  for (const asset of Object.values(state.assets)) {
    const shock = state.stress === asset.symbol ? (Math.random() - .45) * .075 : (Math.random() - .47) * asset.baseVol;
    asset.price = round(asset.price * (1 + shock), asset.price < 100 ? 4 : 2);
    asset.change24h = round(asset.change24h * .96 + shock * 100, 2);
    asset.volatility = clamp(asset.volatility * .85 + Math.abs(shock) * 1.8, .006, .075);
    asset.trend = clamp(asset.trend * .84 + (shock > 0 ? .16 : 0), .08, .92);
    asset.depth = Math.max(30000, round(asset.depth * (state.stress === asset.symbol ? .76 : .98 + Math.random() * .04), 0));
    asset.liquidity = round(clamp(asset.depth / 500000, .04, 1.4), 2);
    asset.regime = regimeFor(asset);
    asset.updatedAt = Date.now();
  }
  for (const position of state.positions) {
    const current = state.assets[position.asset].price;
    position.unrealizedPnl = round((current - position.entryPrice) * position.size * (position.side === 'long' ? 1 : -1));
  }
  state.equity = round(state.capital + state.positions.reduce((sum, p) => sum + p.unrealizedPnl, 0) + state.pnl);
  state.peakEquity = Math.max(state.peakEquity, state.equity);
}
function interpret(asset) {
  const impulse = asset.change24h + (asset.trend - .5) * 7;
  const direction = Math.abs(impulse) < 1.2 ? 'no_action' : impulse > 0 ? 'long' : 'short';
  const confidence = clamp(.53 + Math.abs(impulse) / 28 - asset.volatility * 2, .35, .91);
  return { asset: asset.symbol, direction, thesis: direction === 'no_action' ? 'Signal quality is mixed; preserving optionality.' : `${asset.regime === 'trending' ? 'Persistent flow' : 'Short-horizon price displacement'} supports a cautious ${direction} thesis.`, expected_edge_bps: round(16 + confidence * 38), confidence: round(confidence, 2), time_horizon_minutes: 30, risk_flags: [asset.liquidity < .25 ? 'low_liquidity' : null, asset.volatility > .035 ? 'high_volatility' : null].filter(Boolean) };
}
function runCycle() {
  if (!state.running || state.killed) return;
  state.cycle += 1; tickMarket();
  const evaluated = [];
  for (const asset of Object.values(state.assets)) {
    const thesis = interpret(asset); const cost = round(6 + (1 / asset.liquidity) * 3); const throttle = state.throttle[asset.symbol][asset.regime];
    const currentExposure = exposure(); const maxAsset = state.capital * state.config.maxAssetExposurePct; const maxTotal = state.capital * state.config.maxExposurePct;
    const checks = { direction_present: thesis.direction !== 'no_action', edge_over_cost: thesis.expected_edge_bps > cost + state.config.minEdgeOverCostBps, liquidity: asset.liquidity > .08, drawdown_clear: (state.peakEquity - state.equity) / state.peakEquity < state.config.drawdownStopPct, portfolio_capacity: currentExposure < maxTotal, asset_capacity: true };
    const baseSize = state.capital * state.config.kellyFraction * thesis.confidence * (thesis.expected_edge_bps / 10000) / Math.max(asset.volatility, .01);
    const requested = clamp(baseSize * throttle, 0, Math.min(state.capital * state.config.maxPositionPct, maxAsset, maxTotal - currentExposure));
    checks.asset_capacity = requested > 0;
    const accepted = Object.values(checks).every(Boolean);
    const id = state.decisions.length + 1;
    const decision = { id, cycle: state.cycle, asset: asset.symbol, direction: thesis.direction, thesis: thesis.thesis, expectedEdgeBps: thesis.expected_edge_bps, confidence: thesis.confidence, regime: asset.regime, accepted, size: round(requested), reason: accepted ? 'All deterministic checks passed.' : Object.entries(checks).find(([, pass]) => !pass)?.[0].replaceAll('_', ' ') || 'Rejected', createdAt: now() };
    state.decisions.unshift(decision); state.receipts[id] = { decision, stages: ['perceive', 'interpret', 'classify_regime', 'allocate_risk_check', accepted ? 'execute' : 'dispose', 'observe_outcome', 'adapt'], inputs: { price: asset.price, volatility: round(asset.volatility, 4), orderBookDepth: asset.depth, liquidityScore: asset.liquidity, observedAt: now(), ttlSeconds: 15, memoryMatches: Math.min(3, state.cycle) }, checks, sizing: { baseKelly: round(baseSize), throttleMultiplier: throttle, finalSize: round(requested), estimatedCostBps: cost }, memory: { regime: asset.regime, priorOutcome: state.throttle[asset.symbol][asset.regime] > .8 ? 'Recent theses in this bucket are holding up.' : 'Recent outcomes reduced this bucket throttle.' } };
    if (accepted && thesis.direction !== 'no_action') { const fill = asset.price * (1 + (thesis.direction === 'long' ? 1 : -1) * cost / 10000); state.positions.unshift({ id, asset: asset.symbol, side: thesis.direction, size: round(requested / asset.price, 6), entryPrice: round(fill, asset.price < 100 ? 4 : 2), unrealizedPnl: 0, openedAt: now() }); }
    if (state.decisions.length > 80) state.decisions.pop(); evaluated.push(decision);
  }
  const accepted = evaluated.filter(d => d.accepted).length; state.history.push({ cycle: state.cycle, time: now(), equity: state.equity, pnl: state.equity - state.capital, accepted, regimes: Object.values(state.assets).filter(a => a.regime !== 'normal').length });
  if (state.history.length > 36) state.history.shift();
  for (const asset of Object.values(state.assets)) for (const regime of Object.keys(state.throttle[asset.symbol])) state.throttle[asset.symbol][regime] = round(clamp(state.throttle[asset.symbol][regime] * .995 + (asset.regime === regime && accepted ? .012 : 0), .2, 1.25), 2);
}
setInterval(runCycle, 4000); runCycle();

function send(res, status, body, type = 'application/json') { res.writeHead(status, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' }); res.end(type === 'application/json' ? JSON.stringify(body) : body); }
function jsonBody(req) { return new Promise(resolve => { let data = ''; req.on('data', chunk => data += chunk); req.on('end', () => { try { resolve(JSON.parse(data || '{}')); } catch { resolve({}); } }); }); }
async function handler(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`); const parts = url.pathname.split('/').filter(Boolean);
  if (req.method === 'GET' && url.pathname === '/') return send(res, 200, fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8'), 'text/html');
  if (req.method === 'GET' && url.pathname === '/app.js') return send(res, 200, fs.readFileSync(path.join(__dirname, 'public', 'app.js'), 'utf8'), 'text/javascript');
  if (req.method === 'GET' && url.pathname === '/styles.css') return send(res, 200, fs.readFileSync(path.join(__dirname, 'public', 'styles.css'), 'utf8'), 'text/css');
  if (req.method === 'GET' && url.pathname === '/agent/status') return send(res, 200, { running: state.running, killed: state.killed, cycle: state.cycle, cadenceSeconds: 4, uptimeSeconds: Math.round((Date.now() - state.startedAt) / 1000), lastStage: 'adapt' });
  if (req.method === 'POST' && url.pathname === '/agent/kill') { state.killed = true; state.running = false; return send(res, 200, { ok: true, killed: true }); }
  if (req.method === 'POST' && url.pathname === '/agent/resume') { state.killed = false; state.running = true; return send(res, 200, { ok: true, killed: false }); }
  if (req.method === 'POST' && url.pathname === '/stress-test') { const body = await jsonBody(req); state.stress = body.asset || 'SOL-USD'; return send(res, 200, { ok: true, asset: state.stress }); }
  if (req.method === 'GET' && url.pathname === '/market') return send(res, 200, Object.values(state.assets));
  if (req.method === 'GET' && url.pathname === '/portfolio') return send(res, 200, { capital: state.capital, equity: state.equity, pnl: round(state.equity - state.capital), exposure: round(exposure()), exposurePct: round(exposure() / state.capital * 100, 1), positions: state.positions.slice(0, 12) });
  if (req.method === 'GET' && url.pathname === '/metrics') return send(res, 200, { history: state.history, throttle: state.throttle, decisionsPerHour: state.cycle * 15, accepted: state.decisions.filter(d => d.accepted).length, rejected: state.decisions.filter(d => !d.accepted).length, regimeShifts: state.history.filter(h => h.regimes > 0).length });
  if (req.method === 'GET' && url.pathname === '/agent/decisions') return send(res, 200, state.decisions.slice(0, Number(url.searchParams.get('limit') || 30)));
  if (req.method === 'GET' && parts[0] === 'agent' && parts[1] === 'decisions' && parts[3] === 'receipt') return send(res, state.receipts[parts[2]] ? 200 : 404, state.receipts[parts[2]] || { error: 'Not found' });
  if (req.method === 'GET' && url.pathname === '/config/risk') return send(res, 200, state.config);
  if (req.method === 'PUT' && url.pathname === '/config/risk') { Object.assign(state.config, await jsonBody(req)); return send(res, 200, state.config); }
  send(res, 404, { error: 'Not found' });
}
http.createServer((req, res) => handler(req, res).catch(() => send(res, 500, { error: 'Internal error' }))).listen(PORT, () => console.log(`ATLAS running at http://localhost:${PORT}`));

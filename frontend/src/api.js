// Thin API client. Base URL is injected at build time (VITE_API_BASE) and can
// be overridden at runtime via window.__API_BASE__ (used by the Docker image).
let BASE =
  (typeof window !== 'undefined' && window.__API_BASE__) ||
  import.meta.env.VITE_API_BASE ||
  'http://localhost:8000';

// Render exposes services over HTTPS on the default port (443). A common
// mistake is pointing the frontend at the internal "…onrender.com:8000" or at
// http://. Normalise any *.onrender.com base to https with no explicit port so
// a copy-pasted URL still works (and we don't hit mixed-content blocks).
try {
  const u = new URL(BASE);
  if (u.hostname.endsWith('.onrender.com')) {
    u.protocol = 'https:';
    u.port = '';
  }
  BASE = u.toString().replace(/\/+$/, '');
} catch {
  /* leave BASE as-is if it isn't a parseable absolute URL */
}

function authHeaders() {
  const t = localStorage.getItem('tcg_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function req(path, { method = 'GET', body, auth = false } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(auth ? authHeaders() : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  base: BASE,
  // --- multiplayer (2-human) ---
  mpCreate: (body) => req('/api/multiplayer/create', { method: 'POST', body }),
  mpJoin: (mid, name) => req(`/api/multiplayer/${mid}/join`, { method: 'POST', body: { name } }),
  mpState: (mid, token) => req(`/api/multiplayer/${mid}/state?token=${encodeURIComponent(token || '')}`),
  mpAction: (mid, token, index) =>
    req(`/api/multiplayer/${mid}/action?token=${encodeURIComponent(token || '')}`, { method: 'POST', body: { index } }),
  mpOpen: () => req('/api/multiplayer/open'),
  mpLearned: () => req('/api/multiplayer/learned'),
  mpLearn: (epochs) => req('/api/multiplayer/learn', { method: 'POST', body: { epochs } }),
  mpLearnStatus: (jobId) => req(`/api/multiplayer/learn/${jobId}`),
  mpDatasetUrl: () => `${BASE}/api/multiplayer/dataset`,
  mpRematch: (mid, token, swap = false) =>
    req(`/api/multiplayer/${mid}/rematch?token=${encodeURIComponent(token || '')}&swap=${swap ? 'true' : 'false'}`, { method: 'POST' }),
  // --- favorites (per-user) ---
  favorites: () => req('/api/favorites', { auth: true }),
  addFavorite: (kind, ref_id) => req('/api/favorites', { method: 'POST', body: { kind, ref_id }, auth: true }),
  removeFavorite: (kind, ref_id) => req(`/api/favorites/${kind}/${encodeURIComponent(ref_id)}`, { method: 'DELETE', auth: true }),
  base: BASE,
  health: () => req('/api/health'),
  decks: () => req('/api/decks'),
  agents: () => req('/api/agents'),

  login: (username_or_email, password) =>
    req('/api/auth/login', { method: 'POST', body: { username_or_email, password } }),
  register: (username, email, password) =>
    req('/api/auth/register', { method: 'POST', body: { username, email, password } }),
  me: () => req('/api/auth/me', { auth: true }),

  newGame: (cfg) => req('/api/game/new', { method: 'POST', body: cfg }),
  state: (gid) => req(`/api/game/${gid}/state`),
  step: (gid) => req(`/api/game/${gid}/step`, { method: 'POST' }),
  action: (gid, index) => req(`/api/game/${gid}/action`, { method: 'POST', body: { index } }),
  saveGame: (gid) => req(`/api/game/${gid}/save`, { method: 'POST', auth: true }),
  myGames: () => req('/api/me/games', { auth: true }),

  metrics: () => req('/api/training/metrics'),
  cards: (q, page = 1) => req(`/api/cards/search?q=${encodeURIComponent(q)}&page=${page}`),
  cardsCatalog: () => req('/api/cards/catalog'),
  rules: () => req('/api/rules'),
  sources: () => req('/api/sources'),
  competitionInfo: () => req('/api/competition/info'),
  sets: () => req('/api/sets'),
  competitionReport: (body) => req('/api/competition/report', { method: 'POST', body }),
  competitionReportStatus: (jobId) => req(`/api/competition/report/${jobId}`),
  // ladder / submissions
  submissionsList: () => req('/api/submissions'),
  createSubmission: (body) => req('/api/submissions', { method: 'POST', body }),
  submissionDetail: (id) => req(`/api/submissions/${id}`),
  submissionExport: (id) => req(`/api/submissions/${id}/export`),
  deleteSubmission: (id) => req(`/api/submissions/${id}`, { method: 'DELETE' }),
  runEpisodes: (count) => req('/api/episodes/run', { method: 'POST', body: { count } }),
  episodeStatus: (jobId) => req(`/api/episodes/status/${jobId}`),
  cancelEpisodes: (jobId) => req(`/api/episodes/${jobId}/cancel`, { method: 'POST' }),
  // lifetime model scoreboard
  modelStats: () => req('/api/models/stats'),
  modelStatsReset: () => req('/api/models/stats/reset', { method: 'POST' }),
  modelDocs: () => req('/api/models/docs'),
  modelExport: (id) => req(`/api/models/${id}/export`),
  modelsExportAll: () => req('/api/models/export'),
  setCardImage: (id, url) => req(`/api/cards/${id}/image`, { method: 'POST', body: { url } }),
  clearCardImage: (id) => req(`/api/cards/${id}/image`, { method: 'DELETE' }),
  importDeck: (name, list) => req('/api/decks/import', { method: 'POST', body: { name, list } }),
  runTournament: (agents, decks, games_per_pairing) =>
    req('/api/tournament/run', { method: 'POST', body: { agents, decks, games_per_pairing } }),
  tournamentStatus: (jobId) => req(`/api/tournament/${jobId}`),
  cancelTournament: (jobId) => req(`/api/tournament/${jobId}/cancel`, { method: 'POST' }),
  adminUsers: () => req('/api/admin/users', { auth: true }),
};

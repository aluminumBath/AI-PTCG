// Thin API client. Base URL is injected at build time (VITE_API_BASE) and can
// be overridden at runtime via window.__API_BASE__ (used by the Docker image).
const BASE =
  (typeof window !== 'undefined' && window.__API_BASE__) ||
  import.meta.env.VITE_API_BASE ||
  'http://localhost:8000';

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
  adminUsers: () => req('/api/admin/users', { auth: true }),
};

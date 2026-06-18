// Optional "official competition data" source.
//
// When enabled, this loads the competition card metadata CSV from /public/assets
// (the file you download from the competition Data page, e.g. "EN Card Data.csv")
// and uses it to override card names/metadata — and card images — in the UI.
// This is the intended fix for "a lot of card images are wrong": the built-in
// images are derived from illustrative card ids, whereas the competition ships
// authoritative data you place in public/assets.
//
// Expected layout under frontend/public/assets/ (any one CSV name works):
//   assets/EN Card Data.csv         ← the competition card metadata
//   assets/images/<Card ID>.png     ← card images (default path pattern)
//
// The image path pattern is configurable in public/config.js, e.g.:
//   window.__OFFICIAL_IMG__ = "assets/images/{id}.png";
// Tokens: {id} {name} {expansion} {no}. If the CSV has an Image column it wins.
//
// Note: per the competition rules, the Pokémon data/images are licensed for
// competition use only — keep them local and delete after the competition.
import { useEffect, useState } from 'react';

const KEY = 'tcg.officialData';
const ASSET = (p) => `${import.meta.env.BASE_URL}${String(p).replace(/^\/+/, '')}`;

const CSV_CANDIDATES = [
  'assets/EN Card Data.csv',
  'assets/en_card_data.csv',
  'assets/cards.csv',
  'assets/card_data.csv',
];
const IMG_PATTERN =
  (typeof window !== 'undefined' && window.__OFFICIAL_IMG__) || 'assets/images/{id}.png';

let _enabled = false;
try { _enabled = localStorage.getItem(KEY) === '1'; } catch { /* no storage */ }

let _state = { ready: false, loading: false, error: null, byName: new Map(), count: 0, source: null };
const subs = new Set();
const notify = () => subs.forEach((fn) => { try { fn(); } catch { /* ignore */ } });

export function isOfficialEnabled() { return _enabled; }
export function subscribeOfficial(fn) { subs.add(fn); return () => subs.delete(fn); }

const norm = (s) => (s == null ? '' : String(s)).trim().toLowerCase();

// Minimal CSV parser with quoted-field + escaped-quote support.
function parseCSV(text) {
  const rows = []; let field = '', row = [], inq = false, i = 0;
  const pushF = () => { row.push(field); field = ''; };
  const pushR = () => { rows.push(row); row = []; };
  while (i < text.length) {
    const c = text[i];
    if (inq) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i += 2; continue; } inq = false; i++; continue; }
      field += c; i++; continue;
    }
    if (c === '"') { inq = true; i++; continue; }
    if (c === ',') { pushF(); i++; continue; }
    if (c === '\r') { i++; continue; }
    if (c === '\n') { pushF(); pushR(); i++; continue; }
    field += c; i++;
  }
  if (field.length || row.length) { pushF(); pushR(); }
  return rows;
}

function buildMaps(rows) {
  if (!rows.length) return { byName: new Map(), count: 0 };
  const header = rows[0].map((h) => norm(h));
  const idx = (names) => { for (const n of names) { const k = header.indexOf(n); if (k >= 0) return k; } return -1; };
  const ci = {
    id: idx(['card id', 'card_id', 'id']),
    name: idx(['card name', 'card_name', 'name']),
    exp: idx(['expansion', 'set']),
    no: idx(['collection no.', 'collection no', 'collection_no', 'number', 'no']),
    stage: idx(['stage (pokémon) / type (energy and trainer)', 'stage', 'type']),
    cat: idx(['category']),
    rule: idx(['rule']),
    hp: idx(['hp']),
    image: idx(['image', 'image url', 'image_url', 'img']),
  };
  const get = (row, k) => (k >= 0 && row[k] != null ? String(row[k]).trim() : '');
  const byName = new Map();
  for (let r = 1; r < rows.length; r++) {
    const row = rows[r];
    if (!row || (row.length === 1 && !row[0])) continue;
    const name = get(row, ci.name);
    if (!name) continue;
    byName.set(norm(name), {
      id: get(row, ci.id), name, expansion: get(row, ci.exp), no: get(row, ci.no),
      stage: get(row, ci.stage), category: get(row, ci.cat), rule: get(row, ci.rule),
      hp: get(row, ci.hp), image: get(row, ci.image),
    });
  }
  return { byName, count: byName.size };
}

export async function loadOfficialData(force = false) {
  if (_state.ready && !force) return _state;
  if (_state.loading) return _state;
  _state = { ..._state, loading: true, error: null }; notify();

  let text = null, used = null;
  for (const cand of CSV_CANDIDATES) {
    try {
      const res = await fetch(ASSET(cand), { cache: 'no-store' });
      if (res.ok) { text = await res.text(); used = cand; break; }
    } catch { /* try next */ }
  }
  if (text == null) {
    _state = { ...(_state), loading: false, ready: false,
      error: 'No card CSV found in public/assets (expected e.g. "EN Card Data.csv").' };
    notify(); return _state;
  }
  const { byName, count } = buildMaps(parseCSV(text));
  _state = {
    ready: true, loading: false, byName, count, source: used,
    error: count ? null : 'CSV loaded but no rows matched the expected columns.',
  };
  notify(); return _state;
}

export function setOfficial(on) {
  _enabled = !!on;
  try { localStorage.setItem(KEY, on ? '1' : '0'); } catch { /* ignore */ }
  if (on && !_state.ready && !_state.loading) loadOfficialData();
  notify();
}

function fillPattern(pat, meta) {
  return pat
    .replace('{id}', encodeURIComponent(meta.id || ''))
    .replace('{name}', encodeURIComponent(meta.name || ''))
    .replace('{expansion}', encodeURIComponent(meta.expansion || ''))
    .replace('{no}', encodeURIComponent(meta.no || ''));
}

export function officialMetaFor(card) {
  if (!_enabled || !_state.ready) return null;
  const name = card?.name || card?.card_name;
  if (!name) return null;
  return _state.byName.get(norm(name))
    || _state.byName.get(norm(String(name).replace(/ ex$/i, '')))
    || null;
}

export function officialImageFor(card) {
  const meta = officialMetaFor(card);
  if (!meta) return null;
  if (meta.image) return /^https?:\/\//.test(meta.image) ? meta.image : ASSET(meta.image);
  if (meta.id) return ASSET(fillPattern(IMG_PATTERN, meta));
  return null;
}

// React hook: re-renders the consumer when the toggle flips or data loads.
export function useOfficial() {
  const [, force] = useState(0);
  useEffect(() => subscribeOfficial(() => force((n) => n + 1)), []);
  useEffect(() => { if (_enabled && !_state.ready && !_state.loading) loadOfficialData(); }, []);
  return {
    enabled: _enabled, ready: _state.ready, loading: _state.loading,
    error: _state.error, count: _state.count, source: _state.source,
    toggle: () => setOfficial(!_enabled), set: setOfficial,
    imageFor: officialImageFor, metaFor: officialMetaFor,
  };
}

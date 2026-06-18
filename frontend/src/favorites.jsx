import { useEffect, useState } from 'react';
import { api } from './api';

// Module-level cache so every Star/list across tabs stays in sync without
// prop-drilling. The whole app is gated behind login, so favorites always have
// an authenticated user.
let cache = { decks: [], cards: [], sets: [] };
let loaded = false;
const subs = new Set();
const emit = () => subs.forEach((fn) => fn(cache));

const KEYMAP = { deck: 'decks', card: 'cards', set: 'sets' };

export async function loadFavorites() {
  try { cache = await api.favorites(); }
  catch { cache = { decks: [], cards: [], sets: [] }; }
  loaded = true; emit();
  return cache;
}

export function isFav(kind, id) {
  return (cache[KEYMAP[kind]] || []).includes(id);
}

export async function toggleFavorite(kind, id) {
  const on = isFav(kind, id);
  try {
    cache = on ? await api.removeFavorite(kind, id) : await api.addFavorite(kind, id);
    loaded = true; emit();
  } catch (e) { /* surface nothing; the star simply won't flip */ }
  return cache;
}

export function useFavorites() {
  const [f, setF] = useState(cache);
  useEffect(() => {
    const fn = (c) => setF({ ...c });
    subs.add(fn);
    if (!loaded) loadFavorites(); else setF({ ...cache });
    return () => subs.delete(fn);
  }, []);
  return { favs: f, isFav, toggle: toggleFavorite };
}

// --- small client-side card-detail cache -----------------------------------
// Favorited cards are stored server-side by id only; remember name/image here
// so the Favorites tab can render them (best-effort; falls back to the id).
const CARD_META_KEY = 'tcg.cardmeta';
function readCardMeta() {
  try { return JSON.parse(localStorage.getItem(CARD_META_KEY) || '{}'); } catch { return {}; }
}
export function rememberCard(card) {
  if (!card?.id) return;
  const m = readCardMeta();
  m[card.id] = { name: card.name, image: card.image, types: card.types };
  try { localStorage.setItem(CARD_META_KEY, JSON.stringify(m)); } catch {}
}
export function cardMeta(id) {
  return readCardMeta()[id] || null;
}

// --- reusable star toggle ---------------------------------------------------
export function Star({ kind, id, title }) {
  const { isFav: check, toggle } = useFavorites();
  const on = check(kind, id);
  return (
    <button
      type="button"
      className={`star ${on ? 'on' : ''}`}
      title={title || (on ? 'Remove favorite' : 'Add to favorites')}
      aria-pressed={on}
      onClick={(e) => { e.stopPropagation(); e.preventDefault(); toggle(kind, id); }}
    >
      {on ? '★' : '☆'}
    </button>
  );
}

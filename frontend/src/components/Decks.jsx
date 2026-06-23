import { useEffect, useState } from 'react';
import { api } from '../api';
import { Star } from '../favorites';
import { officialImageFor, useOfficial } from '../officialData';

const TYPE_COLOR = {
  Fire: 'var(--fire)', Water: 'var(--water)', Grass: 'var(--grass)',
  Psychic: 'var(--psychic)', Lightning: 'var(--lightning)', Metal: 'var(--metal)',
  Darkness: 'var(--darkness)', Colorless: 'var(--colorless)', Fighting: '#d98a4e',
};

export default function Decks() {
  useOfficial();  // re-render when the official-data toggle flips / loads
  const [meta, setMeta] = useState([]);
  const [sets, setSets] = useState([]);

  useEffect(() => {
    api.decks().then((r) => setMeta(r.meta || [])).catch(() => {});
    api.sets().then((r) => setSets(r.sets || [])).catch(() => {});
  }, []);

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Reference · Decks</div>
        <h1>Decks &amp; strategies</h1>
        <p className="sub">Every battle-ready archetype, its game plan, and its key cards. All decks are validated as exactly 60 cards under the 4-copy rule and span the implemented expansions below.</p>
      </div>

      {sets.length > 0 && (
        <div className="panel pad" style={{ marginBottom: 16 }}>
          <b style={{ fontFamily: 'var(--display)' }}>Sets in the card pool</b>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
            {sets.map((s) => (
              <span key={s.code} className="set-chip">
                <Star kind="set" id={s.code} />
                <b style={{ marginLeft: 6 }}>{s.name}</b><span className="mono"> · {s.code} · {s.cards} cards</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="deck-grid">
        {meta.map((d) => {
          const thumb = officialImageFor({ name: d.key_cards?.[0] }) || d.image;
          return (
          <div className="panel pad deck-card" key={d.id}>
            <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
              {thumb && (
                <img className="deck-thumb" src={thumb} alt={d.id}
                  onError={(e) => { e.currentTarget.style.display = 'none'; }} />
              )}
              <div style={{ flex: 1 }}>
                <div className="row between">
                  <div className="deck-name">{d.id.replace(/_/g, ' ')}</div>
                  <Star kind="deck" id={d.id} />
                </div>
                <div className="row" style={{ gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                  {d.type && <span className="type-tag" style={{ '--tc': TYPE_COLOR[d.type] || 'var(--muted)' }}>{d.type}</span>}
                  <span className="tag">{d.archetype}</span>
                </div>
              </div>
            </div>
            <p className="deck-strategy">{d.strategy}</p>
            {d.key_cards?.length > 0 && (
              <div className="keycards">
                <span className="kc-label">Key cards</span>
                {d.key_cards.map((c) => <span key={c} className="pill">{c}</span>)}
              </div>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}

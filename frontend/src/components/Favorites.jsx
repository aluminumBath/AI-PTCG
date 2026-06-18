import { useEffect, useState } from 'react';
import { api } from '../api';
import { useFavorites, Star, cardMeta } from '../favorites';

const TYPE_VAR = {
  Fire: 'var(--fire)', Water: 'var(--water)', Grass: 'var(--grass)',
  Psychic: 'var(--psychic)', Lightning: 'var(--lightning)', Metal: 'var(--metal)',
  Darkness: 'var(--darkness)', Colorless: 'var(--colorless)',
};

export default function Favorites({ onLaunch }) {
  const { favs } = useFavorites();
  const [deckMeta, setDeckMeta] = useState([]);
  const [sets, setSets] = useState([]);

  useEffect(() => {
    api.decks().then((r) => setDeckMeta(r.meta || [])).catch(() => {});
    api.sets().then((r) => setSets(r.sets || [])).catch(() => {});
  }, []);

  const favDecks = (favs.decks || []).map((id) => deckMeta.find((d) => d.id === id) || { id });
  const favSets = (favs.sets || []).map((code) => sets.find((s) => s.code === code) || { code, name: code });
  const favCards = (favs.cards || []).map((id) => ({ id, ...(cardMeta(id) || {}) }));

  const empty = !favDecks.length && !favSets.length && !favCards.length;

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">You · Favorites</div>
        <h1>Your battle kit</h1>
        <p className="sub">Decks, cards, and sets you've starred. Favorited decks are pinned to the top of every deck picker and can jump straight into battle from here.</p>
      </div>

      {empty && (
        <div className="panel pad">
          <p className="sub" style={{ margin: 0 }}>
            Nothing starred yet. Tap the ☆ on a deck (in <b>Decks</b>), a card (in <b>Card explorer</b>),
            or a set to add it here — your favorites then sit ready at the top of every deck picker.
          </p>
        </div>
      )}

      {favDecks.length > 0 && (
        <section style={{ marginBottom: 22 }}>
          <div className="row between" style={{ alignItems: 'baseline' }}>
            <h2 className="sec-title">Decks <span className="count">{favDecks.length}</span></h2>
          </div>
          <div className="deck-grid">
            {favDecks.map((d) => (
              <div className="panel pad deck-card" key={d.id}>
                <div className="row between" style={{ alignItems: 'flex-start' }}>
                  <div className="row" style={{ gap: 10 }}>
                    {d.image && <img className="deck-thumb" src={d.image} alt={d.id}
                      onError={(e) => { e.target.style.display = 'none'; }} />}
                    <div>
                      <div className="deck-name">{d.id.replace(/_/g, ' ')}</div>
                      {d.archetype && <div className="deck-arch">{d.archetype}</div>}
                    </div>
                  </div>
                  <Star kind="deck" id={d.id} />
                </div>
                {d.strategy && <p className="deck-strategy">{d.strategy}</p>}
                <div className="row" style={{ gap: 8, marginTop: 10 }}>
                  <button className="btn primary sm" onClick={() => onLaunch?.('play', d.id)}>Play vs AI</button>
                  <button className="btn sm" onClick={() => onLaunch?.('watch', d.id)}>Watch</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {favCards.length > 0 && (
        <section style={{ marginBottom: 22 }}>
          <h2 className="sec-title">Cards <span className="count">{favCards.length}</span></h2>
          <div className="cards">
            {favCards.map((c) => (
              <div className="cardx" key={c.id}>
                <div className="cardx-img">
                  {c.image
                    ? <img src={c.image} alt={c.name || c.id} loading="lazy"
                        onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                    : <div className="empty-slot" style={{ width: '100%', aspectRatio: '5/7' }}><span>{c.id}</span></div>}
                  <span className="card-star"><Star kind="card" id={c.id} /></span>
                </div>
                <div className="meta"><div className="nm">{c.name || c.id}</div></div>
              </div>
            ))}
          </div>
        </section>
      )}

      {favSets.length > 0 && (
        <section>
          <h2 className="sec-title">Sets <span className="count">{favSets.length}</span></h2>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            {favSets.map((s) => (
              <span key={s.code} className="set-chip">
                <Star kind="set" id={s.code} />
                <b style={{ marginLeft: 6 }}>{s.name}</b>
                {s.cards != null && <span className="mono"> · {s.cards} cards</span>}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

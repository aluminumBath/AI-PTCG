import { useEffect, useState } from 'react';
import { api } from '../api';

export default function CardExplorer() {
  const [q, setQ] = useState('');
  const [cards, setCards] = useState([]);
  const [source, setSource] = useState('');
  const [loading, setLoading] = useState(false);

  async function search(query) {
    setLoading(true);
    try {
      const r = await api.cards(query);
      setCards(r.data || []);
      setSource(r.source || '');
    } catch (e) { setCards([]); }
    finally { setLoading(false); }
  }
  useEffect(() => { search(''); }, []);

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Reference · Standard</div>
        <h1>Card explorer</h1>
        <p className="sub">Browse the latest Standard-legal cards pulled live from the official Pokémon TCG database. Cards here are reference data; the battle engine plays the implemented archetypes.</p>
      </div>

      <div className="panel pad" style={{ marginBottom: 16 }}>
        <div className="row">
          <input className="grow" placeholder="Search by name (e.g. Charizard)…" value={q}
            onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && search(q)} />
          <button className="btn primary" onClick={() => search(q)}>Search</button>
          {source && <span className="tag">source · {source}</span>}
        </div>
      </div>

      {loading ? (
        <div className="panel pad"><span className="live"><span className="spin" /> loading cards…</span></div>
      ) : (
        <div className="cards">
          {cards.map((c) => (
            <div className="cardx" key={c.id}>
              {c.image
                ? <img src={c.image} alt={c.name} loading="lazy" />
                : <div className="empty-slot" style={{ width: '100%', aspectRatio: '5/7' }}>{c.name}</div>}
              <div className="meta">
                <div className="nm">{c.name}</div>
                <div className="st">{c.set || c.supertype}{c.hp ? ` · ${c.hp} HP` : ''}</div>
              </div>
            </div>
          ))}
          {cards.length === 0 && <div className="panel pad sub">No cards found.</div>}
        </div>
      )}
    </div>
  );
}

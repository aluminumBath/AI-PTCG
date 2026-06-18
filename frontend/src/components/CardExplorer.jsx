import { useEffect, useState } from 'react';
import { api } from '../api';
import ImageDisclaimer from './ImageDisclaimer';

function CardTile({ card, onChanged }) {
  const [src, setSrc] = useState(card.image || '');
  const [broken, setBroken] = useState(false);
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(card.image || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const overridden = card.image_overridden;
  const missing = !src || broken;

  async function save() {
    setErr('');
    if (!/^https?:\/\//.test(val.trim())) { setErr('Must start with http:// or https://'); return; }
    setBusy(true);
    try {
      await api.setCardImage(card.id, val.trim());
      setSrc(val.trim()); setBroken(false); setEditing(false);
      onChanged && onChanged();
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  async function clear() {
    setBusy(true);
    try { await api.clearCardImage(card.id); setEditing(false); onChanged && onChanged(); }
    finally { setBusy(false); }
  }

  return (
    <div className="cardx">
      <div className="cardx-img">
        {!missing
          ? <img src={src} alt={card.name} loading="lazy" onError={() => setBroken(true)} />
          : <div className="empty-slot" style={{ width: '100%', aspectRatio: '5/7' }}>
              <span>image missing</span>
            </div>}
        <button className="img-edit" title="Edit image link" onClick={() => { setEditing(!editing); setVal(src); }}>✎</button>
        {overridden && <span className="img-flag" title="Custom image">custom</span>}
      </div>
      <div className="meta">
        <div className="nm">{card.name}</div>
        <div className="st">{card.set || card.supertype}{card.hp ? ` · ${card.hp} HP` : ''}</div>
      </div>
      {editing && (
        <div className="img-editor">
          <input className="input" placeholder="https://… image URL" value={val}
            onChange={(e) => setVal(e.target.value)} />
          {err && <div className="err sm">{err}</div>}
          <div className="row" style={{ gap: 6, marginTop: 6 }}>
            <button className="btn primary xs" onClick={save} disabled={busy}>Save</button>
            {overridden && <button className="btn ghost xs" onClick={clear} disabled={busy}>Reset</button>}
            <button className="btn ghost xs" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CardExplorer() {
  const [q, setQ] = useState('');
  const [cards, setCards] = useState([]);
  const [source, setSource] = useState('');
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState(null);

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
  useEffect(() => { api.sources().then(setSources).catch(() => {}); }, []);

  return (
    <div>
      <ImageDisclaimer />
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
            <CardTile key={c.id} card={c} onChanged={() => search(q)} />
          ))}
          {cards.length === 0 && <div className="panel pad sub">No cards found.</div>}
        </div>
      )}

      {sources && (
        <div className="panel pad" style={{ marginTop: 16 }}>
          <b style={{ fontFamily: 'var(--display)' }}>Official sources</b>
          <div className="row" style={{ marginTop: 10, gap: 10 }}>
            {sources.links?.map((l) => (
              <a key={l.url} className="btn ghost sm" href={l.url} target="_blank" rel="noreferrer">{l.label} ↗</a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

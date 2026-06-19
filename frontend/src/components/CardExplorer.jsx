import { useEffect, useState } from 'react';
import { api } from '../api';
import ImageDisclaimer from './ImageDisclaimer';
import { Star, rememberCard } from '../favorites';
import { officialImageFor, officialMetaFor, searchOfficial, officialCount, useOfficial } from '../officialData';

function CardTile({ card, onChanged, onOpen }) {
  const [src, setSrc] = useState(card.image || '');
  const [broken, setBroken] = useState(false);
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(card.image || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const overridden = card.image_overridden;
  // For official catalog entries (from searchOfficial) the card already carries
  // its own id-based image + metadata, so use them directly. For our normal
  // cards, override by name when the toggle is on (unless a custom image is set).
  const om = card.official ? null : officialMetaFor(card);
  const offSrc = card.official ? null : (!overridden ? officialImageFor(card) : null);
  const shown = card.official ? (card.image || src) : (offSrc || src);
  const dispName = card.official ? card.name : (om?.name || card.name);
  const dispSet = card.official
    ? (card.set || card.supertype || '')
    : ((om && (om.expansion || om.category)) || card.set || card.supertype);
  const dispHp = card.official ? card.hp : ((om && om.hp) || card.hp);
  const missing = !shown || broken;
  // Official catalog entries have full detail (attacks, weakness…) in the DB.
  const canOpen = card.official && onOpen;
  const open = () => canOpen && onOpen(card.id);

  // remember name/image so the Favorites tab can render this card by id later
  useEffect(() => { if (card.id) rememberCard(card); }, [card.id]);
  useEffect(() => { setBroken(false); }, [shown]);

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
          ? <img src={shown} alt={dispName} loading="lazy" onError={() => setBroken(true)}
              onClick={open} style={canOpen ? { cursor: 'pointer' } : undefined} />
          : <div className="empty-slot" style={{ width: '100%', aspectRatio: '5/7', cursor: canOpen ? 'pointer' : 'default' }} onClick={open}>
              <span>image missing</span>
            </div>}
        <button className="img-edit" title="Edit image link" onClick={() => { setEditing(!editing); setVal(src); }}>✎</button>
        {overridden && <span className="img-flag" title="Custom image">custom</span>}
        {card.id && <span className="card-star"><Star kind="card" id={card.id} /></span>}
      </div>
      <div className="meta">
        <div className="nm" onClick={open} style={canOpen ? { cursor: 'pointer' } : undefined}
          title={canOpen ? 'View attacks & details' : undefined}>{dispName}</div>
        <div className="st">{dispSet}{dispHp ? ` · ${dispHp} HP` : ''}</div>
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

function Pips({ label, value }) {
  if (!value) return null;
  return <span className="tag" style={{ fontSize: 12 }}>{label}: {value}</span>;
}

// Detail view for an official card — fetches attacks + battle stats from the DB.
function OfficialCardModal({ id, onClose }) {
  const [card, setCard] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    if (id == null) return;
    setCard(null); setErr('');
    api.officialCard(id).then(setCard).catch((e) => setErr(e.message || 'not found'));
  }, [id]);
  if (id == null) return null;
  const img = `${api.base}/api/official/cards/${id}/image`;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="row" style={{ gap: 8, alignItems: 'baseline' }}>
              <h2 style={{ margin: 0, fontFamily: 'var(--display)' }}>{card?.name || 'Card'}</h2>
              {card?.expansion && <span className="tag">{card.expansion}{card.collection_no ? ` · ${card.collection_no}` : ''}</span>}
            </div>
            <div className="mono sub" style={{ fontSize: 12, marginTop: 4 }}>Card ID {id}</div>
          </div>
          <button className="btn ghost sm" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {err && <div className="err">{err}</div>}
          {!card && !err && <span className="live"><span className="spin" /> loading…</span>}
          {card && (
            <div className="row" style={{ gap: 18, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <img src={img} alt={card.name} onError={(e) => { e.currentTarget.style.display = 'none'; }}
                style={{ width: 200, maxWidth: '40%', borderRadius: 10, border: '1px solid var(--line)' }} />
              <div style={{ flex: 1, minWidth: 220 }}>
                <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                  {card.stage && <span className="tag">{card.stage}</span>}
                  {card.category && <span className="tag">{card.category}</span>}
                  {card.type && <Pips label="Type" value={card.type} />}
                  {card.hp && <Pips label="HP" value={card.hp} />}
                </div>
                <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
                  <Pips label="Weakness" value={card.weakness} />
                  <Pips label="Resistance" value={card.resistance} />
                  <Pips label="Retreat" value={card.retreat} />
                </div>
                {card.moves && card.moves.length > 0 ? (
                  <>
                    <h4 style={{ margin: '0 0 8px' }}>Attacks &amp; abilities</h4>
                    {card.moves.map((m, i) => (
                      <div key={i} className="panel pad" style={{ marginBottom: 8 }}>
                        <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                          <b>{m.cost ? `${m.cost} ` : ''}{m.name}</b>
                          {m.damage && <span className="tag">{m.damage}</span>}
                        </div>
                        {m.effect && <div className="sub" style={{ marginTop: 4 }}>{m.effect}</div>}
                      </div>
                    ))}
                  </>
                ) : <div className="sub">No attack text recorded for this card.</div>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CardExplorer() {
  const official = useOfficial();  // re-render grid when official data toggles/loads
  const [q, setQ] = useState('');
  const [cards, setCards] = useState([]);
  const [source, setSource] = useState('');
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState(null);
  const [detailId, setDetailId] = useState(null);

  async function search(query) {
    // When the official-data toggle is on, browse the official catalog (loaded
    // client-side from public/assets) instead of the live card API.
    if (official.enabled && official.ready) {
      setCards(searchOfficial(query));
      setSource(`official · ${officialCount()} cards`);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const r = await api.cards(query);
      setCards(r.data || []);
      setSource(r.source || '');
    } catch (e) { setCards([]); }
    finally { setLoading(false); }
  }
  // Re-query on mount and whenever the official toggle flips or finishes loading.
  useEffect(() => { search(q); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [official.enabled, official.ready]);
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
            <CardTile key={c.id} card={c} onChanged={() => search(q)} onOpen={setDetailId} />
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

      <OfficialCardModal id={detailId} onClose={() => setDetailId(null)} />
    </div>
  );
}

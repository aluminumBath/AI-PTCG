import { useEffect, useState } from 'react';
import { api } from '../api';

export default function DeckImport({ onImported }) {
  const [name, setName] = useState('My deck');
  const [text, setText] = useState('');
  const [catalog, setCatalog] = useState([]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.cardsCatalog()
      .then((r) => { setCatalog(r.cards || []); if (!text) setText(r.sample_decklist || ''); })
      .catch(() => {});
  }, []);

  async function doImport() {
    setBusy(true); setResult(null);
    try { setResult(await api.importDeck(name, text)); }
    catch (e) { setResult({ ok: false, errors: [e.message], unknown: [], warnings: [] }); }
    finally { setBusy(false); }
  }

  function loadSample() {
    api.cardsCatalog().then((r) => setText(r.sample_decklist || ''));
  }

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Build · Import</div>
        <h1>Import a deck</h1>
        <p className="sub">Paste a decklist in the Pokémon TCG Live export format (or <span style={{ fontFamily: 'var(--mono)' }}>count name</span> per line). The importer maps it onto the engine's implemented cards — anything not yet implemented is flagged so you know why a list isn't battle-ready. Valid decks become selectable in Watch and Play modes.</p>
      </div>

      <div className="row" style={{ alignItems: 'stretch', gap: 16 }}>
        <div className="panel pad grow" style={{ minWidth: 320 }}>
          <label className="field">Deck name
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field" style={{ marginTop: 12 }}>Decklist
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={16}
              style={{ fontFamily: 'var(--mono)', fontSize: 12.5, resize: 'vertical', lineHeight: 1.6 }} />
          </label>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" onClick={doImport} disabled={busy}>
              {busy ? <span className="spin" /> : 'Import deck'}
            </button>
            <button className="btn ghost" onClick={loadSample}>Load sample</button>
          </div>

          {result && (
            <div style={{ marginTop: 16 }}>
              {result.ok ? (
                <div className="banner">
                  <span className="winner" style={{ fontSize: 16 }}>Imported — {result.total} cards ✓</span>
                  <p className="sub" style={{ marginTop: 6 }}>
                    "{result.name}" is now selectable in Watch and Play modes.
                  </p>
                </div>
              ) : (
                <div className="err" style={{ fontFamily: 'var(--body)' }}>
                  Couldn't import this list ({result.total} parsed).
                </div>
              )}
              {result.unknown?.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div className="nav-label" style={{ padding: '6px 0' }}>Not yet implemented</div>
                  {result.unknown.map((u, i) => <div key={i} className="tag" style={{ marginRight: 6 }}>{u}</div>)}
                </div>
              )}
              {result.errors?.length > 0 && result.errors.map((e, i) => <div key={i} className="err">{e}</div>)}
              {result.warnings?.length > 0 && result.warnings.map((w, i) => (
                <div key={i} style={{ color: 'var(--warn)', fontFamily: 'var(--mono)', fontSize: 12, marginTop: 6 }}>⚠ {w}</div>
              ))}
            </div>
          )}
        </div>

        <div className="panel pad" style={{ width: 280, flex: 'none' }}>
          <b style={{ fontFamily: 'var(--display)' }}>Battle-ready cards</b>
          <p className="sub" style={{ fontSize: 12, marginTop: 4 }}>The importer recognises these.</p>
          <div className="log" style={{ maxHeight: 420, marginTop: 8 }}>
            {catalog.map((c) => (
              <div className="ln" key={c.name}>
                {c.name}<span className="t" style={{ marginLeft: 8 }}>{c.category}{c.hp ? ` · ${c.hp}` : ''}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

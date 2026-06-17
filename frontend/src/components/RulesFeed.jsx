import { useEffect, useState } from 'react';
import { api } from '../api';

export default function RulesFeed() {
  const [data, setData] = useState(null);
  const [sources, setSources] = useState(null);

  useEffect(() => {
    api.rules().then(setData).catch(() => setData(null));
    api.sources().then(setSources).catch(() => setSources(null));
  }, []);

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Reference · Rules</div>
        <h1>Official rules feed</h1>
        <p className="sub">The rules the engine enforces, grouped by phase — a living checklist of rule fidelity. Every match in Watch, Play, and the Model Arena runs under these.</p>
      </div>

      {!data ? (
        <div className="panel pad"><span className="live"><span className="spin" /> loading rules…</span></div>
      ) : (
        <>
          <div className="row" style={{ marginBottom: 16 }}>
            <span className="pill">{data.count} rules enforced</span>
            <span className="tag">{data.groups.length} phases</span>
          </div>

          <div className="rules-grid">
            {data.groups.map((g) => (
              <div className="panel pad" key={g.group}>
                <div className="rules-head">{g.group}</div>
                {g.items.map((it, i) => (
                  <div className="rule" key={i}>
                    <div className="rule-name"><span className="rule-check">✓</span>{it.rule}</div>
                    <div className="rule-detail">{it.detail}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>

          {data.notes?.length > 0 && (
            <div className="panel pad" style={{ marginTop: 16 }}>
              <div className="rules-head">Documented simplifications</div>
              {data.notes.map((n, i) => (
                <div className="rule-detail" key={i} style={{ marginTop: 6 }}>• {n}</div>
              ))}
            </div>
          )}

          {sources && (
            <div className="panel pad" style={{ marginTop: 16 }}>
              <div className="rules-head">Sources & attribution</div>
              <p className="rule-detail" style={{ marginTop: 6 }}>{sources.disclaimer}</p>
              <div className="row" style={{ marginTop: 12, gap: 10 }}>
                {sources.links?.map((l) => (
                  <a key={l.url} className="btn ghost sm" href={l.url} target="_blank" rel="noreferrer">{l.label} ↗</a>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

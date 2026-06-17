const TYPE_VAR = {
  Fire: 'var(--fire)', Water: 'var(--water)', Grass: 'var(--grass)',
  Psychic: 'var(--psychic)', Lightning: 'var(--lightning)', Metal: 'var(--metal)',
  Darkness: 'var(--darkness)', Colorless: 'var(--colorless)',
};

function sideAccent(player) {
  const t = player?.active?.types?.[0];
  return TYPE_VAR[t] || 'var(--colorless)';
}

function Gauge({ remaining, max }) {
  const p = Math.max(0, Math.min(1, max ? remaining / max : 0));
  return (
    <div className="gauge" style={{ '--p': p }}>
      <b>{Math.round(p * 100)}</b>
    </div>
  );
}

function Poke({ poke, isActive }) {
  if (!poke) {
    return <div className="empty-slot">empty</div>;
  }
  const name = poke.name.replace(/ ex$/, '');
  const isEx = poke.rule_box;
  return (
    <div className={`card-poke ${isActive ? 'act' : ''}`}>
      <div className="nm">
        {name}{isEx && <span className="ex"> {poke.rule_box}</span>}
      </div>
      <div className="hpwrap">
        <Gauge remaining={poke.remaining_hp} max={poke.hp} />
        <div className="hp-meta">
          <div><span className="big">{poke.remaining_hp}</span> / {poke.hp}</div>
          <div>HP</div>
        </div>
      </div>
      <div className="energy-row">
        {(poke.energy_types || []).map((t, i) => (
          <span key={i} className={`pip ${t}`} title={t} />
        ))}
      </div>
      {poke.status?.length > 0 && (
        <div className="statuses">
          {poke.status.map((s) => <span key={s} className={`status ${s}`}>{s}</span>)}
        </div>
      )}
    </div>
  );
}

export default function Board({ player, activeTurn, flip }) {
  const accent = sideAccent(player);
  const taken = player.prizes_taken || 0;
  return (
    <div className={`side ${activeTurn ? 'active-turn' : ''}`} style={{ '--side-accent': accent }}>
      <div className="side-head">
        <div className="side-name"><span className="chip" />{player.name}</div>
        <div className="row" style={{ gap: 14 }}>
          <span className="tag">hand {player.hand_count}</span>
          <span className="tag">deck {player.deck_count}</span>
          <div className="prizes" title={`${6 - taken} prizes left`}>
            {Array.from({ length: 6 }).map((_, i) => (
              <span key={i} className={`prize ${i < taken ? 'taken' : ''}`} />
            ))}
          </div>
        </div>
      </div>
      <div className="field-grid" style={{ direction: flip ? 'rtl' : 'ltr' }}>
        <div style={{ direction: 'ltr' }}>
          <Poke poke={player.active} isActive />
        </div>
        <div className="bench" style={{ direction: 'ltr' }}>
          {player.bench.length === 0 && <div className="empty-slot">no bench</div>}
          {player.bench.map((b) => <Poke key={b.uid} poke={b} />)}
        </div>
      </div>
    </div>
  );
}

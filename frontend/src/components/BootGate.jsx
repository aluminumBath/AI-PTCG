import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

// Vite serves files in /public at BASE_URL; the image lives at
// public/assets/pokeball.png.
const BALL = `${import.meta.env.BASE_URL}assets/pokeball.png`;

/**
 * Gates the whole app on backend availability. Render's free tier puts the
 * service to sleep when idle, so the first request after inactivity can take
 * 30–60s while it cold-starts. We poll /api/health and only render the app once
 * it answers. A short grace period avoids flashing the screen on warm loads.
 */
export default function BootGate({ children }) {
  const [ready, setReady] = useState(false);
  const [show, setShow] = useState(false);   // reveal the waking screen after a grace period
  const [elapsed, setElapsed] = useState(0);
  const done = useRef(false);

  useEffect(() => {
    const start = Date.now();
    const grace = setTimeout(() => { if (!done.current) setShow(true); }, 1200);
    const ticker = setInterval(() => setElapsed(Math.round((Date.now() - start) / 1000)), 1000);

    async function ping() {
      if (done.current) return;
      try {
        const ctrl = new AbortController();
        const to = setTimeout(() => ctrl.abort(), 8000);
        const res = await fetch(`${api.base}/api/health`, { signal: ctrl.signal, cache: 'no-store' });
        clearTimeout(to);
        if (res.ok) {
          const j = await res.json().catch(() => null);
          if (j && j.ok) {
            done.current = true;
            clearTimeout(grace);
            clearInterval(ticker);
            setReady(true);
            return;
          }
        }
      } catch {
        /* backend asleep or a network blip — keep retrying */
      }
      if (!done.current) setTimeout(ping, 2500);
    }
    ping();

    return () => { done.current = true; clearTimeout(grace); clearInterval(ticker); };
  }, []);

  if (ready) return children;
  if (!show) return null;  // brief blank during the fast initial check (warm starts feel instant)

  const slow = elapsed >= 6;
  return (
    <div className="boot">
      <div className="boot-card">
        <img className="boot-ball" src={BALL} alt="" draggable="false" />
        <h1 className="boot-title">{slow ? 'Waking the server…' : 'Connecting…'}</h1>
        <p className="boot-sub">
          {slow
            ? 'The free hosting tier sleeps when idle, so the battle server is spinning back up. This usually takes 30–60 seconds — thanks for your patience.'
            : 'Reaching the battle server.'}
        </p>
        <div className="boot-bar"><span className="boot-bar-fill" /></div>
        <div className="boot-elapsed">{elapsed}s elapsed</div>
      </div>
    </div>
  );
}

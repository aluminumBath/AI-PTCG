import { useEffect, useState } from 'react';
import { api } from '../api';

// Shown at the top of any view that displays Pokémon/card imagery.
export default function ImageDisclaimer() {
  const [text, setText] = useState(
    'Pokémon and all card images are © The Pokémon Company / Nintendo / Game Freak / Creatures Inc. We claim no ownership; shown for reference only.'
  );
  useEffect(() => {
    api.sources().then((r) => r.disclaimer && setText(r.disclaimer)).catch(() => {});
  }, []);
  return (
    <div className="disclaimer" role="note">
      <span className="disclaimer-mark">©</span>
      <span>{text}</span>
    </div>
  );
}

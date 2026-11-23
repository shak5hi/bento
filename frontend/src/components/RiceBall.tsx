import onigiri from '../assets/onigiri.png';
import './RiceBall.css';

interface Props {
  /** Pixel size of the rice ball. */
  size?: number;
  /** Shown under the rice ball and read by screen readers. */
  label?: string;
  /** Centre it in the whole viewport (page loads). */
  fullscreen?: boolean;
}

/** Bento's loading indicator: the onigiri from the logo pops in and spins. */
export function RiceBall({ size = 48, label = 'Loading', fullscreen = false }: Props) {
  return (
    <div className={`riceball${fullscreen ? ' riceball-screen' : ''}`} role="status" aria-live="polite">
      <img src={onigiri} alt="" width={size} height={size} className="riceball-img" draggable={false} />
      {label && <span className={size < 24 ? 'sr-only' : 'riceball-label'}>{label}</span>}
    </div>
  );
}

/** Tiny spinning rice ball for buttons that are busy. */
export function RiceBallInline() {
  return <img src={onigiri} alt="" width={16} height={16} className="riceball-img riceball-inline" draggable={false} />;
}

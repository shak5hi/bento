import { useId, useRef, useState } from 'react';

export interface Point {
  t: string;
  v: number | null;
}

interface Props {
  points: Point[];
  height?: number;
  /** Fixed y-range, e.g. [0, 100] for health scores. Defaults to 0..max. */
  domain?: [number, number];
  format: (v: number) => string;
  formatTime?: (t: string) => string;
  label: string;
  color?: string;
}

const defaultTime = (t: string) =>
  new Date(t).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

/** Single-series line: 2px stroke, faint area, end marker, recessive grid, crosshair tooltip. */
export function LineChart({ points, height = 120, domain, format, formatTime = defaultTime, label, color = 'var(--ink)' }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const gradientId = useId();

  const values = points.map((p) => p.v).filter((v): v is number => v !== null);
  if (points.length < 2 || values.length < 2) {
    return (
      <div className="chart-empty" style={{ height }}>
        Not enough data yet — the line appears after a few readings.
      </div>
    );
  }

  const [lo, hi] = domain ?? [0, Math.max(...values) * 1.15 || 1];
  const W = 1000;
  const H = 100;
  const x = (i: number) => (i / (points.length - 1)) * W;
  const y = (v: number) => H - ((v - lo) / (hi - lo || 1)) * H;

  const segments: string[] = [];
  let current = '';
  points.forEach((p, i) => {
    if (p.v === null) {
      if (current) segments.push(current);
      current = '';
      return;
    }
    current += `${current ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p.v).toFixed(1)}`;
  });
  if (current) segments.push(current);
  const line = segments.join('');
  const firstIdx = points.findIndex((p) => p.v !== null);
  const lastIdx = points.length - 1 - [...points].reverse().findIndex((p) => p.v !== null);
  const area = `${line}L${x(lastIdx)} ${H}L${x(firstIdx)} ${H}Z`;
  const last = points[lastIdx];

  const onMove = (e: React.PointerEvent) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const i = Math.round(((e.clientX - rect.left) / rect.width) * (points.length - 1));
    setHover(Math.max(0, Math.min(points.length - 1, i)));
  };

  const hp = hover !== null ? points[hover] : null;
  const pct = (i: number) => `${(i / (points.length - 1)) * 100}%`;
  const ypct = (v: number) => `${(y(v) / H) * 100}%`;

  return (
    <div
      ref={ref}
      className="chart"
      style={{ height }}
      onPointerMove={onMove}
      onPointerLeave={() => setHover(null)}
      role="img"
      aria-label={`${label}. Latest ${last.v !== null ? format(last.v) : 'no data'}.`}
    >
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.10" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.5, 1].map((f) => (
          <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="var(--line)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        ))}
        <path d={area} fill={`url(#${gradientId})`} />
        <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      </svg>

      {last.v !== null && hover === null && (
        <span className="chart-dot" style={{ left: pct(lastIdx), top: ypct(last.v), background: color }} />
      )}

      {hp && hover !== null && (
        <>
          <span className="chart-crosshair" style={{ left: pct(hover) }} />
          {hp.v !== null && <span className="chart-dot" style={{ left: pct(hover), top: ypct(hp.v), background: color }} />}
          <div className={`chart-tip ${hover > points.length / 2 ? 'left' : ''}`} style={{ left: pct(hover) }}>
            <strong>{hp.v !== null ? format(hp.v) : 'No data'}</strong>
            <span>{formatTime(hp.t)}</span>
          </div>
        </>
      )}
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, api, type PublicStatus } from '../lib/api';
import { STATUS_LABEL, timeAgo } from '../lib/format';
import { LineChart } from '../components/LineChart';
import { RiceBall } from '../components/RiceBall';
import logoSrc from '../assets/logo.png';
import './Dashboard.css';
import './StatusPage.css';

const KIND = { latency: 'Slow responses', errors: 'Errors' } as const;

function duration(from: string, to: string): string {
  const m = Math.max(1, Math.round((new Date(to).getTime() - new Date(from).getTime()) / 60000));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
}

function uptimeText(v: number | null): string {
  if (v === null) return '—';
  return `${v >= 99.995 ? '100' : v.toFixed(2)}%`;
}

function uptimeClass(v: number | null): string {
  if (v === null) return '';
  return v >= 99.5 ? 's-healthy' : v >= 95 ? 's-degraded' : 's-critical';
}

/** Public, read-only status page at /status/:slug. No login, no code findings. */
export default function StatusPage() {
  const { slug = '' } = useParams();
  const [data, setData] = useState<PublicStatus | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await api<PublicStatus>(`/public/status/${encodeURIComponent(slug)}`);
      setData(d);
      setMissing(false);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setMissing(true);
      else setError(err instanceof ApiError ? err.message : 'Could not load this status page.');
    }
  }, [slug]);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    document.title = data ? `${data.name} status · Bento` : 'Status · Bento';
  }, [data]);

  const live = data ? data.openIncidents.length : 0;

  return (
    <div className="dash status-page">
      <header className="topbar">
        <Link to="/" className="brand">
          <img src={logoSrc} alt="Bento" className="brand-logo" />
        </Link>
        <span className="muted small">Public status page</span>
      </header>

      <main className="sp-main">
        {missing && (
          <section className="sp-missing">
            <p className="eyebrow">Status</p>
            <h1 className="sp-title">This status page isn't available.</h1>
            <p className="muted">It doesn't exist, or its owner has made it private.</p>
            <Link to="/" className="btn">Go to Bento</Link>
          </section>
        )}

        {error && !data && <div className="notice notice-crit" role="alert">{error}</div>}
        {!data && !missing && !error && <RiceBall label="Loading status" />}

        {data && (
          <>
            <section className="sp-hero">
              <div>
                <p className="eyebrow">Status</p>
                <h1 className="sp-title">{data.name}</h1>
                <p className={`sp-banner ${live ? 'is-live' : data.status === 'unknown' ? 'is-wait' : 'is-ok'}`} role="status">
                  {live
                    ? `${live} ongoing incident${live > 1 ? 's' : ''}`
                    : data.status === 'unknown'
                      ? 'Collecting the first measurements'
                      : 'All systems operational'}
                </p>
              </div>
              <div className="sp-score">
                <span className="sp-score-num">{data.health ?? '—'}</span>
                <span className="label">Health score</span>
                <span className={`status-text s-${data.status}`}>{STATUS_LABEL[data.status]}</span>
              </div>
            </section>

            <section className="sp-card">
              <div className="d-head">
                <h2 className="sp-h">Uptime</h2>
                <span className="muted small">
                  {data.monitoredEndpoints} monitored endpoint{data.monitoredEndpoints === 1 ? '' : 's'}
                </span>
              </div>
              <dl className="sp-uptime">
                {(['24h', '7d', '30d'] as const).map((k) => (
                  <div key={k}>
                    <dt>Last {k === '24h' ? '24 hours' : k === '7d' ? '7 days' : '30 days'}</dt>
                    <dd className={uptimeClass(data.uptime[k])}>{uptimeText(data.uptime[k])}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="sp-card">
              <div className="d-head">
                <h2 className="sp-h">Response time</h2>
                <span className="muted small">p95 latency, last 24 hours</span>
              </div>
              <LineChart
                points={data.latency.map((p) => ({ t: p.t, v: p.p95 }))}
                height={140}
                format={(v) => `${Math.round(v)} ms p95`}
                formatTime={(t) => new Date(t).toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' })}
                label="p95 latency over the last 24 hours"
              />
            </section>

            <section className="sp-card">
              <h2 className="sp-h">Ongoing incidents</h2>
              {data.openIncidents.length === 0 ? (
                <p className="muted small sp-empty">No ongoing incidents.</p>
              ) : (
                <ul className="rows">
                  {data.openIncidents.map((i) => (
                    <li key={`${i.host}-${i.openedAt}`} className="row">
                      <span className="sev sev-critical">{KIND[i.kind]}</span>
                      <span className="row-main">{i.host}</span>
                      <span className="muted">since {timeAgo(i.openedAt)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="sp-card">
              <h2 className="sp-h">Recently resolved</h2>
              {data.resolvedIncidents.length === 0 ? (
                <p className="muted small sp-empty">Nothing in the last 30 days.</p>
              ) : (
                <ul className="rows">
                  {data.resolvedIncidents.map((i) => (
                    <li key={`${i.host}-${i.openedAt}`} className="row">
                      <span className="sev sev-low">{KIND[i.kind]}</span>
                      <span className="row-main">{i.host}</span>
                      <span className="muted">
                        {timeAgo(i.closedAt)} · lasted {duration(i.openedAt, i.closedAt)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <footer className="sp-foot muted small">
              <span>Updated {timeAgo(data.updatedAt)}</span>
              <span>
                Monitored by <Link to="/">Bento</Link>
              </span>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}

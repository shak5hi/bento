import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api, type LatencyPoint, type ProjectDetail } from '../../lib/api';
import { SEVERITY_LABEL, STATUS_LABEL, effort, host, timeAgo } from '../../lib/format';
import { LineChart } from '../../components/LineChart';
import { RiceBall } from '../../components/RiceBall';

interface Props {
  projectId: string;
  onClose: () => void;
  onChanged: () => void;
}

const PARTS = [
  { key: 'uptime', label: 'Uptime', max: 40 },
  { key: 'latency', label: 'Latency', max: 20 },
  { key: 'errors', label: 'Errors', max: 20 },
  { key: 'code', label: 'Code', max: 20 },
] as const;

const EP_STATE = { normal: 'Normal', failing: 'Failing', incident: 'Incident', pending: 'First probe soon' } as const;

export function ProjectDrawer({ projectId, onClose, onChanged }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<ProjectDetail | null>(null);
  const [latency, setLatency] = useState<LatencyPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newUrl, setNewUrl] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [d, l] = await Promise.all([
        api<ProjectDetail>(`/projects/${projectId}`),
        api<{ points: LatencyPoint[] }>(`/projects/${projectId}/latency?minutes=60`),
      ]);
      setData(d);
      setLatency(l.points);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load this project.');
    }
  }, [projectId]);

  useEffect(() => {
    ref.current?.showModal();
    load();
    const id = window.setInterval(load, 10_000);
    return () => window.clearInterval(id);
  }, [load]);

  const run = async (key: string, fn: () => Promise<unknown>, message?: string) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      if (message) setToast(message);
      await load();
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That did not work. Please try again.');
    } finally {
      setBusy(null);
    }
  };

  const addEndpoint = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl.trim()) return;
    run('add', async () => {
      await api(`/projects/${projectId}/endpoints`, { method: 'POST', body: { url: newUrl.trim() } });
      setNewUrl('');
    }, 'Endpoint added — first probe within a minute.');
  };

  const remove = async () => {
    if (!data || !window.confirm(`Delete ${data.project.name}? Its history, findings and incidents go with it.`)) return;
    setBusy('delete');
    try {
      await api(`/projects/${projectId}`, { method: 'DELETE' });
      onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete the project.');
      setBusy(null);
    }
  };

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(id);
  }, [toast]);

  const p = data?.project;
  const openIncidents = data?.incidents.filter((i) => i.status === 'open') ?? [];
  const pastIncidents = data?.incidents.filter((i) => i.status === 'closed').slice(0, 5) ?? [];

  return (
    <dialog ref={ref} className="drawer" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <div className="drawer-inner">
        <header className="drawer-head">
          <div>
            <p className="eyebrow">Project</p>
            <h2>{p?.name ?? <>&nbsp;</>}</h2>
            {p?.repoUrl && (
              <a className="drawer-link" href={p.repoUrl} target="_blank" rel="noreferrer">
                {host(p.repoUrl)} ↗
              </a>
            )}
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </header>

        {error && <div className="notice notice-crit" role="alert">{error}</div>}
        {toast && <div className="notice" role="status">{toast}</div>}

        {!data && !error && <RiceBall label="Loading project" />}

        {data && p && (
          <>
            <section className="d-section d-score">
              <div className="d-score-num">
                <span className="big">{p.health ?? '—'}</span>
                <span className={`status-text s-${p.status}`}>{STATUS_LABEL[p.status]}</span>
                {p.parts?.basis === 'code' && <span className="muted small">Scored on code only — add an endpoint for live health.</span>}
              </div>
              <div className="bars">
                {PARTS.map(({ key, label, max }) => {
                  const v = p.parts?.[key] ?? null;
                  return (
                    <div className="bar" key={key}>
                      <span>{label}</span>
                      <span className="track">
                        <span className={`fill ${v === null ? '' : v / max >= 0.8 ? 'f-healthy' : v / max >= 0.5 ? 'f-degraded' : 'f-critical'}`} style={{ width: `${v === null ? 0 : (v / max) * 100}%` }} />
                      </span>
                      <span className="num">{v === null ? '—' : `${Math.round(v * 10) / 10}/${max}`}</span>
                    </div>
                  );
                })}
              </div>
            </section>

            {data.advice && (
              <section className="pickle pickle-sm">
                <p className="pickle-label">Pickle</p>
                <p className="pickle-text">{data.advice.brief}</p>
                {data.advice.recommendations.length > 0 && (
                  <ol className="recs">
                    {data.advice.recommendations.map((r, i) => (
                      <li key={i}>
                        <strong>{r.title}</strong>
                        {r.why && <span>{r.why}</span>}
                        {effort(r.effort_minutes) && <em>{effort(r.effort_minutes)}</em>}
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            )}

            {openIncidents.length > 0 && (
              <section className="d-section">
                <h3>Live incidents</h3>
                <ul className="rows">
                  {openIncidents.map((i) => (
                    <li key={i.id} className="row">
                      <span className="sev sev-critical">{i.kind === 'latency' ? 'Slow' : 'Errors'}</span>
                      <span className="row-main">{host(i.url)}</span>
                      <span className="muted">
                        {i.kind === 'latency'
                          ? `${Math.round(i.peak ?? 0)} ms vs ${Math.round(i.baseline ?? 0)} ms`
                          : `${Math.round((i.peak ?? 0) * 100)}% failing`}{' '}
                        · since {timeAgo(i.openedAt)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="d-section">
              <div className="d-head">
                <h3>Endpoints</h3>
                <span className="muted small">p95 latency, last hour</span>
              </div>
              <LineChart
                points={latency.map((pt) => ({ t: pt.t, v: pt.p95 }))}
                height={96}
                format={(v) => `${Math.round(v)} ms p95`}
                formatTime={(t) => new Date(t).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                label="p95 latency over the last hour"
              />
              <ul className="rows">
                {data.endpoints.map((e) => (
                  <li key={e.id} className="row">
                    <span className={`ep-state ep-${e.state}`}>{EP_STATE[e.state]}</span>
                    <span className="row-main" title={e.url}>{host(e.url)}</span>
                    <span className="muted">
                      {e.lastStatus ?? (e.state === 'pending' ? '' : 'no response')}
                      {e.lastLatencyMs !== null && ` · ${e.lastLatencyMs} ms`}
                    </span>
                    <button
                      className="row-x"
                      aria-label={`Stop monitoring ${e.url}`}
                      disabled={busy === e.id}
                      onClick={() => run(e.id, () => api(`/endpoints/${e.id}`, { method: 'DELETE' }), 'Endpoint removed.')}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
              <form className="inline-form" onSubmit={addEndpoint}>
                <input type="url" placeholder="https://api.example.com/health" value={newUrl} onChange={(e) => setNewUrl(e.target.value)} aria-label="Endpoint URL" />
                <button className="btn" disabled={busy === 'add' || !newUrl.trim()}>Add</button>
              </form>
            </section>

            <section className="d-section">
              <div className="d-head">
                <h3>Code findings</h3>
                <span className="muted small">
                  {p.repoUrl ? `Last scan ${timeAgo(p.lastScanAt)}${p.lastScanSha ? ` · ${p.lastScanSha.slice(0, 7)}` : ''}` : 'No repository connected'}
                </span>
              </div>
              {p.lastScanError && (
                <p className="scan-error small" role="status">
                  Last scan failed: {p.lastScanError}
                </p>
              )}
              {data.findings.length === 0 ? (
                <p className="muted small">{p.repoUrl ? (p.lastScanAt ? 'The latest scan found nothing to fix.' : p.lastScanError ? 'No successful scan yet.' : 'First scan in progress…') : 'Add a repository to scan dependencies, tests, CI and secrets.'}</p>
              ) : (
                <ul className="findings">
                  {data.findings.map((f) => (
                    <li key={f.id}>
                      <span className={`sev sev-${f.severity}`}>{SEVERITY_LABEL[f.severity]}</span>
                      <div>
                        <strong>{f.title}</strong>
                        {f.detail && <p>{f.detail}</p>}
                      </div>
                      {effort(f.effortMinutes) && <span className="muted small">{effort(f.effortMinutes)}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {pastIncidents.length > 0 && (
              <section className="d-section">
                <h3>Resolved incidents</h3>
                <ul className="rows">
                  {pastIncidents.map((i) => (
                    <li key={i.id} className="row">
                      <span className="sev sev-low">{i.kind}</span>
                      <span className="row-main">{host(i.url)}</span>
                      <span className="muted">{timeAgo(i.closedAt)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <footer className="drawer-foot">
              {p.repoUrl && (
                <button className="btn" disabled={busy === 'scan'} onClick={() => run('scan', () => api(`/projects/${projectId}/scan`, { method: 'POST' }), 'Scan queued.')}>
                  {busy === 'scan' ? 'Queuing…' : 'Scan now'}
                </button>
              )}
              <button className="btn btn-danger" disabled={busy === 'delete'} onClick={remove}>Delete project</button>
            </footer>
          </>
        )}
      </div>
    </dialog>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api, type LatencyPoint, type ProjectDetail } from '../../lib/api';
import { SEVERITY_LABEL, STATUS_LABEL, effort, host, timeAgo } from '../../lib/format';
import { LineChart } from '../../components/LineChart';
import { RiceBall, RiceBallInline } from '../../components/RiceBall';

interface Props {
  projectId: string;
  onClose: () => void;
  onChanged: () => void;
}

const CARD_ORDER = ['security', 'website', 'basics', 'upkeep'] as const;

const EP_STATE = { normal: 'Normal', failing: 'Failing', incident: 'Incident', pending: 'First check soon' } as const;

type Finding = ProjectDetail['findings'][number];

/** Under a finding: the fix button, or where its pull request is. Bento never merges. */
function FixAction({ finding, busy, onFix }: { finding: Finding; busy: boolean; onFix: () => void }) {
  const fix = finding.fix;
  if (fix?.status === 'open' && fix.prUrl) {
    return (
      <a className="fix-link" href={fix.prUrl} target="_blank" rel="noreferrer">
        PR #{fix.prNumber} open ↗
      </a>
    );
  }
  if (fix?.status === 'queued' || busy) {
    return <span className="fix-pending"><RiceBallInline />Opening a pull request…</span>;
  }
  if (fix?.status === 'merged' && fix.prUrl) {
    return (
      <a className="fix-link" href={fix.prUrl} target="_blank" rel="noreferrer">
        PR #{fix.prNumber} merged ↗ <span className="muted">· resolves on the next scan</span>
      </a>
    );
  }
  if (!finding.fixable) return null;
  return (
    <span className="fix-row">
      {fix?.status === 'failed' && fix.error && <span className="fix-error">Last attempt failed: {fix.error}</span>}
      <button type="button" className="btn btn-sm" onClick={onFix}>
        {fix?.status === 'failed' ? 'Try again' : 'Fix with a pull request'}
      </button>
    </span>
  );
}

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
    }, 'Website added. The first check runs within a minute.');
  };

  const remove = async () => {
    if (!data || !window.confirm(`Delete ${data.project.name}? Its history and problems go with it.`)) return;
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

  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setToast(`${what} copied.`);
    } catch {
      setError('Could not copy. Select the text and copy it yourself.');
    }
  };

  const p = data?.project;
  const origin = window.location.origin;
  const publicUrl = p?.publicSlug ? `${origin}/status/${p.publicSlug}` : null;
  const badgeUrl = p?.publicSlug ? `${origin}/api/badge/${p.publicSlug}.svg` : null;
  const badgeMarkdown = publicUrl && badgeUrl ? `[![Bento health](${badgeUrl})](${publicUrl})` : '';
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
                {p.grade && <span className={`grade g-${p.grade}`}>Grade {p.grade}</span>}
                <span className={`status-text s-${p.status}`}>{STATUS_LABEL[p.status]}</span>
                {p.weekChange != null && p.weekChange !== 0 && (
                  <span className={`small ${p.weekChange > 0 ? 'up' : 'down'}`}>
                    {p.weekChange > 0 ? '▲' : '▼'} {Math.abs(p.weekChange)} this week
                  </span>
                )}
              </div>
              <div className="cards">
                {CARD_ORDER.map((key) => {
                  const c = p.cards?.[key];
                  if (!c) return null;
                  return (
                    <div className="card" key={key} title={c.items.map((i) => i.label).join(' · ')}>
                      <span className="card-label">{c.label}</span>
                      <span className={`card-grade ${c.grade ? `g-${c.grade}` : 'g-none'}`}>{c.grade ?? '—'}</span>
                      <span className="card-summary">{c.summary}</span>
                    </div>
                  );
                })}
              </div>
            </section>

            {(p.nextAction || p.capped) && (
              <section className="d-section next-action">
                {p.nextAction && (
                  <p>
                    <span className="label">Do this next</span>
                    {p.nextAction.title}
                    {p.nextAction.gain ? <strong> +{p.nextAction.gain} points</strong> : null}
                  </p>
                )}
                {p.capped && <p className="muted small">{p.capped}.</p>}
              </section>
            )}

            {data.history.length > 0 && (
              <section className="d-section">
                <h3>Score history</h3>
                <ul className="rows">
                  {data.history.slice(0, 6).map((h) => (
                    <li key={h.at} className="row">
                      <span className={h.previous === null || h.total >= h.previous ? 'up' : 'down'}>
                        {h.previous === null ? h.total : `${h.previous} → ${h.total}`}
                      </span>
                      <span className="row-main" title={h.reason}>{h.reason}</span>
                      <span className="muted">{timeAgo(h.at)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

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
                <h3>Happening now</h3>
                <ul className="rows">
                  {openIncidents.map((i) => (
                    <li key={i.id} className="row">
                      <span className="sev sev-critical">{i.kind === 'latency' ? 'Slow' : 'Failing'}</span>
                      <span className="row-main">{host(i.url)}</span>
                      <span className="muted">
                        {i.kind === 'latency'
                          ? `${Math.round(i.peak ?? 0)} ms instead of about ${Math.round(i.baseline ?? 0)} ms`
                          : `${Math.round((i.peak ?? 0) * 100)}% of checks failing`}{' '}
                        · since {timeAgo(i.openedAt)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="d-section">
              <div className="d-head">
                <h3>Websites</h3>
                <span className="muted small">How fast it answers, last hour</span>
              </div>
              <LineChart
                points={latency.map((pt) => ({ t: pt.t, v: pt.p95 }))}
                height={96}
                format={(v) => `${Math.round(v)} ms`}
                formatTime={(t) => new Date(t).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                label="How fast the website answered over the last hour"
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
                      onClick={() => run(e.id, () => api(`/endpoints/${e.id}`, { method: 'DELETE' }), 'Website removed.')}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
              <form className="inline-form" onSubmit={addEndpoint}>
                <input type="url" placeholder="https://api.example.com/health" value={newUrl} onChange={(e) => setNewUrl(e.target.value)} aria-label="Endpoint URL" />
                <button className="btn" disabled={busy === 'add' || !newUrl.trim()}>{busy === 'add' ? <><RiceBallInline />Adding…</> : 'Add'}</button>
              </form>
            </section>

            <section className="d-section">
              <div className="d-head">
                <h3>Problems in the code</h3>
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
                        <FixAction
                          finding={f}
                          busy={busy === `fix-${f.id}`}
                          onFix={() =>
                            run(
                              `fix-${f.id}`,
                              () => api(`/projects/${projectId}/findings/${f.id}/fix`, { method: 'POST' }),
                              'Bento is opening a pull request. It appears here in a few seconds.',
                            )
                          }
                        />
                      </div>
                      {effort(f.effortMinutes) && <span className="muted small">{effort(f.effortMinutes)}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {pastIncidents.length > 0 && (
              <section className="d-section">
                <h3>Fixed site problems</h3>
                <ul className="rows">
                  {pastIncidents.map((i) => (
                    <li key={i.id} className="row">
                      <span className="sev sev-low">{i.kind === 'latency' ? 'Was slow' : 'Was failing'}</span>
                      <span className="row-main">{host(i.url)}</span>
                      <span className="muted">{timeAgo(i.closedAt)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="d-section">
              <div className="d-head">
                <h3 id="public-label">Public status page</h3>
                <button
                  type="button"
                  role="switch"
                  aria-checked={p.isPublic}
                  aria-labelledby="public-label"
                  className={`switch${p.isPublic ? ' on' : ''}`}
                  disabled={busy === 'public'}
                  onClick={() =>
                    run(
                      'public',
                      () => api(`/projects/${projectId}/public`, { method: 'PUT', body: { enabled: !p.isPublic } }),
                      p.isPublic ? 'Status page is private again.' : 'Status page is public.',
                    )
                  }
                >
                  <span />
                </button>
              </div>
              <p className="muted small public-note">
                {p.isPublic
                  ? 'Anyone with the link sees the health score and whether the website is up and fast. Problems in your code always stay private.'
                  : 'Off. Turn it on to share whether your website is up and fast, and to get a README badge. Problems in your code are never shown.'}
              </p>
              {publicUrl && badgeUrl && (
                <div className="public-share">
                  <label className="share-row">
                    <span className="label">Page</span>
                    <input readOnly value={publicUrl} onFocus={(e) => e.target.select()} />
                    <a className="btn" href={publicUrl} target="_blank" rel="noreferrer">Open ↗</a>
                  </label>
                  <label className="share-row">
                    <span className="label">Badge</span>
                    <input readOnly value={badgeMarkdown} onFocus={(e) => e.target.select()} />
                    <button type="button" className="btn" onClick={() => copy(badgeMarkdown, 'Badge Markdown')}>Copy</button>
                  </label>
                  <img className="badge-preview" src={badgeUrl} alt={`Bento health badge for ${p.name}`} height={20} />
                </div>
              )}
            </section>

            <footer className="drawer-foot">
              {p.repoUrl && (
                <button className="btn" disabled={busy === 'scan'} onClick={() => run('scan', () => api(`/projects/${projectId}/scan`, { method: 'POST' }), 'Scan queued.')}>
                  {busy === 'scan' ? <><RiceBallInline />Queuing…</> : 'Scan now'}
                </button>
              )}
              <button className="btn btn-danger" disabled={busy === 'delete'} onClick={remove}>{busy === 'delete' ? <><RiceBallInline />Deleting…</> : 'Delete project'}</button>
            </footer>
          </>
        )}
      </div>
    </dialog>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError, api, auth, type Dashboard as DashboardData, type ProjectSummary, type SystemHealth, type Task } from '../lib/api';
import { STATUS_LABEL, effort, firstName, greeting, timeAgo } from '../lib/format';
import { LineChart } from '../components/LineChart';
import { ProjectDrawer } from './dashboard/ProjectDrawer';
import { NewProjectDialog } from './dashboard/NewProjectDialog';
import './Dashboard.css';

const REFRESH_MS = 15_000;

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [system, setSystem] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openProject, setOpenProject] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([
        api<DashboardData>('/dashboard'),
        api<SystemHealth>('/system').catch(() => null),
      ]);
      setData(d);
      setSystem(s);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load your workspace.');
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(() => document.visibilityState === 'visible' && load(), REFRESH_MS);
    return () => window.clearInterval(id);
  }, [load]);

  return (
    <div className="dash">
      <TopBar data={data} system={system} onNew={() => setCreating(true)} />

      <main className="dash-main">
        {error && !data && (
          <div className="notice notice-crit" role="alert">
            {error} <button onClick={load}>Retry</button>
          </div>
        )}
        {!data && !error && <Skeleton />}

        {data && data.projects.length === 0 && <EmptyState name={firstName(data.user.name, data.user.email)} onNew={() => setCreating(true)} />}

        {data && data.projects.length > 0 && (
          <>
            {error && <div className="notice">Showing the last data we have — {error.toLowerCase()}</div>}
            <Hero data={data} />
            <div className="dash-grid">
              <div className="dash-col">
                <Today tasks={data.today} total={data.portfolio.openFindings + data.portfolio.openIncidents} onOpen={setOpenProject} />
                <Projects projects={data.projects} onOpen={setOpenProject} />
              </div>
              <aside className="dash-col">
                <Activity items={data.activity} />
                <SystemPanel system={system} />
              </aside>
            </div>
          </>
        )}
      </main>

      {openProject && (
        <ProjectDrawer projectId={openProject} onClose={() => setOpenProject(null)} onChanged={load} />
      )}
      {creating && (
        <NewProjectDialog
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false);
            load();
            setOpenProject(id);
          }}
        />
      )}
    </div>
  );
}

/* ───────────────────────── top bar ───────────────────────── */

function TopBar({ data, system, onNew }: { data: DashboardData | null; system: SystemHealth | null; onNew: () => void }) {
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenu(false);
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [menu]);

  const signOut = () => {
    auth.clear();
    navigate('/login', { replace: true });
  };

  const initials = data ? firstName(data.user.name, data.user.email).slice(0, 1).toUpperCase() : '·';
  const live = system?.status === 'ok';

  return (
    <header className="topbar">
      <Link to="/dashboard" className="brand">
        <span className="mark">B</span>
        <span>Bento</span>
      </Link>

      <div className="topbar-right">
        <span className={`live ${system ? (live ? 'is-ok' : 'is-warn') : ''}`} title={system ? 'Monitoring pipeline status' : undefined}>
          <i />
          {system ? (live ? 'Monitoring live' : 'Monitoring degraded') : 'Connecting…'}
        </span>
        <button className="btn btn-primary" onClick={onNew}>
          New project
        </button>
        <div className="menu" ref={menuRef}>
          <button className="avatar" onClick={() => setMenu((m) => !m)} aria-haspopup="menu" aria-expanded={menu} aria-label="Account">
            {initials}
          </button>
          {menu && data && (
            <div className="menu-pop" role="menu">
              <div className="menu-head">
                <strong>{data.user.name || firstName(null, data.user.email)}</strong>
                <span>{data.user.email}</span>
              </div>
              <button role="menuitem" onClick={signOut}>Sign out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

/* ───────────────────────── hero: Q1 health + Q5 trend + Pickle brief ───────────────────────── */

function Hero({ data }: { data: DashboardData }) {
  const { portfolio, user } = data;
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
  const trend = portfolio.trend.map((p) => ({ t: p.t, v: p.health }));
  const delta = trend.length >= 2 ? (trend[trend.length - 1].v ?? 0) - (trend[0].v ?? 0) : null;

  return (
    <section className="hero">
      <div className="hero-left">
        <p className="eyebrow">{today}</p>
        <h1 className="hero-title">
          {greeting()}, <b>{firstName(user.name, user.email)}.</b>
        </h1>
        <div className="pickle">
          <p className="pickle-label">Pickle · daily brief</p>
          <p className="pickle-text">{data.brief}</p>
        </div>
      </div>

      <div className="health-card">
        <div className="health-head">
          <p className="label">Portfolio health</p>
          <span className={`status-text s-${statusOf(portfolio.health)}`}>{portfolio.label}</span>
        </div>
        <div className="health-number">
          {portfolio.health ?? '—'}
          <span>/100</span>
        </div>
        <div className="health-trend">
          {trend.length >= 2 ? (
            <>
              <LineChart
                points={trend}
                height={84}
                domain={[0, 100]}
                format={(v) => `${Math.round(v)} health`}
                label="Portfolio health over the last 14 days"
                color="var(--accent)"
              />
              <p className="health-trend-note">
                {delta === 0 ? 'Flat' : `${delta! > 0 ? '+' : ''}${delta}`} over the last 14 days
              </p>
            </>
          ) : (
            <p className="health-trend-note">The 14-day trend line appears once Bento has a few hours of history.</p>
          )}
        </div>
        <dl className="health-stats">
          <div><dt>Projects</dt><dd>{portfolio.projects}</dd></div>
          <div><dt>Need attention</dt><dd>{portfolio.needsAttention}</dd></div>
          <div><dt>Live incidents</dt><dd className={portfolio.openIncidents ? 'is-crit' : ''}>{portfolio.openIncidents}</dd></div>
        </dl>
      </div>
    </section>
  );
}

function statusOf(health: number | null) {
  if (health === null) return 'unknown';
  return health >= 80 ? 'healthy' : health >= 50 ? 'degraded' : 'critical';
}

/* ───────────────────────── Q3 + Q4: biggest risk, three tasks ───────────────────────── */

function Today({ tasks, total, onOpen }: { tasks: Task[]; total: number; onOpen: (id: string) => void }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>What deserves your attention today</h2>
        {total > tasks.length && <span className="section-meta">{tasks.length} of {total} · ranked by Pickle</span>}
      </div>

      {tasks.length === 0 ? (
        <div className="calm">
          <p className="calm-title">Nothing needs you right now.</p>
          <p>Every monitored endpoint is within its normal range and the latest scans came back clean.</p>
        </div>
      ) : (
        <ol className="tasks">
          {tasks.map((t, i) => (
            <li key={t.id}>
              <button className="task" onClick={() => onOpen(t.projectId)}>
                <span className="task-n">{String(i + 1).padStart(2, '0')}</span>
                <span className="task-body">
                  {i === 0 && <span className="task-flag">Biggest risk</span>}
                  <span className="task-title">{t.title}</span>
                  {t.detail && <span className="task-detail">{t.detail}</span>}
                  <span className="task-meta">
                    <span>{t.projectName}</span>
                    <span className={`sev sev-${t.severity}`}>{t.kind === 'incident' ? 'Live incident' : t.severity}</span>
                    {effort(t.effortMinutes) && <span>{effort(t.effortMinutes)}</span>}
                  </span>
                </span>
                <span className="task-go" aria-hidden="true">→</span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/* ───────────────────────── Q2: which projects need attention ───────────────────────── */

function Projects({ projects, onOpen }: { projects: ProjectSummary[]; onOpen: (id: string) => void }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>Projects</h2>
        <span className="section-meta">Worst first</span>
      </div>
      <ul className="projects">
        {projects.map((p) => (
          <li key={p.id}>
            <button className="project" onClick={() => onOpen(p.id)}>
              <span className="project-name">
                {p.name}
                <span className="project-sub">
                  {p.endpoints} endpoint{p.endpoints === 1 ? '' : 's'}
                  {p.repoUrl ? ` · scanned ${timeAgo(p.lastScanAt)}` : ' · no repository'}
                </span>
              </span>
              <span className="project-health">
                <span className="track"><span className={`fill f-${p.status}`} style={{ width: `${p.health ?? 0}%` }} /></span>
                <span className="project-score">{p.health ?? '—'}</span>
              </span>
              <span className={`status-text s-${p.status}`}>
                {STATUS_LABEL[p.status]}
                {p.basis === 'code' && p.health !== null && <em> · code only</em>}
              </span>
              <span className="project-counts">
                {p.openIncidents > 0 && <span className="sev sev-critical">{p.openIncidents} incident{p.openIncidents > 1 ? 's' : ''}</span>}
                {p.openFindings > 0 && <span>{p.openFindings} finding{p.openFindings > 1 ? 's' : ''}</span>}
                {p.openIncidents === 0 && p.openFindings === 0 && <span className="muted">Clear</span>}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ───────────────────────── side column ───────────────────────── */

function Activity({ items }: { items: DashboardData['activity'] }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>Recent activity</h2>
      </div>
      {items.length === 0 ? (
        <p className="muted small">Scans, incidents and recoveries will show up here.</p>
      ) : (
        <ul className="activity">
          {items.map((a, i) => (
            <li key={i} className={`act act-${a.kind}`}>
              <span className="act-dot" />
              <div>
                <p className="act-title">
                  {a.title}
                  {a.projectName && <span> · {a.projectName}</span>}
                </p>
                {a.body && <p className="act-body">{a.body}</p>}
                <time className="act-time">{timeAgo(a.at)}</time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SystemPanel({ system }: { system: SystemHealth | null }) {
  if (!system) return null;
  const jobs = system.queues['probe.jobs'];
  const workers = Object.entries(system.workers);
  return (
    <section className="section system">
      <div className="section-head">
        <h2>Pipeline</h2>
        <span className={`status-text ${system.status === 'ok' ? 's-healthy' : 's-degraded'}`}>
          {system.status === 'ok' ? 'All running' : 'Degraded'}
        </span>
      </div>
      <ul className="workers">
        {workers.map(([name, w]) => (
          <li key={name}>
            <span className={`wdot ${w.status === 'ok' ? 'ok' : 'down'}`} />
            {name}
            <span className="muted">{w.instances > 1 ? `×${w.instances}` : w.status === 'ok' ? '' : 'down'}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">
        {jobs ? `${jobs.waiting} probe job${jobs.waiting === 1 ? '' : 's'} waiting · ` : ''}
        {system.alerts.sent} alert{system.alerts.sent === 1 ? '' : 's'} sent, {system.alerts.suppressed} duplicate
        {system.alerts.suppressed === 1 ? '' : 's'} suppressed · advisor circuit {system.advisorCircuit}
      </p>
    </section>
  );
}

/* ───────────────────────── states ───────────────────────── */

function EmptyState({ name, onNew }: { name: string; onNew: () => void }) {
  return (
    <section className="empty">
      <p className="eyebrow">Welcome, {name}</p>
      <h1 className="hero-title">
        Every project deserves <b>a place at the table.</b>
      </h1>
      <p className="empty-lede">
        Add a project and Bento starts watching it straight away: uptime and latency from the endpoints you list, code health from
        its repository. Pickle turns all of it into a short list of what to do next.
      </p>
      <ol className="steps">
        <li><span>01</span><div><strong>Connect your project</strong><p>A name, a public repository, and the URLs you care about.</p></div></li>
        <li><span>02</span><div><strong>Bento builds a health profile</strong><p>Probes every minute, scans the code, learns what normal looks like.</p></div></li>
        <li><span>03</span><div><strong>You get priorities, not noise</strong><p>Three things worth your time today — never a wall of alerts.</p></div></li>
      </ol>
      <button className="btn btn-primary btn-lg" onClick={onNew}>Add your first project</button>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading your workspace">
      <div className="sk sk-title" />
      <div className="sk sk-block" />
      <div className="sk-row">
        <div className="sk sk-card" />
        <div className="sk sk-card" />
      </div>
    </div>
  );
}

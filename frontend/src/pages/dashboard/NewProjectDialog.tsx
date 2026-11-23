import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, api, type GitHubRepo, type GitHubStatus } from '../../lib/api';

interface Props {
  onClose: () => void;
  onCreated: (projectId: string) => void;
  /** Called after a multi-repo import (no single project to open). */
  onImported?: (count: number) => void;
}

type Tab = 'github' | 'manual';

export function NewProjectDialog({ onClose, onCreated, onImported }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<Tab>('github');
  const [github, setGithub] = useState<GitHubStatus | null>(null);

  useEffect(() => {
    ref.current?.showModal();
    api<GitHubStatus>('/github/status')
      .then((s) => {
        setGithub(s);
        if (!s.configured) setTab('manual');
      })
      .catch(() => setTab('manual'));
  }, []);

  return (
    <dialog ref={ref} className="dialog dialog-wide" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <div className="dialog-body">
        <p className="eyebrow">New project</p>
        <h2 className="dialog-title">Connect a project</h2>

        {github?.configured && (
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'github'} className={tab === 'github' ? 'on' : ''} onClick={() => setTab('github')}>
              From GitHub
            </button>
            <button role="tab" aria-selected={tab === 'manual'} className={tab === 'manual' ? 'on' : ''} onClick={() => setTab('manual')}>
              Enter manually
            </button>
          </div>
        )}

        {tab === 'github' && github?.configured ? (
          <GitHubImport status={github} onClose={onClose} onCreated={onCreated} onImported={onImported} />
        ) : (
          <ManualForm onClose={onClose} onCreated={onCreated} />
        )}
      </div>
    </dialog>
  );
}

/* ───────────── GitHub ───────────── */

function GitHubImport({ status, onClose, onCreated, onImported }: Props & { status: GitHubStatus }) {
  const [repos, setRepos] = useState<GitHubRepo[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const connected = status.installations.length > 0;

  useEffect(() => {
    if (!connected) return;
    api<{ repos: GitHubRepo[] }>('/github/repos')
      .then((r) => setRepos(r.repos))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load your repositories.'));
  }, [connected]);

  const connect = async (kind: 'installUrl' | 'authorizeUrl') => {
    setBusy(true);
    try {
      const urls = await api<{ installUrl: string; authorizeUrl: string }>('/github/connect', { method: 'POST' });
      window.location.assign(urls[kind]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach GitHub.');
      setBusy(false);
    }
  };

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (repos ?? []).filter((r) => !q || r.fullName.toLowerCase().includes(q));
  }, [repos, query]);

  const toggle = (name: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

  const importRepos = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ projects: { id: string }[] }>('/github/import', { method: 'POST', body: { repos: [...picked] } });
      if (res.projects.length === 1) onCreated(res.projects[0].id);
      else onImported?.(res.projects.length);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Import failed.');
      setBusy(false);
    }
  };

  if (!connected) {
    return (
      <>
        <p className="dialog-lede">
          Give Bento access to your GitHub repositories — public or private. Bento scans each one on every push, and if a repo
          lists a website, it starts monitoring that too.
        </p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => connect('installUrl')}>
            {busy ? 'Opening GitHub…' : 'Connect GitHub'}
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <p className="dialog-lede">
        Pick the repositories Bento should watch. Connected as{' '}
        <b>{status.login ?? status.installations.map((i) => i.account).join(', ')}</b> ·{' '}
        <button type="button" className="linklike" onClick={() => connect('installUrl')}>Change repository access</button>
      </p>

      <input className="repo-search" placeholder="Search repositories" value={query} onChange={(e) => setQuery(e.target.value)} />

      <ul className="repo-list" aria-busy={repos === null}>
        {repos === null && !error && <li className="muted small repo-empty">Loading your repositories…</li>}
        {repos !== null && visible.length === 0 && (
          <li className="muted small repo-empty">{repos.length === 0 ? 'Bento has no repositories yet — use “Change repository access”.' : 'No matches.'}</li>
        )}
        {visible.map((r) => {
          const added = Boolean(r.projectId);
          return (
            <li key={r.fullName}>
              <label className={`repo ${added ? 'repo-added' : ''}`}>
                <input type="checkbox" disabled={added} checked={added || picked.has(r.fullName)} onChange={() => toggle(r.fullName)} />
                <span className="repo-main">
                  <span className="repo-name">
                    {r.fullName}
                    {r.private && <span className="pill">Private</span>}
                    {added && <span className="pill pill-quiet">Added</span>}
                  </span>
                  <span className="repo-meta">
                    {[r.language, r.homepage && `monitors ${r.homepage.replace(/^https?:\/\//, '')}`].filter(Boolean).join(' · ') || r.description || ' '}
                  </span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>

      {error && <p className="form-error" role="alert">{error}</p>}

      <div className="dialog-actions">
        <button type="button" className="btn" onClick={onClose}>Cancel</button>
        <button type="button" className="btn btn-primary" disabled={busy || picked.size === 0} onClick={importRepos}>
          {busy ? 'Importing…' : picked.size > 1 ? `Import ${picked.size} projects` : 'Import project'}
        </button>
      </div>
    </>
  );
}

/* ───────────── manual ───────────── */

function ManualForm({ onClose, onCreated }: Pick<Props, 'onClose' | 'onCreated'>) {
  const [name, setName] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [endpoints, setEndpoints] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ project: { id: string } }>('/projects', {
        method: 'POST',
        body: {
          name,
          repo_url: repoUrl.trim() || null,
          endpoints: endpoints.split(/\s+/).map((u) => u.trim()).filter(Boolean),
        },
      });
      onCreated(res.project.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the project.');
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="dialog-form">
      <p className="dialog-lede">Bento starts probing the endpoints within a minute and scans the repository straight away.</p>

      <label className="field">
        <span>Name</span>
        <input autoFocus required maxLength={120} placeholder="GetMyHelp API" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="field">
        <span>Public repository <em>optional</em></span>
        <input type="url" placeholder="https://github.com/you/project" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} />
      </label>
      <label className="field">
        <span>Endpoints to monitor <em>one per line</em></span>
        <textarea
          rows={3}
          placeholder={'https://api.example.com/health\nhttps://example.com'}
          value={endpoints}
          onChange={(e) => setEndpoints(e.target.value)}
        />
      </label>

      {error && <p className="form-error" role="alert">{error}</p>}

      <div className="dialog-actions">
        <button type="button" className="btn" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={busy || !name.trim()}>
          {busy ? 'Adding…' : 'Add project'}
        </button>
      </div>
    </form>
  );
}

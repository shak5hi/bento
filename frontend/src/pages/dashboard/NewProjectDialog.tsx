import { useEffect, useRef, useState } from 'react';
import { ApiError, api } from '../../lib/api';

interface Props {
  onClose: () => void;
  onCreated: (projectId: string) => void;
}

export function NewProjectDialog({ onClose, onCreated }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [endpoints, setEndpoints] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

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
    <dialog ref={ref} className="dialog" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <form onSubmit={submit} className="dialog-body">
        <p className="eyebrow">New project</p>
        <h2 className="dialog-title">Connect a project</h2>
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
    </dialog>
  );
}

import { useEffect, useRef, useState } from 'react';
import { ApiError, api, type EmailSettings } from '../../lib/api';
import { RiceBall } from '../../components/RiceBall';

/** Incident alerts and the weekly digest, on or off. */
export function EmailSettingsDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<EmailSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    ref.current?.showModal();
    api<EmailSettings>('/me/email').then(setData, (err) =>
      setError(err instanceof ApiError ? err.message : 'Could not load your email settings.'),
    );
  }, []);

  const toggle = async (field: 'incidentEmails' | 'weeklyDigest') => {
    if (!data) return;
    setSaving(field);
    setError(null);
    try {
      setData(await api<EmailSettings>('/me/email', { method: 'PUT', body: { [field]: !data[field] } }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That did not save. Please try again.');
    } finally {
      setSaving(null);
    }
  };

  const rows = [
    { field: 'incidentEmails' as const, title: 'Incident alerts', text: 'An email when one of your sites goes down or slows right down, and when it recovers.' },
    { field: 'weeklyDigest' as const, title: 'Weekly digest', text: 'Monday morning: your health scores, what changed, and Pickle’s top 3 for the week.' },
  ];

  return (
    <dialog ref={ref} className="dialog" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <div className="dialog-body">
        <p className="eyebrow">Settings</p>
        <h2 className="dialog-title">Email</h2>
        {error && <p className="form-error" role="alert">{error}</p>}
        {!data && !error && <RiceBall label="Loading settings" />}
        {data && (
          <>
            <p className="dialog-lede">
              Sent to <strong>{data.email}</strong>. Every email has a one-click unsubscribe link.
            </p>
            {!data.deliverable && (
              <p className="notice">Your GitHub email is private, so Bento has no address to send to.</p>
            )}
            {!data.emailConfigured && (
              <p className="notice">Email isn’t set up on this Bento server yet, so nothing will be sent until it is.</p>
            )}
            <ul className="email-settings">
              {rows.map(({ field, title, text }) => (
                <li key={field}>
                  <div>
                    <strong id={`email-${field}`}>{title}</strong>
                    <span>{text}</span>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={data[field]}
                    aria-labelledby={`email-${field}`}
                    className={`switch${data[field] ? ' on' : ''}`}
                    disabled={saving === field}
                    onClick={() => toggle(field)}
                  >
                    <span />
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="dialog-actions">
          <button className="btn" onClick={onClose}>Done</button>
        </div>
      </div>
    </dialog>
  );
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 5) return 'Good evening';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export function firstName(name: string | null | undefined, email: string): string {
  const n = (name || '').trim().split(/\s+/)[0];
  return n || email.split('@')[0];
}

export function effort(minutes: number | null | undefined): string | null {
  if (!minutes) return null;
  return minutes < 60 ? `~${minutes} min` : `~${Math.round((minutes / 60) * 10) / 10} h`;
}

export function host(url: string): string {
  try {
    const u = new URL(url);
    return u.host + (u.pathname === '/' ? '' : u.pathname);
  } catch {
    return url;
  }
}

export const STATUS_LABEL = { healthy: 'Healthy', degraded: 'Needs attention', critical: 'At risk', unknown: 'Waiting for data' } as const;
/** Severity in words a student acts on. */
export const SEVERITY_LABEL = { critical: 'Fix now', high: 'Fix now', medium: 'This week', low: 'When you have time' } as const;

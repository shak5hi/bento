const TOKEN_KEY = 'bento.token';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const auth = {
  get token(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable: session lasts until reload */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Can't reach Bento right now. Check your connection and try again.");
  }

  if (res.status === 401 && auth.token) {
    auth.clear();
    window.location.assign('/login');
  }
  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'Something went wrong. Please try again.';
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

// ---------- types (mirror backend/services/api) ----------

export type Severity = 'critical' | 'high' | 'medium' | 'low';
export type Status = 'healthy' | 'degraded' | 'critical' | 'unknown';

export interface Task {
  id: string;
  kind: 'incident' | 'finding';
  projectId: string;
  projectName: string;
  severity: Severity;
  title: string;
  detail: string | null;
  effortMinutes: number | null;
  since: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  repoUrl: string | null;
  health: number | null;
  basis: 'full' | 'code' | null;
  status: Status;
  endpoints: number;
  openIncidents: number;
  openFindings: number;
  lastScanAt: string | null;
}

export interface Recommendation {
  title: string;
  why: string;
  effort_minutes: number;
  severity: Severity;
}

export interface Dashboard {
  user: { name: string | null; email: string };
  brief: string;
  portfolio: {
    health: number | null;
    label: string;
    projects: number;
    needsAttention: number;
    openIncidents: number;
    openFindings: number;
    trend: { t: string; health: number }[];
  };
  biggestRisk: Task | null;
  today: Task[];
  projects: ProjectSummary[];
  pickle: { projectId: string; brief: string; recommendations: Recommendation[]; generatedAt: string }[];
  activity: { kind: string; title: string; body: string | null; at: string; projectName: string | null }[];
}

export interface ProjectDetail {
  project: {
    id: string;
    name: string;
    repoUrl: string | null;
    lastScanAt: string | null;
    lastScanSha: string | null;
    lastScanError: string | null;
    health: number | null;
    status: Status;
    parts: { uptime: number | null; latency: number | null; errors: number | null; code: number; basis: string } | null;
  };
  endpoints: {
    id: string;
    url: string;
    intervalS: number;
    state: 'normal' | 'failing' | 'incident' | 'pending';
    lastStatus: number | null;
    lastLatencyMs: number | null;
    lastProbedAt: string | null;
  }[];
  findings: { id: string; severity: Severity; title: string; detail: string | null; effortMinutes: number | null; firstSeen: string }[];
  incidents: { id: string; url: string; kind: 'latency' | 'errors'; status: 'open' | 'closed'; baseline: number | null; peak: number | null; openedAt: string; closedAt: string | null }[];
  advice: { brief: string; recommendations: Recommendation[]; generatedAt: string } | null;
}

export interface LatencyPoint {
  t: string;
  p95: number | null;
  failures: number;
  total: number;
}

export interface SystemHealth {
  status: 'ok' | 'degraded';
  workers: Record<string, { instances: number; status: 'ok' | 'down' }>;
  queues: Record<string, { waiting: number; unacked: number }>;
  alerts: { sent: number; suppressed: number };
}

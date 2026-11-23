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

export type Grade = 'A' | 'B' | 'C' | 'D' | 'F';
export type CardKey = 'security' | 'website' | 'basics' | 'upkeep';

/** One report card (bento_core.scoring). Unmeasured cards say why instead of pretending to be perfect. */
export interface ScoreCard {
  key: CardKey;
  label: string;
  score: number | null;
  grade: Grade | null;
  state: 'measured' | 'not_monitored' | 'measuring' | 'not_checked';
  summary: string;
  items: { label: string; key?: string; severity?: Severity; done?: boolean; points?: number }[];
}

export interface NextAction {
  key: string;
  title: string;
  gain: number | null;
  effortMinutes: number | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  repoUrl: string | null;
  health: number | null;
  grade: Grade | null;
  weekChange: number | null;
  nextAction: NextAction | null;
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
    isPublic: boolean;
    publicSlug: string | null;
    health: number | null;
    status: Status;
    grade: Grade | null;
    basis: 'full' | 'code' | null;
    cards: Record<CardKey, ScoreCard> | null;
    nextAction: NextAction | null;
    capped: string | null;
    weekChange: number | null;
  };
  history: { at: string; total: number; previous: number | null; grade: Grade | null; reason: string }[];
  endpoints: {
    id: string;
    url: string;
    intervalS: number;
    state: 'normal' | 'failing' | 'incident' | 'pending';
    lastStatus: number | null;
    lastLatencyMs: number | null;
    lastProbedAt: string | null;
  }[];
  findings: {
    id: string;
    severity: Severity;
    title: string;
    detail: string | null;
    effortMinutes: number | null;
    firstSeen: string;
    /** Bento can open a pull request for this (GitHub-app projects only). */
    fixable: boolean;
    fix: { status: 'queued' | 'open' | 'merged' | 'closed' | 'failed'; prUrl: string | null; prNumber: number | null; error: string | null } | null;
  }[];
  incidents: { id: string; url: string; kind: 'latency' | 'errors'; status: 'open' | 'closed'; baseline: number | null; peak: number | null; openedAt: string; closedAt: string | null }[];
  advice: { brief: string; recommendations: Recommendation[]; generatedAt: string } | null;
}

export interface LatencyPoint {
  t: string;
  p95: number | null;
  failures: number;
  total: number;
}

/** GET /public/status/:slug — no findings or vulnerability details, by design. */
export interface PublicStatus {
  name: string;
  health: number | null;
  status: Status;
  basis: 'full' | 'code' | null;
  updatedAt: string | null;
  monitoredEndpoints: number;
  uptime: { '24h': number | null; '7d': number | null; '30d': number | null };
  latency: { t: string; p95: number | null }[];
  openIncidents: { kind: 'latency' | 'errors'; host: string; openedAt: string }[];
  resolvedIncidents: { kind: 'latency' | 'errors'; host: string; openedAt: string; closedAt: string }[];
}

export interface SystemHealth {
  status: 'ok' | 'degraded';
  workers: Record<string, { instances: number; status: 'ok' | 'down' }>;
  queues: Record<string, { waiting: number; unacked: number }>;
  alerts: { sent: number; suppressed: number };
}

// ---------- GitHub ----------

export interface GitHubStatus {
  configured: boolean;
  login: string | null;
  installations: { id: number; account: string; type: string | null }[];
}

export interface GitHubRepo {
  installationId: number;
  fullName: string;
  name: string;
  private: boolean;
  description: string | null;
  language: string | null;
  homepage: string | null;
  url: string;
  pushedAt: string | null;
  archived: boolean;
  projectId: string | null;
}

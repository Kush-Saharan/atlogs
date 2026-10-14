import type {
  AssetDoc,
  AssetSummary,
  Connector,
  DocumentParse,
  GraphData,
  HistoryItem,
  HistoryRun,
  MaintenanceLog,
  MaintenanceLogDetail,
  RiskAssessment,
  PriorityRecommendation,
  DecisionEntry,
  Overview,
  Part,
  ReviewItem,
  SimilarCases,
  Technician,
  ComponentDefault,
  ScheduleProposal,
  WorkflowEvent,
} from './types'

// Strip any trailing slash(es) so a VITE_API_URL like "https://host/" doesn't
// produce double-slash paths ("https://host//api/...") that 404.
export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8001').replace(
  /\/+$/,
  '',
)

const TOKEN_KEY = 'atlogs.token'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY)

/** fetch + bearer token; a 401 clears the token and sends the user to /login.
 *  (SSE already uses fetch streaming, so headers work; EventSource is not used.) */
async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(url, { ...init, headers })
  if (res.status === 401 && !url.endsWith('/api/auth/login')) {
    setToken(null)
    if (location.pathname !== '/login') location.assign('/login')
  }
  return res
}

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await authFetch(`${API_URL}${path}`, {
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

async function sendJSON<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await authFetch(`${API_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

export interface ConnectorCreate {
  name: string
  description: string
  kind: 'manual' | 'api'
  endpoint?: string | null
  payload?: unknown
}

export interface User {
  id: number
  email: string
  role: 'engineer' | 'manager' | 'admin'
  active?: boolean
}

export const api = {
  login: (email: string, password: string) =>
    sendJSON<{ token: string; user: User }>('POST', '/api/auth/login', { email, password }),
  me: (signal?: AbortSignal) => getJSON<User>('/api/auth/me', signal),
  users: (signal?: AbortSignal) => getJSON<User[]>('/api/admin/users', signal),
  createUser: (body: { email: string; password: string; role: string }) =>
    sendJSON<User>('POST', '/api/admin/users', body),
  updateUser: (id: number, body: { role?: string; active?: boolean }) =>
    sendJSON<User>('PATCH', `/api/admin/users/${id}`, body),
  setCriticality: (unifiedId: string, level: string) =>
    sendJSON<{ criticality: string }>('PUT', `/api/assets/${encodeURIComponent(unifiedId)}/criticality`, { level }),
  technicians: (signal?: AbortSignal) => getJSON<Technician[]>('/api/resources/technicians', signal),
  saveTechnician: (body: Omit<Technician, 'id'>, id?: number) =>
    id === undefined
      ? sendJSON<Technician>('POST', '/api/resources/technicians', body)
      : sendJSON<Technician>('PUT', `/api/resources/technicians/${id}`, body),
  deleteTechnician: (id: number) => sendJSON<unknown>('DELETE', `/api/resources/technicians/${id}`),
  parts: (signal?: AbortSignal) => getJSON<Part[]>('/api/resources/parts', signal),
  savePart: (body: Omit<Part, 'id'>, id?: number) =>
    id === undefined
      ? sendJSON<Part>('POST', '/api/resources/parts', body)
      : sendJSON<Part>('PUT', `/api/resources/parts/${id}`, body),
  deletePart: (id: number) => sendJSON<unknown>('DELETE', `/api/resources/parts/${id}`),
  scheduleDefaults: (signal?: AbortSignal) => getJSON<ComponentDefault[]>('/api/schedule/defaults', signal),
  saveScheduleDefault: (component: string, body: Omit<ComponentDefault, 'component'>) =>
    sendJSON<ComponentDefault>('PUT', `/api/schedule/defaults/${encodeURIComponent(component)}`, body),
  deleteScheduleDefault: (component: string) =>
    sendJSON<unknown>('DELETE', `/api/schedule/defaults/${encodeURIComponent(component)}`),
  scheduleProposal: (signal?: AbortSignal) => getJSON<ScheduleProposal | null>('/api/schedule/proposal', signal),
  proposeSchedule: (days: number) => sendJSON<ScheduleProposal>('POST', `/api/schedule/propose?days=${days}`),
  logs: (signal?: AbortSignal) => getJSON<MaintenanceLog[]>('/api/logs', signal),
  log: (id: number, signal?: AbortSignal) =>
    getJSON<MaintenanceLogDetail>(`/api/logs/${id}`, signal),
  reviewLog: (id: number, fields: Record<string, string>) =>
    sendJSON<MaintenanceLogDetail>('PUT', `/api/records/${id}/review`, { fields }),
  similarCases: (id: number, signal?: AbortSignal) =>
    getJSON<SimilarCases>(`/api/records/${id}/similar`, signal),
  riskAssessment: (id: number, signal?: AbortSignal) =>
    getJSON<RiskAssessment | null>(`/api/records/${id}/risk`, signal),
  assessRisk: (id: number) => sendJSON<RiskAssessment>('POST', `/api/records/${id}/risk`),
  priorityRecommendation: (id: number, signal?: AbortSignal) =>
    getJSON<PriorityRecommendation | null>(`/api/records/${id}/priority`, signal),
  recommendPriority: (id: number) => sendJSON<PriorityRecommendation>('POST', `/api/records/${id}/priority`),
  decide: (recId: number, body: { action: string; priority?: string; comment?: string }) =>
    sendJSON<DecisionEntry>('POST', `/api/recommendations/${recId}/decision`, body),
  decisions: (id: number, signal?: AbortSignal) => getJSON<DecisionEntry[]>(`/api/records/${id}/decisions`, signal),
  audit: (signal?: AbortSignal) => getJSON<DecisionEntry[]>('/api/audit', signal),
  overview: (signal?: AbortSignal) => getJSON<Overview>('/api/overview', signal),
  graph: (asset?: string, signal?: AbortSignal) =>
    getJSON<GraphData>(
      `/api/graph${asset ? `?asset=${encodeURIComponent(asset)}` : ''}`,
      signal,
    ),
  assets: (signal?: AbortSignal) => getJSON<AssetSummary[]>('/api/assets', signal),
  review: (signal?: AbortSignal) => getJSON<ReviewItem[]>('/api/review', signal),
  connectors: (signal?: AbortSignal) => getJSON<Connector[]>('/api/connectors', signal),
  createConnector: (body: ConnectorCreate) =>
    sendJSON<Connector>('POST', '/api/connectors', body),
  deleteConnector: (id: number) =>
    sendJSON<{ ok: boolean }>('DELETE', `/api/connectors/${id}`),
  resolveReview: (id: number, action: 'merge' | 'separate' | 'dismiss') =>
    sendJSON<{ ok: boolean; status?: string }>(
      'POST',
      `/api/review/${id}/resolve`,
      { action },
    ),
  asset: (id: string, signal?: AbortSignal) =>
    getJSON<AssetDoc>(`/api/asset/${encodeURIComponent(id)}`, signal),
  documents: (signal?: AbortSignal) =>
    getJSON<DocumentParse[]>('/api/documents', signal),
  startIngestPath: (path: string) =>
    sendJSON<IngestJob>('POST', '/api/documents/ingest-path', { path }),
  documentJobs: (signal?: AbortSignal) =>
    getJSON<{ jobs: IngestJobSummary[]; running: boolean }>(
      '/api/documents/jobs',
      signal,
    ),
  cancelDocumentJob: (jobId: string) =>
    sendJSON<{ ok: boolean }>('POST', `/api/documents/jobs/${jobId}/cancel`),
  history: (kind?: 'rca' | 'compliance', signal?: AbortSignal) =>
    getJSON<HistoryItem[]>(`/api/history${kind ? `?kind=${kind}` : ''}`, signal),
  historyRun: (id: number, signal?: AbortSignal) =>
    getJSON<HistoryRun>(`/api/history/${id}`, signal),
}

/** Parse an SSE `data: {json}\n\n` response body into WorkflowEvents. */
async function* readSSE(res: Response, label: string): AsyncGenerator<WorkflowEvent> {
  if (!res.ok || !res.body) {
    throw new Error(`${label} failed: ${res.status}`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        const dataLine = frame.split('\n').find((l) => l.startsWith('data:'))
        if (!dataLine) continue
        const json = dataLine.slice(5).trim()
        if (json) {
          try {
            yield JSON.parse(json) as WorkflowEvent
          } catch {
            // ignore malformed frame
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * POST a JSON body and stream Server-Sent Events back as they arrive.
 * Abort via the AbortSignal (used to interrupt a running answer/workflow).
 */
export async function* streamWorkflow(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<WorkflowEvent> {
  const res = await authFetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  yield* readSSE(res, `POST ${path}`)
}

export interface IngestJob {
  job_id?: string
  status?: string
  label?: string
  count?: number
  error?: string
}

export interface IngestJobSummary {
  id: string
  kind: string
  label: string
  status: string // running | done | error | cancelled
  started_at: number
  finished_at: number | null
  event_count: number
  last_message: string
}

/** Upload PDFs (multipart) and START a background ingest job. Returns the job id
 *  immediately; the job keeps running server-side even if the page is left. */
export async function startDocumentUpload(files: File[]): Promise<IngestJob> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  // Do NOT set Content-Type — the browser adds the multipart boundary.
  const res = await authFetch(`${API_URL}/api/documents/ingest`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
    body: fd,
  })
  if (!res.ok) throw new Error(`upload failed: ${res.status}`)
  return (await res.json()) as IngestJob
}

/** Tail a background ingest job's status (GET SSE). Reconnect-safe: replays the
 *  buffered log then follows the live tail. */
export async function* streamJob(
  jobId: string,
  signal?: AbortSignal,
): AsyncGenerator<WorkflowEvent> {
  const res = await authFetch(`${API_URL}/api/documents/jobs/${jobId}/stream`, {
    headers: { Accept: 'text/event-stream' },
    signal,
  })
  yield* readSSE(res, `GET /api/documents/jobs/${jobId}/stream`)
}

/** Thrown by submitLog; `existingId` is set on a 409 duplicate. */
export class LogSubmitError extends Error {
  status: number
  existingId?: number
  constructor(message: string, status: number, existingId?: number) {
    super(message)
    this.status = status
    this.existingId = existingId
  }
}

/** Submit a maintenance log as pasted text or a file (multipart). */
export async function submitLog(
  input: { text?: string; file?: File | null; force?: boolean },
): Promise<MaintenanceLog> {
  const fd = new FormData()
  if (input.file) fd.append('file', input.file)
  else fd.append('text', input.text ?? '')
  if (input.force) fd.append('force', 'true')
  const res = await authFetch(`${API_URL}/api/logs`, { method: 'POST', body: fd })
  if (res.ok) return (await res.json()) as MaintenanceLog
  const body = await res.json().catch(() => ({}))
  const d = body.detail
  throw new LogSubmitError(
    typeof d === 'string' ? d : (d?.message ?? `Upload failed (${res.status})`),
    res.status,
    d?.existing_id,
  )
}

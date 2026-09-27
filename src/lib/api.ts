const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/* ------------------------------------------------------------------
   Token management
   NOTE: Bearer tokens in localStorage are an acceptable trade-off
   for this educational project. A production system would use
   HttpOnly secure cookies for refresh tokens.
------------------------------------------------------------------ */
let accessToken: string | null = localStorage.getItem('sentinel_access_token')
let storedRefreshToken: string | null = localStorage.getItem('sentinel_refresh_token')

export function setTokens(access: string, refresh: string) {
  accessToken = access
  storedRefreshToken = refresh
  localStorage.setItem('sentinel_access_token', access)
  localStorage.setItem('sentinel_refresh_token', refresh)
}

export function clearTokens() {
  accessToken = null
  storedRefreshToken = null
  localStorage.removeItem('sentinel_access_token')
  localStorage.removeItem('sentinel_refresh_token')
  localStorage.removeItem('sentinel_user')
}

export function getAccessToken(): string | null {
  return accessToken
}

export function getStoredRefreshToken(): string | null {
  return storedRefreshToken
}

/* ------------------------------------------------------------------
   Types
------------------------------------------------------------------ */
export interface ApiUser {
  id: string
  name: string
  email: string
  role: string
  department?: string
  jobTitle?: string
}

export interface LoginResponse {
  accessToken: string
  refreshToken: string
  token_type?: string
  expires_in?: number
  user: ApiUser
}

export interface DashboardMetrics {
  openAlerts: number
  identitiesWatched: number
  anomaliesDetected: number
  meanRiskIndex: number
  watchlistCount: number
}

export interface TrendPoint {
  label: string
  anomalies: number
  meanRisk: number
  baseline: number
}

export interface DetectionMixItem {
  kind: string
  count: number
}

export interface TriageItem {
  id: string
  headline: string
  severity: string
  risk_score: number
  status: string
  employee_id: string
}

export interface DriftItem {
  id: string
  name: string
  drift: number
  department: string
  risk_score: number
}

export interface DashboardResponse {
  metrics: DashboardMetrics
  anomalyTrend: TrendPoint[]
  detectionMix: DetectionMixItem[]
  priorityTriage: TriageItem[]
  behaviourDrift: DriftItem[]
}

export interface PaginatedResponse<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface ApiAnomaly {
  id: string
  user_id: string
  detection_type: string
  severity: string
  risk_score: number
  anomaly_score: number
  confidence: number
  description: string
  status: string
  detected_at: string
  created_at: string
  risk_factors?: RiskFactor[]
}

export interface RiskFactor {
  id: string
  signal_type: string
  signal_value: number
  weight: number
  contribution: number
}

export interface ApiActivity {
  id: string
  user_id: string
  timestamp: string
  event_type: string
  action: string
  resource: string
  source_ip: string
  risk_contribution: number
}

export interface ApiInvestigation {
  id: string
  anomaly_id: string
  assigned_to: string | null
  title: string
  summary: string | null
  status: string
  priority: string
  created_at: string
  updated_at: string
  resolved_at: string | null
  events: ApiInvestigationEvent[]
}

export interface ApiInvestigationEvent {
  id: string
  investigation_id: string
  actor_id: string | null
  action: string
  description: string | null
  created_at: string
}

export interface ApiPolicy {
  id: string
  name: string
  description: string | null
  detection_type: string
  enabled: boolean
  severity: string
  threshold: number
  created_by: string | null
  updated_by: string | null
  created_at: string
  updated_at: string
}

export interface ApiNotification {
  id: string
  user_id: string
  type: string
  title: string
  message: string | null
  related_anomaly_id: string | null
  read: boolean
  created_at: string
}

/* ------------------------------------------------------------------
   Error handling
------------------------------------------------------------------ */
export class ApiError extends Error {
  status: number
  code?: string

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/**
 * Human-readable error message mapping for login failures.
 * Never exposes Python stack traces, SQL queries, or internal details.
 */
export function getLoginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0 || error.message.includes('Failed to fetch')) {
      return 'Unable to connect to Sentinel API. Make sure the backend is running.'
    }
    if (error.status === 401) {
      return 'Invalid email or password.'
    }
    if (error.status === 403) {
      return 'Account is not active. Contact your administrator.'
    }
    if (error.status === 422) {
      return 'Please enter a valid email and password.'
    }
    if (error.status >= 500) {
      return 'Sentinel API encountered an error. Please try again.'
    }
    return error.message || 'An unexpected error occurred.'
  }
  if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
    return 'Unable to connect to Sentinel API. Make sure the backend is running.'
  }
  return 'An unexpected error occurred. Please try again.'
}

/* ------------------------------------------------------------------
   Fetch wrapper with auth
   Automatically attaches the access token. On 401, attempts one
   token refresh before failing (avoids infinite loops).
------------------------------------------------------------------ */
let _refreshPromise: Promise<void> | null = null
let _retryCount = 0
const MAX_RETRIES = 1

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }

  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  // Handle 401 — attempt token refresh once (unless this is the refresh endpoint itself)
  if (response.status === 401 && !path.includes('/auth/refresh') && !path.includes('/auth/login') && _retryCount < MAX_RETRIES) {
    _retryCount++
    try {
      await refreshAccessToken()
      // Retry with the new token
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`
      }
      const retryResponse = await fetch(`${API_BASE}${path}`, { ...options, headers })
      if (!retryResponse.ok) {
        const body = await retryResponse.json().catch(() => ({}))
        const detail = body?.detail || body?.error?.message || retryResponse.statusText
        throw new ApiError(retryResponse.status, detail, body?.error?.code)
      }
      if (retryResponse.status === 204) return undefined as T
      _retryCount = 0
      return retryResponse.json()
    } catch (refreshError) {
      _retryCount = 0
      // Refresh failed — clear session and re-throw
      clearTokens()
      localStorage.removeItem('sentinel_user')
      // Redirect to login
      window.location.href = '/login'
      throw new ApiError(401, 'Session expired. Please sign in again.')
    }
  }

  _retryCount = 0

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = body?.detail || body?.error?.message || response.statusText
    throw new ApiError(response.status, detail, body?.error?.code)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

/* ------------------------------------------------------------------
   Auth API
------------------------------------------------------------------ */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setTokens(data.accessToken, data.refreshToken)
  localStorage.setItem('sentinel_user', JSON.stringify(data.user))
  return data
}

export async function logout(): Promise<void> {
  try {
    await apiFetch('/api/v1/auth/logout', { method: 'POST' })
  } finally {
    clearTokens()
  }
}

export async function refreshAccessToken(): Promise<void> {
  if (!storedRefreshToken) throw new Error('No refresh token available')

  // Deduplicate concurrent refresh attempts
  if (_refreshPromise) return _refreshPromise

  _refreshPromise = (async () => {
    try {
      const data = await apiFetch<{ accessToken: string; refreshToken: string }>(
        '/api/v1/auth/refresh',
        {
          method: 'POST',
          body: JSON.stringify({ refreshToken: storedRefreshToken }),
        },
      )
      setTokens(data.accessToken, data.refreshToken)
    } finally {
      _refreshPromise = null
    }
  })()

  return _refreshPromise
}

export async function getMe(): Promise<ApiUser> {
  return apiFetch<ApiUser>('/api/v1/auth/me')
}

/* ------------------------------------------------------------------
   Dashboard API
------------------------------------------------------------------ */
export async function getDashboard(): Promise<DashboardResponse> {
  return apiFetch<DashboardResponse>('/api/v1/dashboard')
}

/* ------------------------------------------------------------------
   Users API
------------------------------------------------------------------ */
export async function getUsers(params?: {
  page?: number
  page_size?: number
  search?: string
  department?: string
}): Promise<PaginatedResponse<ApiUser>> {
  const qs = new URLSearchParams()
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  if (params?.search) qs.set('search', params.search)
  if (params?.department) qs.set('department', params.department)
  const query = qs.toString()
  return apiFetch<PaginatedResponse<ApiUser>>(`/api/v1/users${query ? `?${query}` : ''}`)
}

/* ------------------------------------------------------------------
   Anomalies API
------------------------------------------------------------------ */
export async function getAnomalies(params?: {
  page?: number
  page_size?: number
  severity?: string
  status_filter?: string
  detection_type?: string
}): Promise<PaginatedResponse<ApiAnomaly>> {
  const qs = new URLSearchParams()
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  if (params?.severity) qs.set('severity', params.severity)
  if (params?.status_filter) qs.set('status_filter', params.status_filter)
  if (params?.detection_type) qs.set('detection_type', params.detection_type)
  const query = qs.toString()
  return apiFetch<PaginatedResponse<ApiAnomaly>>(`/api/v1/anomalies${query ? `?${query}` : ''}`)
}

/* ------------------------------------------------------------------
   Activity API
------------------------------------------------------------------ */
export async function getActivity(params?: {
  page?: number
  page_size?: number
  user_id?: string
  event_type?: string
}): Promise<PaginatedResponse<ApiActivity>> {
  const qs = new URLSearchParams()
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  if (params?.user_id) qs.set('user_id', params.user_id)
  if (params?.event_type) qs.set('event_type', params.event_type)
  const query = qs.toString()
  return apiFetch<PaginatedResponse<ApiActivity>>(`/api/v1/activity${query ? `?${query}` : ''}`)
}

/* ------------------------------------------------------------------
   Investigations API
------------------------------------------------------------------ */
export async function getInvestigations(params?: {
  page?: number
  page_size?: number
  status_filter?: string
  priority?: string
}): Promise<PaginatedResponse<ApiInvestigation>> {
  const qs = new URLSearchParams()
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  if (params?.status_filter) qs.set('status_filter', params.status_filter)
  if (params?.priority) qs.set('priority', params.priority)
  const query = qs.toString()
  return apiFetch<PaginatedResponse<ApiInvestigation>>(`/api/v1/investigations${query ? `?${query}` : ''}`)
}

export async function getInvestigation(id: string): Promise<ApiInvestigation> {
  return apiFetch<ApiInvestigation>(`/api/v1/investigations/${id}`)
}

/* ------------------------------------------------------------------
   Policies API
------------------------------------------------------------------ */
export async function getPolicies(params?: {
  page?: number
  page_size?: number
  detection_type?: string
}): Promise<PaginatedResponse<ApiPolicy>> {
  const qs = new URLSearchParams()
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  if (params?.detection_type) qs.set('detection_type', params.detection_type)
  const query = qs.toString()
  return apiFetch<PaginatedResponse<ApiPolicy>>(`/api/v1/policies${query ? `?${query}` : ''}`)
}

/* ------------------------------------------------------------------
   ML API
------------------------------------------------------------------ */
export async function getMLStatus(): Promise<{
  loaded: boolean
  model_name: string
  model_version: string
}> {
  return apiFetch('/api/v1/ml/status')
}

export async function mlPredict(features: Record<string, unknown>): Promise<{
  predicted_class: number
  anomaly_probability: number
  risk_score: number
  severity: string
  confidence: number
  model_version: string
  risk_factors: Array<{ feature: string; value: unknown; contribution: number; description?: string }>
  rule_signals: Array<{ type: string; signal_value: number; weight: number; description: string }>
  explanation: string
}> {
  return apiFetch('/api/v1/ml/predict', {
    method: 'POST',
    body: JSON.stringify({ features }),
  })
}

/* ------------------------------------------------------------------
   Health check
------------------------------------------------------------------ */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`)
    return res.ok
  } catch {
    return false
  }
}

export async function getHealthDetail(): Promise<{
  status: string
  database: string
  ml_model?: string
} | null> {
  try {
    const res = await fetch(`${API_BASE}/health`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

/* ------------------------------------------------------------------
   User management (admin) + bootstrap
------------------------------------------------------------------ */
export interface ApiAdminUser extends ApiUser {
  status: string
  employee_code?: string | null
  branch_code?: string | null
  branch_name?: string | null
  mfa_enabled?: boolean
  last_login: string | null
  created_at: string
  roles: Array<{ id: string; name: string; description?: string }>
}

export interface RoleMeta {
  roles: string[]
  branches: Array<{ code: string; name: string }>
}

export async function getRoleMeta(): Promise<RoleMeta> {
  return apiFetch<RoleMeta>('/api/v1/users/meta/reference')
}

export interface HasUsersResponse {
  hasUsers: boolean
  totalUsers: number
}

export async function hasUsers(): Promise<HasUsersResponse> {
  return apiFetch<HasUsersResponse>('/api/v1/auth/has-users')
}

export async function bootstrapAdmin(input: {
  name: string
  email: string
  password: string
  department?: string
  jobTitle?: string
}): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>('/api/v1/auth/bootstrap-admin', {
    method: 'POST',
    body: JSON.stringify({
      name: input.name,
      email: input.email,
      password: input.password,
      department: input.department,
      job_title: input.jobTitle,
    }),
  })
  setTokens(data.accessToken, data.refreshToken)
  localStorage.setItem('sentinel_user', JSON.stringify(data.user))
  return data
}

export async function adminCreateUser(input: {
  name: string
  email: string
  password: string
  role: string
  department?: string
  jobTitle?: string
  employeeCode?: string
  branchCode?: string
  branchName?: string
  mfaEnabled?: boolean
}): Promise<ApiAdminUser> {
  return apiFetch<ApiAdminUser>('/api/v1/users', {
    method: 'POST',
    body: JSON.stringify({
      name: input.name,
      email: input.email,
      password: input.password,
      role: input.role,
      department: input.department,
      job_title: input.jobTitle,
      employee_code: input.employeeCode || undefined,
      branch_code: input.branchCode || undefined,
      branch_name: input.branchName || undefined,
      mfa_enabled: input.mfaEnabled ?? false,
    }),
  })
}

export async function adminUpdateUser(
  id: string,
  patch: {
    name?: string
    department?: string
    jobTitle?: string
    status?: string
    password?: string
    role?: string
  },
): Promise<ApiAdminUser> {
  return apiFetch<ApiAdminUser>(`/api/v1/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({
      name: patch.name,
      department: patch.department,
      job_title: patch.jobTitle,
      status: patch.status,
      password: patch.password,
      role: patch.role,
    }),
  })
}

export async function adminDeactivateUser(id: string): Promise<{ id: string; status: string }> {
  return apiFetch<{ id: string; status: string }>(`/api/v1/users/${id}`, { method: 'DELETE' })
}

/* ------------------------------------------------------------------
   Telemetry API
------------------------------------------------------------------ */
export interface ApiTelemetryEvent {
  id: string
  user_id: string
  event_type: string
  source: string
  occurred_at: string
  received_at: string
  ip_address?: string | null
  location?: string | null
  latitude?: string | null
  longitude?: string | null
  accuracy_m?: number | null
  device?: string | null
  resource?: string | null
  application?: string | null
  metadata?: Record<string, unknown>
  risk_contribution?: number
}

export async function getTelemetry(params?: {
  user_id?: string
  event_type?: string
  source?: string
  page?: number
  page_size?: number
}): Promise<ApiTelemetryEvent[]> {
  const qs = new URLSearchParams()
  if (params?.user_id) qs.set('user_id', params.user_id)
  if (params?.event_type) qs.set('event_type', params.event_type)
  if (params?.source) qs.set('source', params.source)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch<ApiTelemetryEvent[]>(`/api/v1/telemetry${query ? `?${query}` : ''}`)
}

export interface ApiAgentKey {
  id: string
  label?: string | null
  user_id: string
  key: string
  created_at: string
}

export async function createAgentKey(input: { label: string; userId: string }): Promise<ApiAgentKey> {
  return apiFetch<ApiAgentKey>('/api/v1/telemetry/agent-keys', {
    method: 'POST',
    body: JSON.stringify({ label: input.label, user_id: input.userId }),
  })
}

export async function listAgentKeys(): Promise<Array<{ id: string; label?: string | null; user_id: string; active: boolean; last_used_at?: string | null; created_at: string }>> {
  return apiFetch('/api/v1/telemetry/agent-keys')
}

export async function revokeAgentKey(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/telemetry/agent-keys/${id}`, { method: 'DELETE' })
}

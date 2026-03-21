/**
 * lib/api.ts — HTTP клиент для ContentHub API
 *
 * Хранение токенов:
 *   access_token  — в памяти (переменная модуля). Теряется при F5 → авто-refresh.
 *   refresh_token — httpOnly cookie (ставится сервером, JS не видит).
 *   role          — в памяти (переменная модуля). Восстанавливается при /refresh.
 *
 * [FIX#3] role перенесена из localStorage в in-memory хранилище.
 * localStorage.getItem('role') → getUserRole()
 * localStorage.setItem('role') → setUserRole()
 * localStorage.removeItem('role') → setUserRole(null)
 *
 * После F5: RequireAuth → initAuth() → _refreshAccessToken() → setUserRole(data.role)
 * Таким образом role восстанавливается из сервера, не из localStorage.
 */

const BASE = '/api'

// Access token — ТОЛЬКО в памяти, не в localStorage
let accessToken: string | null = null

// [FIX#3] Role — ТОЛЬКО в памяти, не в localStorage
let _userRole: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

// [FIX#3] Публичные функции управления role
export function getUserRole(): string | null {
  return _userRole
}

export function setUserRole(role: string | null): void {
  _userRole = role
}

export function setAccessToken(at: string, role: string) {
  accessToken = at
  // [FIX#3] role → in-memory, НЕ в localStorage
  setUserRole(role)
}

export function clearAuth() {
  accessToken = null
  // [FIX#3] Очищаем in-memory role
  setUserRole(null)
}

/**
 * Обновляет access_token через POST /auth/refresh.
 * Refresh token отправляется браузером автоматически как httpOnly cookie.
 * Вызывается при загрузке страницы (F5) и при 401 ответе.
 */
export async function initAuth(): Promise<boolean> {
  // #region agent log
  fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'login-debug-1',hypothesisId:'H3',location:'src/lib/api.ts:initAuth',message:'initAuth started',data:{hasAccessToken:!!accessToken},timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  return _refreshAccessToken()
}

async function _refreshAccessToken(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method:      'POST',
      credentials: 'include',   // браузер добавляет cookie автоматически
    })
    // #region agent log
    fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'login-debug-1',hypothesisId:'H3',location:'src/lib/api.ts:_refreshAccessToken',message:'refresh response received',data:{status:res.status,ok:res.ok},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    if (!res.ok) {
      clearAuth()
      return false
    }
    const data = await res.json()
    accessToken = data.access_token
    // [FIX#3] role → in-memory вместо localStorage
    if (data.role) setUserRole(data.role)
    return true
  } catch {
    clearAuth()
    return false
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',   // для cookie на /api/auth/* endpoints
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && !retried) {
    // #region agent log
    fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'login-debug-1',hypothesisId:'H4',location:'src/lib/api.ts:request',message:'request got 401; trying refresh',data:{path,method,retried},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    const ok = await _refreshAccessToken()
    if (ok) return request<T>(method, path, body, true)
    clearAuth()
    window.location.href = '/login'
    throw new Error('Сессия истекла')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  return res.json() as Promise<T>
}

export const api = {
  get:    <T>(path: string)               => request<T>('GET',    path),
  post:   <T>(path: string, body?: unknown) => request<T>('POST',   path, body),
  put:    <T>(path: string, body?: unknown) => request<T>('PUT',    path, body),
  delete: <T>(path: string)               => request<T>('DELETE', path),
}

// Авторизация
export const auth = {
  login: async (username: string, password: string) => {
    // #region agent log
    fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'login-debug-1',hypothesisId:'H1',location:'src/lib/api.ts:auth.login',message:'login request started',data:{usernameLength:username.length,passwordLength:password.length},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    const res = await fetch(`${BASE}/auth/login`, {
      method:      'POST',
      headers:     { 'Content-Type': 'application/json' },
      credentials: 'include',   // сервер ставит cookie refresh_token в Set-Cookie
      body:        JSON.stringify({ username, password }),
    })
    // #region agent log
    fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'login-debug-1',hypothesisId:'H1',location:'src/lib/api.ts:auth.login',message:'login response received',data:{status:res.status,ok:res.ok},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      // #region agent log
      fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'login-debug-1',hypothesisId:'H2',location:'src/lib/api.ts:auth.login',message:'login failed response payload',data:{detail:err?.detail||null},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    const data = await res.json()
    // #region agent log
    fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'login-debug-1',hypothesisId:'H5',location:'src/lib/api.ts:auth.login',message:'login succeeded',data:{hasAccessToken:!!data?.access_token,role:data?.role||null},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    // [FIX#3] access_token → в память, role → in-memory (через setAccessToken)
    setAccessToken(data.access_token, data.role)
    return data
  },

  logout: async () => {
    try {
      await fetch(`${BASE}/auth/logout`, {
        method:      'POST',
        credentials: 'include',   // браузер отправляет cookie, сервер его удаляет
      })
    } catch { /* ignore network errors on logout */ }
    clearAuth()
  },

  changePassword: (username: string, newPassword: string, oldPassword?: string) =>
    api.post('/auth/change-password', { username, new_password: newPassword, old_password: oldPassword }),
}

auth.users = {
  list:   ()                               => api.get<any[]>('/auth/users'),
  create: (body: { username: string; password: string; role: string }) => api.post<any>('/auth/users', body),
  update: (id: number, role: string)       => api.put<any>(`/auth/users/${id}/role`, { role }),
}

// Dashboard, agents, etc.
export const dashboard = {
  get: () => api.get<any>('/dashboard'),
}

export const agents = {
  list:  ()                              => api.get<any>('/agents'),
  start: (project: string, name: string) => api.post<any>(`/agents/${project}/${name}/start`),
  stop:  (project: string, name: string) => api.post<any>(`/agents/${project}/${name}/stop`),
}

export const patches = {
  list:    ()          => api.get<any[]>('/patches'),
  diff:    (id: number) => api.get<any>(`/patches/${id}/diff`),
  approve: (id: number) => api.post<any>(`/patches/${id}/approve`),
  reject:  (id: number) => api.post<any>(`/patches/${id}/reject`),
}

export const configs = {
  getSP:            ()             => api.get<any>('/configs/ShortsProject'),
  updateSP:         (section: string, updates: Record<string, string>) =>
    api.put<any>(`/configs/ShortsProject/${section}`, { updates }),
  getSPConfig:       ()             => api.get<any>('/configs/ShortsProject'),
  putSPConfig:       (body: any)    => api.put<any>('/configs/ShortsProject', body),
  getPLSettings:     ()             => api.get<any>('/configs/PreLend/settings'),
  putPLSettings:     (body: any)    => api.put<any>('/configs/PreLend/settings', body),
  getAdvertisers:    ()             => api.get<any[]>('/configs/PreLend/advertisers'),
  putAdvertiser:     (id: string, body: any) => api.put<any>(`/configs/PreLend/advertisers/${id}`, body),
}

export const advertisers = {
  list:   ()                         => api.get<any[]>('/configs/PreLend/advertisers'),
  update: (id: string, body: any)    => api.put<any>(`/configs/PreLend/advertisers/${id}`, body),
  delete: (id: string)               => api.delete<any>(`/configs/PreLend/advertisers/${id}`),
}

export const analytics = {
  funnel:      (days = 7)        => api.get<any>(`/analytics/funnel?days=${days}`),
  get:         (params?: string) => api.get<any>(`/analytics${params ? '?' + params : ''}`),
  planQuality: (limit = 10)      => api.get<any>(`/analytics/plan-quality?limit=${limit}`),
}

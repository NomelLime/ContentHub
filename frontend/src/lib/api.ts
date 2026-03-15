/**
 * lib/api.ts — HTTP клиент для ContentHub API
 */

const BASE = '/api'

// Хранение токенов
let accessToken: string | null = localStorage.getItem('access_token')

export function setTokens(at: string, rt: string) {
  accessToken = at
  localStorage.setItem('access_token', at)
  localStorage.setItem('refresh_token', rt)
}

export function clearTokens() {
  accessToken = null
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

async function refreshAccessToken(): Promise<boolean> {
  const rt = localStorage.getItem('refresh_token')
  if (!rt) return false
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    })
    if (!res.ok) { clearTokens(); return false }
    const data = await res.json()
    accessToken = data.access_token
    localStorage.setItem('access_token', data.access_token)
    return true
  } catch {
    clearTokens()
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
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && !retried) {
    const ok = await refreshAccessToken()
    if (ok) return request<T>(method, path, body, true)
    clearTokens()
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
  get:    <T>(path: string)             => request<T>('GET',    path),
  post:   <T>(path: string, body?: unknown) => request<T>('POST',   path, body),
  put:    <T>(path: string, body?: unknown) => request<T>('PUT',    path, body),
  delete: <T>(path: string)             => request<T>('DELETE', path),
}

// Авторизация
export const auth = {
  login:  (username: string, password: string) =>
    api.post<{ access_token: string; refresh_token: string; role: string }>(
      '/auth/login', { username, password }
    ),
  logout: (refreshToken: string) =>
    api.post('/auth/logout', { refresh_token: refreshToken }),
  changePassword: (username: string, newPassword: string, oldPassword?: string) =>
    api.post('/auth/change-password', { username, new_password: newPassword, old_password: oldPassword }),
  users: {
    list:   ()                                    => api.get<any[]>('/auth/users'),
    create: (u: { username: string; password: string; role: string }) =>
      api.post('/auth/users', u),
    update: (id: number, role: string)            => api.put(`/auth/users/${id}`, { role }),
  },
}

// Dashboard
export const dashboard = {
  get: () => api.get<any>('/dashboard'),
}

// Агенты
export const agents = {
  list:  ()                                     => api.get<any>('/agents'),
  stop:  (project: string, name: string)        => api.post(`/agents/${project}/${name}/stop`),
  start: (project: string, name: string)        => api.post(`/agents/${project}/${name}/start`),
}

// Патчи
export const patches = {
  list:    ()              => api.get<any[]>('/patches'),
  approve: (id: number)   => api.post(`/patches/${id}/approve`),
  reject:  (id: number)   => api.post(`/patches/${id}/reject`),
}

// Конфиги
export const configs = {
  getSP:         ()                                   => api.get<any>('/configs/ShortsProject'),
  getSPSection:  (section: string)                    => api.get<any>(`/configs/ShortsProject/${section}`),
  updateSP:      (section: string, updates: Record<string, string>) =>
    api.put(`/configs/ShortsProject/${section}`, { updates }),
  getPLSettings: ()                                   => api.get<any>('/configs/PreLend/settings'),
  updatePLSettings: (data: Record<string, any>)       => api.put('/configs/PreLend/settings', data),
  getZones:      ()                                   => api.get<any[]>('/configs/Orchestrator/zones'),
}

// Рекламодатели
export const advertisers = {
  list:      ()                              => api.get<any[]>('/advertisers'),
  get:       (id: string)                   => api.get<any>(`/advertisers/${id}`),
  create:    (data: any)                    => api.post('/advertisers', data),
  update:    (id: string, data: any)        => api.put(`/advertisers/${id}`, data),
  delete:    (id: string)                   => api.delete(`/advertisers/${id}`),
  geoData:   {
    get:    ()           => api.get<any>('/advertisers/geo-data'),
    update: (data: any)  => api.put('/advertisers/geo-data', data),
  },
}

// Аналитика
export const analytics = {
  funnel: (days = 7) => api.get<any>(`/analytics/funnel?days=${days}`),
  sp:     ()         => api.get<any>('/analytics/sp'),
  pl:     ()         => api.get<any>('/analytics/pl'),
  audit:  (limit = 50, project?: string) =>
    api.get<any[]>(`/analytics/audit?limit=${limit}${project ? `&project=${project}` : ''}`),
}

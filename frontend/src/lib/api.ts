/**
 * lib/api.ts — HTTP клиент для ContentHub API
 *
 * Хранение токенов:
 *   access_token  — в памяти (переменная модуля). Теряется при F5 → авто-refresh.
 *   refresh_token — httpOnly cookie (ставится сервером, JS не видит).
 *   role          — localStorage (не секрет, нужен для UI-рендеринга до refresh).
 */

const BASE = '/api'

// Access token — ТОЛЬКО в памяти, не в localStorage
let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(at: string, role: string) {
  accessToken = at
  // role сохраняем в localStorage — не секрет, нужен для sidebar/RequireAuth
  localStorage.setItem('role', role)
}

export function clearAuth() {
  accessToken = null
  localStorage.removeItem('role')
}

/**
 * Обновляет access_token через POST /auth/refresh.
 * Refresh token отправляется браузером автоматически как httpOnly cookie.
 * Вызывается при загрузке страницы (F5) и при 401 ответе.
 */
export async function initAuth(): Promise<boolean> {
  return _refreshAccessToken()
}

async function _refreshAccessToken(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method:      'POST',
      credentials: 'include',   // браузер добавляет cookie автоматически
    })
    if (!res.ok) {
      clearAuth()
      return false
    }
    const data = await res.json()
    accessToken = data.access_token
    if (data.role) localStorage.setItem('role', data.role)
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
  get:    <T>(path: string)                       => request<T>('GET',    path),
  post:   <T>(path: string, body?: unknown)       => request<T>('POST',   path, body),
  put:    <T>(path: string, body?: unknown)       => request<T>('PUT',    path, body),
  delete: <T>(path: string)                       => request<T>('DELETE', path),
}

// Авторизация
export const auth = {
  login: async (username: string, password: string) => {
    const res = await fetch(`${BASE}/auth/login`, {
      method:      'POST',
      headers:     { 'Content-Type': 'application/json' },
      credentials: 'include',   // сервер ставит cookie refresh_token в Set-Cookie
      body:        JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    const data = await res.json()
    // access_token → в память, role → localStorage
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
    api.post('/auth/change-password', {
      username,
      new_password: newPassword,
      old_password: oldPassword,
    }),

  users: {
    list:   ()                                                         => api.get<any[]>('/auth/users'),
    create: (u: { username: string; password: string; role: string }) => api.post('/auth/users', u),
    update: (id: number, role: string)                                 => api.put(`/auth/users/${id}`, { role }),
  },
}

// Dashboard
export const dashboard = {
  get: () => api.get<any>('/dashboard'),
}

// Агенты
export const agents = {
  list:  ()                                      => api.get<any>('/agents'),
  stop:  (project: string, name: string)         => api.post(`/agents/${project}/${name}/stop`),
  start: (project: string, name: string)         => api.post(`/agents/${project}/${name}/start`),
}

// Патчи
export const patches = {
  list:    ()              => api.get<any[]>('/patches'),
  approve: (id: number)    => api.post(`/patches/${id}/approve`),
  reject:  (id: number)    => api.post(`/patches/${id}/reject`),
}

// Конфиги
export const configs = {
  getSP:            ()                                              => api.get<any>('/configs/ShortsProject'),
  getSPSection:     (section: string)                              => api.get<any>(`/configs/ShortsProject/${section}`),
  updateSP:         (section: string, updates: Record<string, string>) =>
    api.put(`/configs/ShortsProject/${section}`, { updates }),
  getPLSettings:    ()                                             => api.get<any>('/configs/PreLend/settings'),
  updatePLSettings: (data: Record<string, any>)                   => api.put('/configs/PreLend/settings', data),
  getZones:         ()                                             => api.get<any[]>('/configs/Orchestrator/zones'),
}

// Рекламодатели
export const advertisers = {
  list:    ()                      => api.get<any[]>('/advertisers'),
  get:     (id: string)            => api.get<any>(`/advertisers/${id}`),
  create:  (data: any)             => api.post('/advertisers', data),
  update:  (id: string, data: any) => api.put(`/advertisers/${id}`, data),
  delete:  (id: string)            => api.delete(`/advertisers/${id}`),
  geoData: {
    get:    ()           => api.get<any>('/advertisers/geo-data'),
    update: (data: any)  => api.put('/advertisers/geo-data', data),
  },
}

// Аналитика
export const analytics = {
  funnel: (days = 7)             => api.get<any>(`/analytics/funnel?days=${days}`),
  sp:     ()                     => api.get<any>('/analytics/sp'),
  pl:     ()                     => api.get<any>('/analytics/pl'),
  audit:  (limit = 50, project?: string) =>
    api.get<any[]>(`/analytics/audit?limit=${limit}${project ? `&project=${project}` : ''}`),
}

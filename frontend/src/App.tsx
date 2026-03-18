import React, { Suspense, lazy, useState, useEffect } from 'react'
import { Routes, Route, NavLink, Navigate, useNavigate } from 'react-router-dom'
import { getAccessToken, initAuth, auth as authApi, clearAuth } from './lib/api'
import clsx from 'clsx'

// Lazy pages
const Dashboard     = lazy(() => import('./pages/DashboardPage'))
const PatchesPage   = lazy(() => import('./pages/PatchesPage'))
const ConfigPage    = lazy(() => import('./pages/ConfigPage'))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'))
const UsersPage     = lazy(() => import('./pages/UsersPage'))
const LoginPage     = lazy(() => import('./pages/LoginPage'))

/**
 * Защита маршрутов.
 * При первой загрузке (F5) access_token нет в памяти →
 * пробуем refresh через httpOnly cookie → если успех, показываем контент.
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [authed,  setAuthed]  = useState(false)

  useEffect(() => {
    const token = getAccessToken()
    if (token) {
      // Токен уже в памяти (навигация внутри SPA, не F5)
      setAuthed(true)
      setLoading(false)
    } else {
      // Первая загрузка после F5 — пробуем refresh через cookie
      initAuth().then(ok => {
        setAuthed(ok)
        setLoading(false)
      })
    }
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-screen text-gray-500">
      Загрузка…
    </div>
  )
  if (!authed) return <Navigate to="/login" replace />
  return <>{children}</>
}

const NAV = [
  { to: '/',          label: 'Дашборд' },
  { to: '/patches',   label: 'Патчи' },
  { to: '/config',    label: 'Конфиги' },
  { to: '/analytics', label: 'Аналитика' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const role     = localStorage.getItem('role')
  const isAdmin  = role === 'admin'

  const logout = async () => {
    await authApi.logout()   // удаляет httpOnly cookie + clearAuth()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-5 border-b border-gray-800">
          <span className="text-lg font-bold text-white">ContentHub</span>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => clsx(
                'block px-4 py-2.5 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-indigo-600/20 text-indigo-400 font-medium'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800',
              )}
            >
              {label}
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink
              to="/users"
              className={({ isActive }) => clsx(
                'block px-4 py-2.5 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-indigo-600/20 text-indigo-400 font-medium'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800',
              )}
            >
              Пользователи
            </NavLink>
          )}
        </nav>
        <div className="p-3 border-t border-gray-800">
          <button
            onClick={logout}
            className="w-full px-4 py-2 text-sm text-gray-500 hover:text-white hover:bg-gray-800 rounded-lg transition-colors text-left"
          >
            Выйти
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-gray-500">Загрузка…</div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route path="/"          element={<Dashboard />} />
                <Route path="/patches"   element={<PatchesPage />} />
                <Route path="/config"    element={<ConfigPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/users"     element={<UsersPage />} />
              </Routes>
            </Layout>
          </RequireAuth>
        } />
      </Routes>
    </Suspense>
  )
}

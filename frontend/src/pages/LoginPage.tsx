import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { auth } from '../lib/api'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)
  const navigate                = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      // auth.login() вызывает setAccessToken(access_token, role) →
      // access_token → в память (module variable)
      // role         → в память через setUserRole() [FIX#3: было localStorage]
      // refresh_token → httpOnly cookie (браузер хранит автоматически)
      await auth.login(username, password)
      navigate('/')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">ContentHub</h1>
          <p className="text-gray-500 mt-2 text-sm">Централизованное управление проектами</p>
        </div>
        <form onSubmit={submit} className="bg-gray-800 rounded-2xl border border-gray-700 p-8 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Логин</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-indigo-500"
              placeholder="admin"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          {error && <div className="text-red-400 text-sm text-center">{error}</div>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg font-medium transition-colors"
          >
            {loading ? 'Вход…' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}

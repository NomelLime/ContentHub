import React, { useEffect, useState } from 'react'
import { auth } from '../lib/api'

export default function UsersPage() {
  const [users,   setUsers]   = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [form,    setForm]    = useState({ username: '', password: '', role: 'viewer' })
  const [msg,     setMsg]     = useState<string | null>(null)

  const load = () => {
    auth.users.list().then((d) => { setUsers(d); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setMsg(null)
    try {
      await auth.users.create(form)
      setMsg('✓ Пользователь создан')
      setForm({ username: '', password: '', role: 'viewer' })
      load()
    } catch (e: any) {
      setMsg(`✗ ${e.message}`)
    }
  }

  const updateRole = async (id: number, role: string) => {
    try {
      await auth.users.update(id, role)
      load()
    } catch (e: any) {
      setMsg(`✗ ${e.message}`)
    }
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <h1 className="text-2xl font-bold">Пользователи</h1>

      {msg && (
        <div className={`p-3 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
          {msg}
        </div>
      )}

      {/* Список */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 text-xs uppercase tracking-wider border-b border-gray-700 bg-gray-800/50">
              <th className="px-4 py-3">Логин</th>
              <th className="px-4 py-3">Роль</th>
              <th className="px-4 py-3">Последний вход</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {users.map((u) => (
              <tr key={u.id} className="bg-gray-800">
                <td className="px-4 py-3 font-medium">{u.username}</td>
                <td className="px-4 py-3">
                  <select
                    value={u.role}
                    onChange={(e) => updateRole(u.id, e.target.value)}
                    className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs"
                  >
                    <option value="viewer">viewer</option>
                    <option value="operator">operator</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {u.last_login ? new Date(u.last_login).toLocaleString('ru') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Создать */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h2 className="font-semibold mb-4">Добавить пользователя</h2>
        <form onSubmit={create} className="flex gap-3 flex-wrap">
          <input
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            placeholder="Логин"
            className="flex-1 min-w-32 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            required
          />
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Пароль"
            className="flex-1 min-w-32 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            required
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
          >
            <option value="viewer">viewer</option>
            <option value="operator">operator</option>
            <option value="admin">admin</option>
          </select>
          <button type="submit" className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-medium">
            Создать
          </button>
        </form>
      </div>
    </div>
  )
}

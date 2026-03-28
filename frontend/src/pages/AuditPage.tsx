import React, { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { analytics, getUserRole } from '../lib/api'

type AuditRow = {
  id: number
  ts: string
  username: string | null
  action: string
  project: string | null
  detail_json: string | null
}

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([])
  const [project, setProject] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    setErr(null)
    analytics
      .audit(200, project || undefined)
      .then(setRows)
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [project])

  if (getUserRole() !== 'admin') {
    return <Navigate to="/" replace />
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Журнал аудита</h1>
      <p className="text-gray-400 text-sm">Действия пользователей через ContentHub (конфиги, патчи, агенты, …).</p>

      <div className="flex flex-wrap gap-3 items-center">
        <label className="text-sm text-gray-400">Проект</label>
        <select
          value={project}
          onChange={(e) => setProject(e.target.value)}
          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white"
        >
          <option value="">Все</option>
          <option value="PreLend">PreLend</option>
          <option value="ShortsProject">ShortsProject</option>
          <option value="Orchestrator">Orchestrator</option>
          <option value="Auth">Auth</option>
        </select>
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}
      {loading && <div className="text-gray-500">Загрузка…</div>}

      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="min-w-[720px] w-full text-sm">
          <thead>
            <tr className="bg-gray-900 text-left text-gray-400">
              <th className="p-2">Время</th>
              <th className="p-2">Пользователь</th>
              <th className="p-2">Действие</th>
              <th className="p-2">Проект</th>
              <th className="p-2">Детали</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-gray-800 align-top hover:bg-gray-900/40">
                <td className="p-2 text-gray-400 whitespace-nowrap">{r.ts}</td>
                <td className="p-2">{r.username ?? '—'}</td>
                <td className="p-2 text-indigo-300">{r.action}</td>
                <td className="p-2">{r.project ?? '—'}</td>
                <td className="p-2 text-xs text-gray-500 max-w-md break-all font-mono">
                  {r.detail_json || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

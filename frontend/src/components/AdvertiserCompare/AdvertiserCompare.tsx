import React, { useEffect, useState } from 'react'
import { advertisers } from '../../lib/api'

type Row = {
  id: string
  name?: string
  rate?: number
  status?: string
  template?: string
  clicks: number
  conversions: number
  cr: number
}

export default function AdvertiserCompare() {
  const [period, setPeriod] = useState(24)
  const [rows, setRows] = useState<Row[]>([])
  const [apiAvailable, setApiAvailable] = useState(false)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    setErr(null)
    advertisers
      .compare(period)
      .then((r) => {
        setRows(r.rows || [])
        setApiAvailable(!!r.api_available)
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [period])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <label className="text-sm text-gray-400">Период, ч</label>
        <select
          value={period}
          onChange={(e) => setPeriod(Number(e.target.value))}
          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white"
        >
          {[24, 48, 72, 168].map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>
        {!apiAvailable && !loading && (
          <span className="text-amber-400 text-sm">PreLend Internal API недоступен — метрики по нулям.</span>
        )}
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}
      {loading && <div className="text-gray-500">Загрузка…</div>}

      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="min-w-[640px] w-full text-sm">
          <thead>
            <tr className="bg-gray-900 text-left text-gray-400">
              <th className="p-2">ID</th>
              <th className="p-2">Название</th>
              <th className="p-2">Ставка</th>
              <th className="p-2">Статус</th>
              <th className="p-2">Шаблон</th>
              <th className="p-2 text-right">Клики</th>
              <th className="p-2 text-right">Конв.</th>
              <th className="p-2 text-right">CR</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id || r.name} className="border-t border-gray-800 hover:bg-gray-900/40">
                <td className="p-2 font-mono text-xs text-indigo-300">{r.id}</td>
                <td className="p-2">{r.name}</td>
                <td className="p-2">{r.rate ?? '—'}</td>
                <td className="p-2">{r.status}</td>
                <td className="p-2 text-gray-400">{r.template}</td>
                <td className="p-2 text-right tabular-nums">{r.clicks.toLocaleString()}</td>
                <td className="p-2 text-right tabular-nums">{r.conversions}</td>
                <td className="p-2 text-right tabular-nums">{(r.cr * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

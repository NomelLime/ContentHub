import React, { useEffect, useState } from 'react'
import { analytics } from '../lib/api'

type HookRow = {
  hook_type: string
  clicks: number
  conversions: number
  cr: number
  risk_score?: number
}

export default function HookEffectivenessBoard() {
  const [rows, setRows] = useState<HookRow[]>([])
  const [loading, setLoading] = useState(true)
  const [hours, setHours] = useState(168)

  useEffect(() => {
    setLoading(true)
    analytics
      .hooks(hours)
      .then((res) => {
        const data = Array.isArray(res?.by_hook_type) ? res.by_hook_type : []
        setRows(data.slice(0, 12))
      })
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [hours])

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold">HookEffectivenessBoard</h2>
        <div className="flex gap-2">
          {[24, 72, 168].map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              className={`px-2.5 py-1 rounded text-xs ${hours === h ? 'bg-indigo-600 text-white' : 'bg-gray-700 text-gray-300'}`}
            >
              {h === 168 ? '7д' : `${h}ч`}
            </button>
          ))}
        </div>
      </div>
      {loading ? (
        <div className="h-28 bg-gray-900/50 rounded animate-pulse" />
      ) : rows.length === 0 ? (
        <p className="text-sm text-gray-400">Нет данных по hook_type.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <div key={row.hook_type} className="flex items-center justify-between text-sm border-b border-gray-700/60 pb-2">
              <div className="text-gray-200">{row.hook_type}</div>
              <div className="text-gray-400">
                {row.clicks} кликов · CR {(row.cr * 100).toFixed(2)}% · risk {(row.risk_score ?? 0).toFixed(1)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

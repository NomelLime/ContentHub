import React, { useEffect, useState } from 'react'
import { analytics } from '../lib/api'

type RiskRow = { risk_score: number; clicks: number; conversions: number; cr: number; [k: string]: any }

export default function RiskCommandCenter() {
  const [risk, setRisk] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    analytics.risk(168).then(setRisk).catch(() => setRisk(null)).finally(() => setLoading(false))
  }, [])

  const top = (arr: RiskRow[] | undefined, key: string) =>
    (Array.isArray(arr) ? [...arr].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0)).slice(0, 5) : []).map((r: any) => (
      <div key={`${key}-${r[key]}`} className="text-xs text-gray-300">
        {r[key]}: risk {(r.risk_score || 0).toFixed(1)} · clicks {r.clicks}
      </div>
    ))

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-base font-semibold mb-4">RiskCommandCenter</h2>
      {loading ? (
        <div className="h-24 bg-gray-900/50 rounded animate-pulse" />
      ) : !risk?.available ? (
        <p className="text-sm text-gray-400">Риск-метрики недоступны.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-xs uppercase text-gray-500 mb-2">Advertiser</div>
            <div className="space-y-1">{top(risk.by_advertiser, 'advertiser_id')}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-gray-500 mb-2">Geo</div>
            <div className="space-y-1">{top(risk.by_geo, 'geo')}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-gray-500 mb-2">Hook Type</div>
            <div className="space-y-1">{top(risk.by_hook_type, 'hook_type')}</div>
          </div>
        </div>
      )}
    </div>
  )
}

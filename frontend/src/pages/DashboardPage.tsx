import React, { useEffect, useState, useCallback } from 'react'
import { dashboard as dashApi, agents as agentsApi } from '../lib/api'
import MetricCard from '../components/Dashboard/MetricCard'
import AgentPanel from '../components/AgentPanel/AgentPanel'
import AlertFeed from '../components/AlertFeed/AlertFeed'
import { useWebSocket } from '../hooks/useWebSocket'

export default function DashboardPage() {
  const [data,      setData]      = useState<any>(null)
  const [agentData, setAgentData] = useState<any>({ ShortsProject: [], PreLend: [] })
  const [loading,   setLoading]   = useState(true)
  const role = localStorage.getItem('role')
  const canControl = role === 'admin' || role === 'operator'

  const loadDashboard = () => {
    dashApi.get().then((res) => { setData(res.data); setLoading(false) }).catch(() => setLoading(false))
  }

  const loadAgents = () => {
    agentsApi.list().then(setAgentData).catch(() => {})
  }

  useEffect(() => {
    loadDashboard()
    loadAgents()
    const iv = setInterval(loadDashboard, 60_000)
    return () => clearInterval(iv)
  }, [])

  const handleAgentsWS = useCallback((ws: any) => setAgentData(ws), [])
  const handleMetricsWS = useCallback((ws: any) => setData(ws), [])

  useWebSocket(['agents', 'metrics'], {
    agents:  handleAgentsWS,
    metrics: handleMetricsWS,
  })

  const sp  = data?.sp  || {}
  const pl  = data?.pl  || {}
  const orc = data?.orc || {}

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Дашборд</h1>
        <p className="text-gray-500 text-sm mt-1">
          {data?.updated_at ? `Обновлено: ${new Date(data.updated_at).toLocaleTimeString('ru')}` : 'Загрузка…'}
        </p>
      </div>

      {/* Метрики */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard title="Просмотры (всего)"  value={sp.total_views?.toLocaleString() || '—'}  color="blue"   loading={loading} />
        <MetricCard title="Видео за 24ч"       value={sp.videos_24h  || '—'}                    color="green"  loading={loading} />
        <MetricCard title="Клики PreLend (24ч)" value={pl.clicks_24h?.toLocaleString() || '—'} color="purple" loading={loading} />
        <MetricCard title="CR PreLend (24ч)"   value={pl.cr_24h ? `${(pl.cr_24h * 100).toFixed(2)}%` : '—'} color="yellow" loading={loading} />
      </div>

      {/* Зоны Orchestrator */}
      {orc.zones?.length > 0 && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Orchestrator — Зоны доверия</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {orc.zones.map((z: any) => (
              <div key={z.zone_name} className="bg-gray-900 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium capitalize">{z.zone_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${z.enabled ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                    {z.enabled ? 'ON' : 'OFF'}
                  </span>
                </div>
                <div className="text-2xl font-bold text-indigo-400">{z.confidence_score}</div>
                <div className="mt-1.5 w-full bg-gray-700 rounded-full h-1.5">
                  <div className="h-1.5 rounded-full bg-indigo-500" style={{ width: `${z.confidence_score}%` }} />
                </div>
              </div>
            ))}
          </div>
          {orc.pending_patches > 0 && (
            <div className="mt-3 text-sm text-yellow-400">
              ⚠ {orc.pending_patches} патч(а) ожидают одобрения → <a href="/patches" className="underline">перейти</a>
            </div>
          )}
        </div>
      )}

      {/* Агенты */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h2 className="text-base font-semibold mb-4">Агенты</h2>
        <AgentPanel data={agentData} canControl={canControl} />
      </div>

      {/* Алерты */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h2 className="text-base font-semibold mb-4">Уведомления (real-time)</h2>
        <AlertFeed />
      </div>
    </div>
  )
}

import React, { useEffect, useState, useCallback } from 'react'
// [FIX#3] getUserRole() вместо localStorage.getItem('role')
import { dashboard as dashApi, agents as agentsApi, getUserRole } from '../lib/api'
import MetricCard from '../components/Dashboard/MetricCard'
import AgentPanel from '../components/AgentPanel/AgentPanel'
import AlertFeed from '../components/AlertFeed/AlertFeed'
import { useWebSocket } from '../hooks/useWebSocket'

export default function DashboardPage() {
  const [data,      setData]      = useState<any>(null)
  const [agentData, setAgentData] = useState<any>({ ShortsProject: [], PreLend: [] })
  const [loading,   setLoading]   = useState(true)
  // [FIX#3] role берём из in-memory модуля, не из localStorage
  const role = getUserRole()
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

  const handleAgentsWS  = useCallback((ws: any) => setAgentData(ws), [])
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
        <MetricCard title="Просмотры (всего)"   value={sp.total_views?.toLocaleString() || '—'}  color="blue"   loading={loading} />
        <MetricCard title="Видео за 24ч"        value={sp.videos_24h  || '—'}                    color="green"  loading={loading} />
        <MetricCard title="Клики PreLend (24ч)" value={pl.clicks_24h?.toLocaleString() || '—'}  color="purple" loading={loading} />
        <MetricCard title="CR PreLend (24ч)"    value={pl.cr_24h ? `${(pl.cr_24h * 100).toFixed(2)}%` : '—'} color="orange" loading={loading} />
      </div>

      {/* Агенты */}
      <AgentPanel
        data={agentData}
        canControl={canControl}
      />

      {/* Алерты */}
      <AlertFeed notifications={orc.notifications || []} />
    </div>
  )
}

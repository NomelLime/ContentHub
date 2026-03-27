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
        <MetricCard title="CR PreLend (24ч)"    value={pl.cr_24h ? `${(pl.cr_24h * 100).toFixed(2)}%` : '—'} color="yellow" loading={loading} />
      </div>

      {orc.cycle_telemetry && (
        <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 text-sm">
          <div className="font-medium text-gray-200">Orchestrator — текущий цикл</div>
          <div className="mt-1 text-gray-400">
            <span className="font-mono text-xs">{orc.cycle_telemetry.trace_id}</span>
            {' · '}
            цикл #{orc.cycle_telemetry.cycle_num}
            {' · '}
            <span className="text-gray-300">{orc.cycle_telemetry.status}</span>
          </div>
          {orc.cycle_telemetry.cycle_outcome != null && orc.cycle_telemetry.cycle_outcome !== '' && (
            <div className="mt-2 text-amber-200/90">
              Итог цикла:{' '}
              <span className="font-mono font-semibold">{String(orc.cycle_telemetry.cycle_outcome)}</span>
            </div>
          )}
          {orc.cycle_telemetry.cycle_summary && Object.keys(orc.cycle_telemetry.cycle_summary).length > 0 && (
            <pre className="mt-2 max-h-32 overflow-auto rounded border border-gray-600/60 bg-gray-900/80 p-2 text-xs text-gray-300 font-mono">
              {JSON.stringify(orc.cycle_telemetry.cycle_summary, null, 2)}
            </pre>
          )}
          {orc.cycle_telemetry.node_outcomes && Object.keys(orc.cycle_telemetry.node_outcomes).length > 0 && (
            <div className="mt-2 text-xs text-gray-400">
              Узлы:{' '}
              <span className="font-mono text-gray-300">
                {Object.entries(orc.cycle_telemetry.node_outcomes)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(' · ')}
              </span>
            </div>
          )}
          <p className="mt-2 text-gray-200">{orc.cycle_telemetry.step_label}</p>
          <div className="mt-1 text-xs text-gray-500 font-mono">{orc.cycle_telemetry.current_node}</div>
        </div>
      )}

      {/* Агенты */}
      <AgentPanel
        data={agentData}
        canControl={canControl}
      />

      {/* Алерты */}
      <AlertFeed />
    </div>
  )
}

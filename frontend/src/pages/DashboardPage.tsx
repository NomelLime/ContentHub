import React, { useEffect, useState, useCallback } from 'react'
// [FIX#3] getUserRole() вместо localStorage.getItem('role')
import { dashboard as dashApi, agents as agentsApi, getUserRole } from '../lib/api'
import MetricCard from '../components/Dashboard/MetricCard'
import SystemHealth from '../components/Dashboard/SystemHealth'
import AgentPanel from '../components/AgentPanel/AgentPanel'
import AlertFeed from '../components/AlertFeed/AlertFeed'
import { useWebSocket } from '../hooks/useWebSocket'

type CardColor = 'green' | 'yellow' | 'red' | 'blue' | 'purple'

function colorByRate(value: any, good: number, warn: number, invert = false): CardColor {
  if (typeof value !== 'number') return 'blue'
  if (!invert) {
    if (value >= good) return 'green'
    if (value >= warn) return 'yellow'
    return 'red'
  }
  if (value <= good) return 'green'
  if (value <= warn) return 'yellow'
  return 'red'
}

function colorByDurationSec(value: any): CardColor {
  if (typeof value !== 'number') return 'blue'
  if (value <= 120) return 'green'
  if (value <= 300) return 'yellow'
  return 'red'
}

function colorByLastClickSec(value: any): CardColor {
  if (typeof value !== 'number') return 'blue'
  if (value <= 900) return 'green'
  if (value <= 3600) return 'yellow'
  return 'red'
}

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
  const cycleSummary = orc?.cycle_telemetry?.cycle_summary || {}
  const agentMetrics = orc?.agent_metrics || {}
  const decisionMetrics = orc?.decision_metrics || cycleSummary?.decision_metrics || {}
  const nodeDurations = orc?.node_duration_sec || cycleSummary?.node_duration_sec || {}
  const spHealth = agentMetrics?.sp_agent_health || {}
  const runningRatio =
    typeof spHealth.running_ratio === 'number' ? `${(spHealth.running_ratio * 100).toFixed(0)}%` : '—'
  const cycleDurationSec =
    typeof cycleSummary.cycle_duration_sec === 'number' ? `${cycleSummary.cycle_duration_sec.toFixed(1)}с` : '—'
  const spPipelineStatus = cycleSummary.sp_pipeline_status || '—'
  const fmtPct = (v: any) => (typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—')
  const nativeMetrics = sp?.platform_native_metrics || {}
  const nativeByPlatform = nativeMetrics?.by_platform || {}
  const planApplyColor = colorByRate(decisionMetrics.plan_apply_rate_30d, 0.8, 0.6)
  const planSuccessColor = colorByRate(decisionMetrics.plan_success_24h_rate_30d, 0.65, 0.45)
  const rollbackColor = colorByRate(decisionMetrics.rollback_rate_30d, 0.08, 0.2, true)
  const patchSuccessColor = colorByRate(decisionMetrics.patch_apply_success_rate_30d, 0.8, 0.6)
  const runningRatioColor = colorByRate(spHealth.running_ratio, 0.75, 0.55)
  const cycleDurationColor = colorByDurationSec(cycleSummary.cycle_duration_sec)
  const trafficGapColor = colorByLastClickSec(agentMetrics.last_click_ago_sec)
  const pipelineColor: CardColor =
    spPipelineStatus === 'completed' || spPipelineStatus === 'running'
      ? 'green'
      : spPipelineStatus === 'skipped'
        ? 'yellow'
        : spPipelineStatus === 'failed'
          ? 'red'
          : 'blue'
  const trafficAliveColor: CardColor =
    agentMetrics.traffic_alive === true ? 'green' : agentMetrics.traffic_alive === false ? 'red' : 'blue'

  return (
    <div className="space-y-8">
      <SystemHealth />
      <div>
        <h1 className="text-2xl font-bold">Дашборд</h1>
        <p className="text-gray-500 text-sm mt-1">
          {data?.updated_at ? `Обновлено: ${new Date(data.updated_at).toLocaleTimeString('ru')}` : 'Загрузка…'}
        </p>
      </div>

      {/* Метрики */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Просмотры (всего)"   value={sp.total_views?.toLocaleString() || '—'}  color="blue"   loading={loading} />
        <MetricCard title="Видео за 24ч"        value={sp.videos_24h  || '—'}                    color="green"  loading={loading} />
        <MetricCard title="Клики PreLend (24ч)" value={pl.clicks_24h?.toLocaleString() || '—'}  color="purple" loading={loading} />
        <MetricCard title="CR PreLend (24ч)"    value={pl.cr_24h ? `${(pl.cr_24h * 100).toFixed(2)}%` : '—'} color="yellow" loading={loading} />
      </div>

      {nativeByPlatform && Object.keys(nativeByPlatform).length > 0 && (
        <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 text-sm">
          <div className="font-medium text-gray-200">Platform Native Metrics (Top 3)</div>
          {nativeMetrics.updated_at && (
            <div className="mt-1 text-xs text-gray-500 font-mono">updated: {String(nativeMetrics.updated_at)}</div>
          )}
          <div className="mt-2 space-y-2">
            {Object.entries(nativeByPlatform).map(([platform, pdata]: any) => {
              const top = (pdata?.top_popular_3 || []) as any[]
              if (top.length === 0) return null
              return (
                <div key={platform} className="text-xs text-gray-300">
                  <span className="font-semibold">{String(platform).toUpperCase()}:</span>{' '}
                  {top.map((it, idx) => {
                    const v = it?.metrics?.views
                    const label = typeof v === 'number' ? v.toLocaleString() : 'n/a'
                    return (
                      <span key={`${platform}-${idx}`} className="font-mono">
                        {it?.video_stem || 'unknown'} ({label}){idx < top.length - 1 ? ' | ' : ''}
                      </span>
                    )
                  })}
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="SP агенты: running" value={`${spHealth.running ?? 0}/${spHealth.total ?? 0}`} color="green" loading={loading} />
        <MetricCard title="SP running ratio" value={runningRatio} color={runningRatioColor} loading={loading} />
        <MetricCard title="PL analyst verdicts" value={agentMetrics.analyst_verdicts_count ?? '—'} color="purple" loading={loading} />
        <MetricCard title="Strategist recs" value={agentMetrics.strategist_recs_count ?? '—'} color="yellow" loading={loading} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Plan apply rate (30d)" value={fmtPct(decisionMetrics.plan_apply_rate_30d)} color={planApplyColor} loading={loading} />
        <MetricCard title="Plan success 24h (30d)" value={fmtPct(decisionMetrics.plan_success_24h_rate_30d)} color={planSuccessColor} loading={loading} />
        <MetricCard title="Rollback rate (30d)" value={fmtPct(decisionMetrics.rollback_rate_30d)} color={rollbackColor} loading={loading} />
        <MetricCard title="Patch success (30d)" value={fmtPct(decisionMetrics.patch_apply_success_rate_30d)} color={patchSuccessColor} loading={loading} />
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
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
            <div className="rounded border border-gray-700 bg-gray-900/70 px-2 py-1">
              Длительность: <span className={`font-mono ${cycleDurationColor === 'green' ? 'text-green-300' : cycleDurationColor === 'yellow' ? 'text-yellow-300' : cycleDurationColor === 'red' ? 'text-red-300' : 'text-gray-300'}`}>{cycleDurationSec}</span>
            </div>
            <div className="rounded border border-gray-700 bg-gray-900/70 px-2 py-1">
              Команд обработано: <span className="font-mono text-gray-300">{cycleSummary.commands_processed ?? 0}</span>
            </div>
            <div className="rounded border border-gray-700 bg-gray-900/70 px-2 py-1">
              SP pipeline: <span className={`font-mono ${pipelineColor === 'green' ? 'text-green-300' : pipelineColor === 'yellow' ? 'text-yellow-300' : pipelineColor === 'red' ? 'text-red-300' : 'text-gray-300'}`}>{spPipelineStatus}</span>
            </div>
            <div className="rounded border border-gray-700 bg-gray-900/70 px-2 py-1">
              Supply requests: <span className="font-mono text-gray-300">{cycleSummary.supply_requests ?? 0}</span>
            </div>
          </div>
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
          <div className="mt-2 text-xs text-gray-400">
            PL traffic alive: <span className={`font-mono ${trafficAliveColor === 'green' ? 'text-green-300' : trafficAliveColor === 'red' ? 'text-red-300' : 'text-gray-300'}`}>{String(agentMetrics.traffic_alive ?? '—')}</span>
            {' · '}
            Last click ago: <span className={`font-mono ${trafficGapColor === 'green' ? 'text-green-300' : trafficGapColor === 'yellow' ? 'text-yellow-300' : trafficGapColor === 'red' ? 'text-red-300' : 'text-gray-300'}`}>{agentMetrics.last_click_ago_sec ?? '—'} sec</span>
          </div>
          {nodeDurations && Object.keys(nodeDurations).length > 0 && (
            <div className="mt-2 text-xs text-gray-400">
              Node durations:{' '}
              <span className="font-mono text-gray-300">
                {Object.entries(nodeDurations).map(([k, v]) => `${k}=${v}s`).join(' · ')}
              </span>
            </div>
          )}
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

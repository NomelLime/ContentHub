import React, { useCallback, useEffect, useState } from 'react'
import { system as systemApi } from '../../lib/api'

type SectionStatus = 'ok' | 'degraded' | 'down' | 'unknown' | string

interface HealthPayload {
  timestamp: string
  prelend: Record<string, unknown>
  shorts_project: Record<string, unknown>
  orchestrator: Record<string, unknown>
}

function cardClass(status: SectionStatus): string {
  const s = String(status).toLowerCase()
  if (s === 'ok') return 'bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800'
  if (s === 'degraded' || s === 'unknown') return 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/30 dark:border-yellow-800'
  return 'bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800'
}

function dotClass(status: SectionStatus): string {
  const s = String(status).toLowerCase()
  if (s === 'ok') return 'bg-green-500'
  if (s === 'degraded' || s === 'unknown') return 'bg-yellow-500'
  return 'bg-red-500'
}

export default function SystemHealth() {
  const [data, setData] = useState<HealthPayload | null>(null)
  const [updated, setUpdated] = useState<string>('')

  const load = useCallback(() => {
    systemApi
      .health()
      .then((h) => {
        setData(h as HealthPayload)
        setUpdated(new Date().toLocaleTimeString('ru'))
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [load])

  if (!data) {
    return (
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-sm text-gray-500">
        Загрузка системного health…
      </div>
    )
  }

  const pl = data.prelend || {}
  const sp = data.shorts_project || {}
  const orc = data.orchestrator || {}

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Состояние системы</h2>
        <span className="text-xs text-gray-500">
          Обновлено: {updated} · авто каждые 30с
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={`rounded-lg border p-4 ${cardClass(pl.status as SectionStatus)}`}>
          <div className="flex items-center gap-2 font-medium">
            <span className={`h-2.5 w-2.5 rounded-full ${dotClass(pl.status as SectionStatus)}`} />
            PreLend
          </div>
          <ul className="mt-2 text-sm text-gray-700 dark:text-gray-300 space-y-1">
            <li>API: {pl.api_available ? 'да' : 'нет'}</li>
            <li>Клики 24ч: {String(pl.clicks_24h ?? '—')}</li>
            <li>Конв. 24ч: {String(pl.conversions_24h ?? '—')}</li>
            <li>Bot%: {typeof pl.bot_pct === 'number' ? `${(pl.bot_pct * 100).toFixed(1)}%` : '—'}</li>
            <li>
              Лендинги: {String(pl.landing_up_count ?? 0)}/{String(pl.landing_total ?? 0)}
            </li>
            {pl.response_ms != null && <li>Ответ API: {String(pl.response_ms)} ms</li>}
          </ul>
        </div>

        <div className={`rounded-lg border p-4 ${cardClass(sp.status as SectionStatus)}`}>
          <div className="flex items-center gap-2 font-medium">
            <span className={`h-2.5 w-2.5 rounded-full ${dotClass(sp.status as SectionStatus)}`} />
            ShortsProject
          </div>
          <ul className="mt-2 text-sm text-gray-700 dark:text-gray-300 space-y-1">
            <li>
              Агенты: {String(sp.agents_running ?? 0)}/{String(sp.agents_total ?? 0)}
            </li>
            <li>Загрузок 24ч: {String(sp.uploads_24h ?? 0)}</li>
            <li>Pipeline: {(sp.pipeline_running as boolean) ? 'активен' : 'нет'}</li>
            {(Array.isArray(sp.agents_in_error) && sp.agents_in_error.length > 0) && (
              <li className="text-amber-800 dark:text-amber-200 truncate" title={sp.agents_in_error.join(', ')}>
                Ошибки: {sp.agents_in_error.slice(0, 2).join(', ')}
                {sp.agents_in_error.length > 2 ? '…' : ''}
              </li>
            )}
          </ul>
        </div>

        <div className={`rounded-lg border p-4 ${cardClass(orc.status as SectionStatus)}`}>
          <div className="flex items-center gap-2 font-medium">
            <span className={`h-2.5 w-2.5 rounded-full ${dotClass(orc.status as SectionStatus)}`} />
            Orchestrator
          </div>
          <ul className="mt-2 text-sm text-gray-700 dark:text-gray-300 space-y-1">
            <li>Патчи pending: {String(orc.pending_patches ?? 0)}</li>
            <li>Команд pending: {String(orc.pending_commands ?? 0)}</li>
            <li>Последний план: {orc.last_cycle_at ? String(orc.last_cycle_at).slice(0, 19) : '—'}</li>
            <li>Зон: {orc.zones && typeof orc.zones === 'object' ? Object.keys(orc.zones as object).length : 0}</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

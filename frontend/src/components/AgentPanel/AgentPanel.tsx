/**
 * AgentPanel — карточки агентов с кнопками старт/стоп
 */

import React, { useState } from 'react'
import { agents as agentsApi } from '../../lib/api'
import clsx from 'clsx'

const STATUS_COLOR: Record<string, string> = {
  RUNNING: 'bg-green-500',
  IDLE:    'bg-blue-500',
  WAITING: 'bg-yellow-500',
  ERROR:   'bg-red-500',
  STOPPED: 'bg-gray-500',
  UNKNOWN: 'bg-gray-700',
}

interface Agent {
  name:       string
  project:    string
  status:     string
  updated_at: string | null
  error:      string | null
}

interface Props {
  data: { ShortsProject: Agent[]; PreLend: Agent[] }
  canControl: boolean
}

export default function AgentPanel({ data, canControl }: Props) {
  const [loading, setLoading] = useState<string | null>(null)
  const [msg, setMsg]         = useState<string | null>(null)

  const action = async (project: string, name: string, action: 'start' | 'stop') => {
    const key = `${project}/${name}`
    setLoading(key)
    setMsg(null)
    try {
      if (action === 'start') await agentsApi.start(project, name)
      else                    await agentsApi.stop(project, name)
      setMsg(`✓ ${action === 'start' ? 'Старт' : 'Стоп'}-сигнал отправлен → ${name}`)
    } catch (e: any) {
      setMsg(`✗ Ошибка: ${e.message}`)
    } finally {
      setLoading(null)
    }
  }

  const renderSection = (title: string, agentList: Agent[]) => (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {agentList.map((ag) => {
          const key = `${ag.project}/${ag.name}`
          const isRunning = ag.status === 'RUNNING'
          return (
            <div key={key} className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="flex items-center gap-2 mb-2">
                <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', STATUS_COLOR[ag.status] || 'bg-gray-600')} />
                <span className="text-sm font-medium truncate">{ag.name}</span>
              </div>
              <div className="text-xs text-gray-500 mb-3">{ag.status}</div>
              {ag.error && (
                <div className="text-xs text-red-400 mb-2 truncate" title={ag.error}>
                  {ag.error}
                </div>
              )}
              {canControl && (
                <div className="flex gap-1">
                  <button
                    onClick={() => action(ag.project, ag.name, 'start')}
                    disabled={!!loading || isRunning}
                    className="flex-1 px-2 py-1 text-xs bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors"
                  >
                    {loading === key ? '…' : '▶'}
                  </button>
                  <button
                    onClick={() => action(ag.project, ag.name, 'stop')}
                    disabled={!!loading || !isRunning}
                    className="flex-1 px-2 py-1 text-xs bg-red-800 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors"
                  >
                    {loading === key ? '…' : '■'}
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )

  return (
    <div>
      {msg && (
        <div className={clsx(
          'mb-4 p-3 rounded text-sm',
          msg.startsWith('✓') ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'
        )}>
          {msg}
        </div>
      )}
      {renderSection('ShortsProject', data.ShortsProject || [])}
      {renderSection('PreLend', data.PreLend || [])}
    </div>
  )
}

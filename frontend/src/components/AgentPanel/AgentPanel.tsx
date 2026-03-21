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

const AGENT_DESCRIPTIONS: Record<string, string> = {
  // ShortsProject
  director: 'Координирует пайплайн ShortsProject и распределяет задачи между агентами.',
  sentinel: 'Следит за сбоями и аномалиями, поднимает предупреждения.',
  scout: 'Ищет свежие идеи, темы и входящие сигналы для контента.',
  curator: 'Отбирает и структурирует кандидаты в контент-план.',
  visionary: 'Формирует гипотезы роста и направления экспериментов.',
  narrator: 'Подготавливает текстовую подачу и структуру сценариев.',
  editor: 'Проверяет и улучшает итоговые материалы перед публикацией.',
  strategist: 'Планирует тактику публикаций и приоритеты задач.',
  guardian: 'Контролирует соблюдение правил, лимитов и безопасных режимов.',
  accountant: 'Сводит метрики эффективности и базовую экономику контента.',
  publisher: 'Отвечает за публикацию и выпуск готовых материалов.',
  commander: 'Управляет исполнением этапов и команд в проекте.',
  trend_scout: 'Отслеживает тренды и изменения спроса по контенту.',
  // PreLend
  analyst: 'Анализирует трафик/конверсии и даёт выводы по качеству.',
  monitor: 'Мониторит состояние системы, алерты и отклонения по метрикам.',
  offer_rotator: 'Ротирует офферы по правилам эффективности и рисков.',
}

function getAgentDescription(name: string): string {
  const key = name.trim().toLowerCase()
  return AGENT_DESCRIPTIONS[key] || 'Системный агент проекта. Описание для него пока не заполнено.'
}

export default function AgentPanel({ data, canControl }: Props) {
  const [loading, setLoading] = useState<string | null>(null)
  const [msg, setMsg]         = useState<string | null>(null)
  const [helpOpen, setHelpOpen] = useState<string | null>(null)

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
          const isHelpOpen = helpOpen === key
          return (
            <div key={key} className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="flex items-center gap-2 mb-2">
                <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', STATUS_COLOR[ag.status] || 'bg-gray-600')} />
                <span className="text-sm font-medium truncate">{ag.name}</span>
                <button
                  type="button"
                  onClick={() => setHelpOpen(isHelpOpen ? null : key)}
                  className="ml-auto w-5 h-5 rounded-full text-[10px] bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors"
                  title="Описание агента"
                  aria-label={`Описание агента ${ag.name}`}
                >
                  ?
                </button>
              </div>
              <div className="text-xs text-gray-500 mb-3">{ag.status}</div>
              {isHelpOpen && (
                <div className="text-xs text-gray-300 bg-gray-900/60 border border-gray-700 rounded p-2 mb-3 leading-relaxed">
                  {getAgentDescription(ag.name)}
                </div>
              )}
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

/**
 * AlertFeed — real-time поток уведомлений через WebSocket
 */

import React, { useState, useCallback } from 'react'
import { useWebSocket } from '../../hooks/useWebSocket'
import clsx from 'clsx'

interface Alert {
  id:         number
  level:      string
  category:   string
  message:    string
  created_at: string
}

const LEVEL_STYLE: Record<string, string> = {
  info:    'border-blue-500/50   bg-blue-900/20   text-blue-300',
  warning: 'border-yellow-500/50 bg-yellow-900/20 text-yellow-300',
  error:   'border-red-500/50    bg-red-900/20    text-red-300',
}

const MAX_ALERTS = 50

export default function AlertFeed() {
  const [alerts, setAlerts] = useState<Alert[]>([])

  const handleAlert = useCallback((data: Alert) => {
    setAlerts((prev) => [data, ...prev].slice(0, MAX_ALERTS))
  }, [])

  useWebSocket(['alerts'], { alerts: handleAlert })

  if (!alerts.length) {
    return (
      <div className="text-gray-600 text-center py-8 text-sm">
        Ожидание уведомлений…
      </div>
    )
  }

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {alerts.map((a, i) => (
        <div
          key={`${a.id}-${i}`}
          className={clsx('rounded border px-3 py-2 text-sm', LEVEL_STYLE[a.level] || LEVEL_STYLE.info)}
        >
          <div className="flex items-start justify-between gap-2">
            <span className="flex-1">{a.message}</span>
            <span className="text-xs opacity-60 flex-shrink-0">
              {new Date(a.created_at).toLocaleTimeString('ru')}
            </span>
          </div>
          {a.category && (
            <div className="text-xs opacity-50 mt-0.5">{a.category}</div>
          )}
        </div>
      ))}
    </div>
  )
}

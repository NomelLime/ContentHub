/**
 * hooks/useWebSocket.ts — хук для WebSocket подписки на каналы ContentHub
 *
 * Аутентификация: токен передаётся как query param ?token=<JWT>.
 * Токен читается из памяти (getAccessToken) при каждом (ре)коннекте —
 * подхватывает обновлённый токен после refresh.
 */

import { useEffect, useRef, useCallback } from 'react'
import { getAccessToken } from '../lib/api'

type Channel = 'agents' | 'metrics' | 'alerts'
type Handler = (data: any) => void

export function useWebSocket(
  channels: Channel[],
  handlers: Partial<Record<Channel, Handler>>,
) {
  const wsRef    = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    const ch    = channels.join(',')
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'

    // Токен из памяти — читается при каждом (ре)коннекте
    const token = getAccessToken() ?? ''
    const url   = `${proto}://${window.location.host}/ws?channels=${ch}&token=${encodeURIComponent(token)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        const handler = handlers[msg.channel as Channel]
        if (handler) handler(msg.data)
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = (ev) => {
      // Код 4001 = токен отклонён — не реконнектимся автоматически
      if (ev.code === 4001) {
        console.warn('[WS] Токен отклонён сервером (4001). Требуется повторная авторизация.')
        return
      }
      // Остальные разрывы — реконнект через 3 сек
      retryRef.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    // Keepalive ping каждые 25 сек
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25_000)

    ws.addEventListener('close', () => clearInterval(pingInterval))
  }, [channels.join(',')]) // eslint-disable-line

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      if (retryRef.current) clearTimeout(retryRef.current)
    }
  }, [connect])
}

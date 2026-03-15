/**
 * hooks/useWebSocket.ts — хук для WebSocket подписки на каналы ContentHub
 */

import { useEffect, useRef, useCallback } from 'react'

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
    const url   = `${proto}://${window.location.host}/ws?channels=${ch}`

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

    ws.onclose = () => {
      // Реконнект через 3 сек
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

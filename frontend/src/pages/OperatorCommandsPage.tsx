import React, { useEffect, useState, useCallback } from 'react'
import { operatorCommands } from '../lib/api'

type TraceResp = {
  count: number
  limit: number
  source: string
  events: Record<string, unknown>[]
}

export default function OperatorCommandsPage() {
  const [data, setData] = useState<TraceResp | null>(null)
  const [limit, setLimit] = useState(500)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setErr(null)
    operatorCommands
      .trace(limit)
      .then(setData)
      .catch((e: Error) => setErr(e.message || String(e)))
      .finally(() => setLoading(false))
  }, [limit])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Команды оператора</h1>
        <p className="text-gray-500 text-sm mt-1 max-w-3xl">
          Последние записи из <code className="text-gray-400">policy_command_trace.jsonl</code> (Orchestrator):
          разбор команд из Telegram, коды исходов (ok, llm_empty, …).
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-gray-400">
          Строк:
          <select
            className="ml-2 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-sm"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            {[200, 500, 1000, 2000, 5000].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={load}
          className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm hover:bg-indigo-500"
        >
          Обновить
        </button>
        {data && (
          <span className="text-xs text-gray-500">
            Записей: {data.count} · источник: <span className="font-mono">{data.source}</span>
          </span>
        )}
      </div>

      {err && <div className="rounded border border-red-900/50 bg-red-950/40 p-3 text-sm text-red-200">{err}</div>}

      {loading && <p className="text-gray-500">Загрузка…</p>}

      {!loading && data && data.events.length === 0 && (
        <p className="text-gray-500">Файл трейса пуст или отсутствует (ещё не было команд в этом цикле разработки).</p>
      )}

      {!loading && data && data.events.length > 0 && (
        <div className="space-y-3">
          {data.events.map((ev, i) => (
            <pre
              key={i}
              className="overflow-x-auto rounded-lg border border-gray-700 bg-gray-900/80 p-3 text-xs text-gray-200 font-mono"
            >
              {JSON.stringify(ev, null, 2)}
            </pre>
          ))}
        </div>
      )}
    </div>
  )
}

import React, { useEffect, useState, useCallback } from 'react'
// [FIX#3] getUserRole() вместо localStorage.getItem('role')
import { patches as patchesApi, getUserRole } from '../lib/api'

// ── DiffViewer (inline, без npm зависимостей) ─────────────────────────────────

function DiffViewer({ original, patched }: { original: string; patched: string }) {
  const origLines    = original.split('\n')
  const patchedLines = patched.split('\n')
  const maxLen       = Math.max(origLines.length, patchedLines.length)

  return (
    <div className="grid grid-cols-2 gap-1 text-xs font-mono overflow-auto max-h-96">
      <div className="space-y-0.5">
        <div className="text-gray-400 px-2 py-1 bg-gray-700/50 rounded text-center">До</div>
        {Array.from({ length: maxLen }, (_, i) => {
          const line    = origLines[i] ?? ''
          const changed = line !== (patchedLines[i] ?? '')
          return (
            <div
              key={i}
              className={`px-2 py-0.5 rounded whitespace-pre-wrap break-all ${
                changed ? 'bg-red-900/40 text-red-300' : 'text-gray-300'
              }`}
            >
              {line || '\u00a0'}
            </div>
          )
        })}
      </div>
      <div className="space-y-0.5">
        <div className="text-gray-400 px-2 py-1 bg-gray-700/50 rounded text-center">После</div>
        {Array.from({ length: maxLen }, (_, i) => {
          const line    = patchedLines[i] ?? ''
          const changed = line !== (origLines[i] ?? '')
          return (
            <div
              key={i}
              className={`px-2 py-0.5 rounded whitespace-pre-wrap break-all ${
                changed ? 'bg-green-900/40 text-green-300' : 'text-gray-300'
              }`}
            >
              {line || '\u00a0'}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── PatchCard ─────────────────────────────────────────────────────────────────

function PatchCard({ patch, canAct, onAction }: {
  patch:    any
  canAct:   boolean
  onAction: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [diffData, setDiffData] = useState<any>(null)
  const [acting,   setActing]   = useState(false)

  const loadDiff = async () => {
    if (!diffData) {
      try {
        const d = await patchesApi.diff(patch.id)
        setDiffData(d)
      } catch { /* ignore */ }
    }
    setExpanded(v => !v)
  }

  const act = async (action: 'approve' | 'reject') => {
    setActing(true)
    try {
      if (action === 'approve') await patchesApi.approve(patch.id)
      else                      await patchesApi.reject(patch.id)
      onAction()
    } catch (e: any) {
      alert(`Ошибка: ${e.message}`)
    } finally {
      setActing(false)
    }
  }

  const statusColor: Record<string, string> = {
    pending:  'bg-yellow-900/50 text-yellow-300 border-yellow-700/50',
    approved: 'bg-blue-900/50 text-blue-300 border-blue-700/50',
    applied:  'bg-green-900/50 text-green-300 border-green-700/50',
    rejected: 'bg-red-900/50 text-red-300 border-red-700/50',
    failed:   'bg-red-900/50 text-red-300 border-red-700/50',
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <div className="p-4 flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-block text-xs px-2 py-0.5 rounded border ${statusColor[patch.status] || 'bg-gray-700 text-gray-300 border-gray-600'}`}>
              {patch.status}
            </span>
            <span className="text-xs text-gray-500">#{patch.id} · {patch.repo ?? 'ShortsProject'}</span>
          </div>
          <p className="text-sm font-medium truncate">{patch.file_path}</p>
          <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{patch.goal}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={loadDiff}
            className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            {diffData && expanded ? 'Скрыть' : 'Diff'}
          </button>
          {canAct && patch.status === 'pending' && (
            <>
              <button
                onClick={() => act('approve')}
                disabled={acting}
                className="px-3 py-1.5 text-xs bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded-lg transition-colors"
              >
                ✓ Одобрить
              </button>
              <button
                onClick={() => act('reject')}
                disabled={acting}
                className="px-3 py-1.5 text-xs bg-red-800 hover:bg-red-700 disabled:opacity-50 rounded-lg transition-colors"
              >
                ✗ Отклонить
              </button>
            </>
          )}
        </div>
      </div>

      {expanded && diffData && (
        <div className="border-t border-gray-700 p-4">
          <DiffViewer
            original={diffData.original_code ?? ''}
            patched={diffData.patched_code ?? ''}
          />
        </div>
      )}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function PatchesPage() {
  const [data,    setData]    = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  // [FIX#3] role берём из in-memory модуля, не из localStorage
  const role   = getUserRole()
  const canAct = role === 'admin' || role === 'operator'

  const load = () => {
    setLoading(true)
    // #region agent log
    fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'pages-debug-1',hypothesisId:'H3',location:'src/pages/PatchesPage.tsx:load',message:'patches load invoked',data:{hasList:!!patchesApi?.list},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    patchesApi.list()
      .then(d => { setData(d); setLoading(false) })
      .catch((e: any) => {
        // #region agent log
        fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'pages-debug-1',hypothesisId:'H3',location:'src/pages/PatchesPage.tsx:load',message:'patches list failed',data:{message:e?.message||null},timestamp:Date.now()})}).catch(()=>{});
        // #endregion
        setLoading(false)
      })
  }

  useEffect(() => { load() }, [])

  const pending = data.filter(p => p.status === 'pending')
  const rest    = data.filter(p => p.status !== 'pending')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Патчи кода</h1>
        <button
          onClick={load}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
        >
          Обновить
        </button>
      </div>
      <p className="text-gray-500 text-sm">
        Одобрение/отклонение здесь или через Telegram /approve_N — оба канала пишут в orchestrator.db.
        Нажмите «Diff» чтобы увидеть изменения side-by-side.
      </p>

      {loading ? (
        <div className="text-gray-500 text-center py-12">Загрузка…</div>
      ) : data.length === 0 ? (
        <div className="text-gray-500 text-center py-12">Нет патчей</div>
      ) : (
        <>
          {pending.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-yellow-400 mb-3 uppercase tracking-wider">
                Ожидают одобрения ({pending.length})
              </h2>
              <div className="space-y-3">
                {pending.map(p => (
                  <PatchCard key={p.id} patch={p} canAct={canAct} onAction={load} />
                ))}
              </div>
            </section>
          )}
          {rest.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                История ({rest.length})
              </h2>
              <div className="space-y-3">
                {rest.map(p => (
                  <PatchCard key={p.id} patch={p} canAct={canAct} onAction={load} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}

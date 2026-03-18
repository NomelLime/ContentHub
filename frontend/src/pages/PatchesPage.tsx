import React, { useEffect, useState } from 'react'
import { patches as patchesApi, api } from '../lib/api'

// ── Diff Viewer ────────────────────────────────────────────────────────────────

function DiffViewer({ original, patched }: { original: string; patched: string }) {
  const origLines = original.split('\n')
  const patchLines = patched.split('\n')
  const maxLen = Math.max(origLines.length, patchLines.length)

  return (
    <div className="grid grid-cols-2 gap-0 font-mono text-xs overflow-auto max-h-96 border border-gray-700 rounded-lg">
      <div className="border-r border-gray-700">
        <div className="px-3 py-1.5 bg-gray-800 text-gray-400 border-b border-gray-700 sticky top-0">
          Оригинал
        </div>
        {origLines.map((line, i) => {
          const pLine = patchLines[i] ?? ''
          const changed = line !== pLine
          return (
            <div key={i} className={`flex px-3 py-0.5 ${changed ? 'bg-red-950/40' : ''}`}>
              <span className="text-gray-600 w-8 shrink-0 select-none">{i + 1}</span>
              <span className={`whitespace-pre-wrap break-all ${changed ? 'text-red-300' : 'text-gray-300'}`}>
                {line || '\u00a0'}
              </span>
            </div>
          )
        })}
      </div>
      <div>
        <div className="px-3 py-1.5 bg-gray-800 text-gray-400 border-b border-gray-700 sticky top-0">
          После патча
        </div>
        {patchLines.map((line, i) => {
          const oLine = origLines[i] ?? ''
          const changed = line !== oLine
          return (
            <div key={i} className={`flex px-3 py-0.5 ${changed ? 'bg-green-950/40' : ''}`}>
              <span className="text-gray-600 w-8 shrink-0 select-none">{i + 1}</span>
              <span className={`whitespace-pre-wrap break-all ${changed ? 'text-green-300' : 'text-gray-300'}`}>
                {line || '\u00a0'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Patch Card ─────────────────────────────────────────────────────────────────

function PatchCard({ patch, canAct, onRefresh }: {
  patch: any
  canAct: boolean
  onRefresh: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [diffData, setDiffData] = useState<any>(null)
  const [loadingDiff, setLoadingDiff] = useState(false)
  const [acting, setActing] = useState(false)

  const statusColor: Record<string, string> = {
    pending:  'bg-yellow-500/20 text-yellow-400',
    approved: 'bg-blue-500/20 text-blue-400',
    applied:  'bg-green-500/20 text-green-400',
    rejected: 'bg-red-500/20 text-red-400',
    failed:   'bg-red-500/20 text-red-400',
  }

  const toggleDiff = async () => {
    if (expanded) { setExpanded(false); return }
    if (!diffData) {
      setLoadingDiff(true)
      try {
        const d = await api.get<any>(`/patches/${patch.id}/diff`)
        setDiffData(d)
      } catch { /* ignore */ }
      setLoadingDiff(false)
    }
    setExpanded(true)
  }

  const act = async (action: 'approve' | 'reject') => {
    setActing(true)
    try {
      if (action === 'approve') await patchesApi.approve(patch.id)
      else await patchesApi.reject(patch.id)
      onRefresh()
    } catch { /* ignore */ } finally {
      setActing(false)
    }
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <div className="p-4 flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-semibold text-white">#{patch.id}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor[patch.status] ?? 'bg-gray-600 text-gray-300'}`}>
              {patch.status}
            </span>
            <span className="text-xs text-gray-500">{patch.repo}</span>
          </div>
          <p className="text-sm text-gray-300 font-mono truncate">{patch.file_path}</p>
          <p className="text-sm text-gray-400 mt-1">{patch.goal}</p>
          <p className="text-xs text-gray-600 mt-1">{patch.created_at}</p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={toggleDiff}
            className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            {loadingDiff ? '…' : expanded ? 'Скрыть' : 'Diff'}
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
  const role   = localStorage.getItem('role')
  const canAct = role === 'admin' || role === 'operator'

  const load = () => {
    setLoading(true)
    patchesApi.list()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const pending  = data.filter(p => p.status === 'pending')
  const rest     = data.filter(p => p.status !== 'pending')

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
        <div className="space-y-4">
          {pending.length > 0 && (
            <>
              <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
                Ожидают одобрения ({pending.length})
              </h2>
              {pending.map(p => (
                <PatchCard key={p.id} patch={p} canAct={canAct} onRefresh={load} />
              ))}
            </>
          )}
          {rest.length > 0 && (
            <>
              <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mt-6">
                История ({rest.length})
              </h2>
              {rest.map(p => (
                <PatchCard key={p.id} patch={p} canAct={canAct} onRefresh={load} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

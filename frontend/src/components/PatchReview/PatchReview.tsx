/**
 * PatchReview — просмотр diff + approve/reject
 */

import React, { useState } from 'react'
import { patches as patchesApi } from '../../lib/api'
import clsx from 'clsx'

interface Patch {
  id:           number
  created_at:   string
  repo:         string
  file_path:    string
  goal:         string
  diff_preview: string | null
  status:       string
}

interface Props {
  data:      Patch[]
  canAct:    boolean
  onRefresh: () => void
}

export default function PatchReview({ data, canAct, onRefresh }: Props) {
  const [expanded,  setExpanded]  = useState<number | null>(null)
  const [loading,   setLoading]   = useState<number | null>(null)
  const [msg,       setMsg]       = useState<string | null>(null)

  const act = async (id: number, action: 'approve' | 'reject') => {
    setLoading(id)
    setMsg(null)
    try {
      if (action === 'approve') await patchesApi.approve(id)
      else                      await patchesApi.reject(id)
      setMsg(`✓ Патч #${id} ${action === 'approve' ? 'одобрен' : 'отклонён'}`)
      onRefresh()
    } catch (e: any) {
      setMsg(`✗ Ошибка: ${e.message}`)
    } finally {
      setLoading(null)
    }
  }

  if (!data.length) {
    return <div className="text-gray-500 text-center py-12">Нет ожидающих патчей</div>
  }

  return (
    <div className="space-y-4">
      {msg && (
        <div className={clsx(
          'p-3 rounded text-sm',
          msg.startsWith('✓') ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'
        )}>
          {msg}
        </div>
      )}
      {data.map((patch) => (
        <div key={patch.id} className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div
            className="flex items-center gap-3 p-4 cursor-pointer hover:bg-gray-750 transition-colors"
            onClick={() => setExpanded(expanded === patch.id ? null : patch.id)}
          >
            <span className={clsx(
              'px-2 py-0.5 text-xs rounded font-mono',
              patch.status === 'pending'  ? 'bg-yellow-900 text-yellow-300' :
              patch.status === 'approved' ? 'bg-green-900 text-green-300'   :
              'bg-gray-700 text-gray-400'
            )}>
              #{patch.id}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{patch.goal}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                {patch.repo} · {patch.file_path} · {new Date(patch.created_at).toLocaleString('ru')}
              </div>
            </div>
            <span className="text-gray-500 text-sm">{expanded === patch.id ? '▲' : '▼'}</span>
          </div>

          {expanded === patch.id && (
            <div className="border-t border-gray-700">
              {patch.diff_preview ? (
                <pre className="text-xs font-mono p-4 overflow-x-auto max-h-96 bg-gray-900 text-gray-300 leading-relaxed">
                  {patch.diff_preview.split('\n').map((line, i) => (
                    <div
                      key={i}
                      className={clsx(
                        line.startsWith('+') && !line.startsWith('+++') ? 'text-green-400' :
                        line.startsWith('-') && !line.startsWith('---') ? 'text-red-400'   :
                        line.startsWith('@@') ? 'text-blue-400' : ''
                      )}
                    >
                      {line}
                    </div>
                  ))}
                </pre>
              ) : (
                <div className="p-4 text-gray-500 text-sm">Diff недоступен</div>
              )}

              {canAct && patch.status === 'pending' && (
                <div className="flex gap-3 p-4 border-t border-gray-700 bg-gray-850">
                  <button
                    onClick={() => act(patch.id, 'approve')}
                    disabled={loading === patch.id}
                    className="flex-1 py-2 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded text-sm font-medium transition-colors"
                  >
                    {loading === patch.id ? 'Применяю…' : '✓ Одобрить'}
                  </button>
                  <button
                    onClick={() => act(patch.id, 'reject')}
                    disabled={loading === patch.id}
                    className="flex-1 py-2 bg-red-800 hover:bg-red-700 disabled:opacity-50 rounded text-sm font-medium transition-colors"
                  >
                    {loading === patch.id ? '…' : '✗ Отклонить'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

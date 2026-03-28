import React, { useEffect, useState } from 'react'
import { configs } from '../../lib/api'

const TARGET_LABELS: Record<string, string> = {
  sp_env: 'ShortsProject .env',
  pl_settings: 'PreLend settings.json',
  pl_advertisers: 'PreLend advertisers.json',
}

type CommitRow = { commit: string; committed_ts: number; subject: string }

export default function ConfigHistory({ canEdit }: { canEdit: boolean }) {
  const [targets, setTargets] = useState<string[]>([])
  const [target, setTarget] = useState('sp_env')
  const [commits, setCommits] = useState<CommitRow[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ commit: string; content: string } | null>(null)
  const [revertBusy, setRevertBusy] = useState<string | null>(null)

  useEffect(() => {
    configs
      .historyTargets()
      .then((r) => {
        setTargets(r.targets || [])
        if (r.targets?.length && !r.targets.includes(target)) setTarget(r.targets[0])
      })
      .catch(() => setTargets(['sp_env', 'pl_settings', 'pl_advertisers']))
  }, [])

  const loadLog = () => {
    setLoading(true)
    setErr(null)
    configs
      .historyLog(target, 50)
      .then((r) => setCommits(r.commits || []))
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadLog()
  }, [target])

  const show = (commit: string) => {
    setErr(null)
    configs
      .historyShow(target, commit)
      .then((r) => setPreview({ commit, content: r.content || '' }))
      .catch((e: Error) => setErr(e.message))
  }

  const revert = (commit: string) => {
    if (!canEdit) return
    if (!window.confirm(`Откатить файл к состоянию коммита ${commit.slice(0, 7)}?`)) return
    setRevertBusy(commit)
    setErr(null)
    configs
      .historyRevert(target, commit)
      .then(() => {
        setPreview(null)
        loadLog()
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setRevertBusy(null))
  }

  return (
    <div className="space-y-4">
      <p className="text-gray-400 text-sm max-w-3xl">
        История изменений отслеживаемых конфигов через git в локальных клонах ShortsProject / PreLend.
        Откат меняет файлы в репозитории и создаёт коммит; для PreLend дополнительно отправляется запрос в
        Internal API.
      </p>

      <div className="flex flex-wrap gap-3 items-center">
        <label className="text-sm text-gray-400">Файл</label>
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white"
        >
          {(targets.length ? targets : Object.keys(TARGET_LABELS)).map((k) => (
            <option key={k} value={k}>
              {TARGET_LABELS[k] || k}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={loadLog}
          className="px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded-lg"
        >
          Обновить
        </button>
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}
      {loading && <div className="text-gray-500 text-sm">Загрузка…</div>}

      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-gray-900 text-left text-gray-400">
              <th className="p-2 font-medium">Коммит</th>
              <th className="p-2 font-medium">Дата</th>
              <th className="p-2 font-medium">Сообщение</th>
              <th className="p-2 font-medium w-40">Действия</th>
            </tr>
          </thead>
          <tbody>
            {commits.length === 0 && !loading && (
              <tr>
                <td colSpan={4} className="p-4 text-gray-500">
                  Нет коммитов (или репозиторий без .git / файл не версионировался).
                </td>
              </tr>
            )}
            {commits.map((c) => (
              <tr key={c.commit} className="border-t border-gray-800 hover:bg-gray-900/50">
                <td className="p-2 font-mono text-xs text-indigo-300">{c.commit.slice(0, 7)}</td>
                <td className="p-2 text-gray-400 whitespace-nowrap">
                  {new Date(c.committed_ts * 1000).toLocaleString()}
                </td>
                <td className="p-2 text-gray-300 break-all">{c.subject}</td>
                <td className="p-2 space-x-2 whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => show(c.commit)}
                    className="text-indigo-400 hover:text-indigo-300 text-xs"
                  >
                    Просмотр
                  </button>
                  {canEdit && (
                    <button
                      type="button"
                      disabled={revertBusy === c.commit}
                      onClick={() => revert(c.commit)}
                      className="text-amber-400 hover:text-amber-300 text-xs disabled:opacity-40"
                    >
                      {revertBusy === c.commit ? '…' : 'Откат'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70">
          <div className="bg-gray-900 border border-gray-700 rounded-xl max-w-4xl w-full max-h-[85vh] flex flex-col shadow-xl">
            <div className="flex justify-between items-center p-4 border-b border-gray-800">
              <span className="text-sm text-gray-300 font-mono">{preview.commit.slice(0, 12)}</span>
              <button
                type="button"
                onClick={() => setPreview(null)}
                className="text-gray-400 hover:text-white text-sm"
              >
                Закрыть
              </button>
            </div>
            <pre className="p-4 overflow-auto text-xs text-gray-200 flex-1 whitespace-pre-wrap break-all">
              {preview.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

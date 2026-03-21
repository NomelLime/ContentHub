/**
 * AdvertiserManager — CRUD таблица рекламодателей PreLend
 */

import React, { useEffect, useState } from 'react'
import { advertisers as advApi } from '../../lib/api'
import clsx from 'clsx'

interface Advertiser {
  id:             string
  name:           string
  url:            string
  rate:           number
  geo:            string[]
  device:         string[]
  status:         string
  backup_offer_id?: string
}

const STATUS_BADGE: Record<string, string> = {
  active:  'bg-green-900 text-green-300',
  paused:  'bg-yellow-900 text-yellow-300',
  deleted: 'bg-red-900 text-red-400',
}

export default function AdvertiserManager({ canEdit }: { canEdit: boolean }) {
  // #region agent log
  fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'pre-fix',hypothesisId:'H1',location:'src/components/AdvertiserManager/AdvertiserManager.tsx:27',message:'AdvertiserManager render entered',data:{canEdit,advApiType:typeof advApi,advApiKeys:advApi?Object.keys(advApi):[]},timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  const [list,    setList]    = useState<Advertiser[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<string | null>(null)
  const [editData, setEditData] = useState<Partial<Advertiser>>({})
  const [msg, setMsg] = useState<string | null>(null)

  const load = () => {
    // #region agent log
    fetch('http://127.0.0.1:7662/ingest/84dec7bc-d1eb-46fc-8bc0-42c57a11b413',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d76426'},body:JSON.stringify({sessionId:'d76426',runId:'pre-fix',hypothesisId:'H2',location:'src/components/AdvertiserManager/AdvertiserManager.tsx:36',message:'load() called before advApi.list',data:{hasListMethod:!!advApi?.list},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    setLoading(true)
    advApi.list().then((data) => { setList(data); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const startEdit = (adv: Advertiser) => {
    setEditing(adv.id)
    setEditData({ ...adv })
  }

  const cancelEdit = () => { setEditing(null); setEditData({}) }

  const save = async () => {
    if (!editing) return
    setMsg(null)
    try {
      await advApi.update(editing, editData)
      setMsg('✓ Сохранено')
      load()
      setEditing(null)
    } catch (e: any) {
      setMsg(`✗ ${e.message}`)
    }
  }

  const del = async (id: string) => {
    if (!confirm('Удалить рекламодателя?')) return
    try {
      await advApi.delete(id)
      load()
    } catch (e: any) {
      setMsg(`✗ ${e.message}`)
    }
  }

  if (loading) return <div className="text-gray-500 text-center py-8">Загрузка…</div>

  return (
    <div>
      {msg && (
        <div className={`mb-4 p-3 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
          {msg}
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-gray-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 text-xs uppercase tracking-wider border-b border-gray-700 bg-gray-800/50">
              <th className="px-4 py-3">Название</th>
              <th className="px-4 py-3">Ставка</th>
              <th className="px-4 py-3">ГЕО</th>
              <th className="px-4 py-3">Статус</th>
              <th className="px-4 py-3">Резерв</th>
              {canEdit && <th className="px-4 py-3">Действия</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {list.map((adv) => (
              <React.Fragment key={adv.id}>
                <tr className="bg-gray-800 hover:bg-gray-750 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium">{adv.name}</div>
                    <div className="text-xs text-gray-500 truncate max-w-xs">{adv.url}</div>
                  </td>
                  <td className="px-4 py-3 font-mono">${adv.rate}</td>
                  <td className="px-4 py-3 text-gray-400">{(adv.geo || []).join(', ') || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={clsx('px-2 py-0.5 rounded text-xs font-medium', STATUS_BADGE[adv.status] || 'bg-gray-700 text-gray-400')}>
                      {adv.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{adv.backup_offer_id || '—'}</td>
                  {canEdit && (
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button onClick={() => startEdit(adv)} className="text-xs text-indigo-400 hover:text-indigo-300">Изменить</button>
                        <button onClick={() => del(adv.id)} className="text-xs text-red-400 hover:text-red-300">Удалить</button>
                      </div>
                    </td>
                  )}
                </tr>
                {editing === adv.id && (
                  <tr>
                    <td colSpan={canEdit ? 6 : 5} className="px-4 py-4 bg-gray-750 border-t border-indigo-500/30">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
                        <label className="block">
                          <span className="text-xs text-gray-400">Ставка ($)</span>
                          <input type="number" step="0.01" value={editData.rate || ''} onChange={(e) => setEditData({ ...editData, rate: parseFloat(e.target.value) })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm" />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">Статус</span>
                          <select value={editData.status || 'active'} onChange={(e) => setEditData({ ...editData, status: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm">
                            <option value="active">active</option>
                            <option value="paused">paused</option>
                          </select>
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">ГЕО (через запятую)</span>
                          <input type="text" value={(editData.geo || []).join(', ')} onChange={(e) => setEditData({ ...editData, geo: e.target.value.split(',').map(s => s.trim()) })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm" />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">ID резервного оффера</span>
                          <input type="text" value={editData.backup_offer_id || ''} onChange={(e) => setEditData({ ...editData, backup_offer_id: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm" placeholder="adv_xxx" />
                        </label>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={save} className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded text-sm">Сохранить</button>
                        <button onClick={cancelEdit} className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm">Отмена</button>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

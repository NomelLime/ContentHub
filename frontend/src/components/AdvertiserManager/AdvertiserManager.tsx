/**
 * AdvertiserManager — CRUD таблица рекламодателей PreLend
 */

import React, { useEffect, useState } from 'react'
import { advertisers as advApi, configs } from '../../lib/api'
import clsx from 'clsx'

interface Advertiser {
  id:             string
  name:           string
  url:            string
  rate:           number
  geo:            string[]
  device:         string[]
  time_from?:     string
  time_to?:       string
  template?:      string
  status:         string
  backup_offer_id?: string
  hmac_secret?:   string
  allowed_ips?:   string[]
  max_postbacks_per_min?: number
}

const STATUS_BADGE: Record<string, string> = {
  active:  'bg-green-900 text-green-300',
  paused:  'bg-yellow-900 text-yellow-300',
  deleted: 'bg-red-900 text-red-400',
}

function generateHmacSecret(length = 48): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  let result = ''
  for (let i = 0; i < bytes.length; i += 1) {
    result += chars[bytes[i] % chars.length]
  }
  return result
}

export default function AdvertiserManager({ canEdit }: { canEdit: boolean }) {
  const [list,    setList]    = useState<Advertiser[]>([])
  const [loading, setLoading] = useState(true)
  const [templateOptions, setTemplateOptions] = useState<{ offers: string[]; cloaked: string[] }>({ offers: ['expert_review'], cloaked: ['expert_review'] })
  const [cloakTemplate, setCloakTemplate] = useState('expert_review')
  const [savingCloak, setSavingCloak] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [editData, setEditData] = useState<Partial<Advertiser>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const [createData, setCreateData] = useState({
    name: '',
    url: '',
    rate: 0,
    geo: '',
    device: '',
    time_from: '00:00',
    time_to: '23:59',
    template: 'expert_review',
    status: 'active',
    backup_offer_id: '',
    hmac_secret: '',
    allowed_ips: '',
    max_postbacks_per_min: 60,
  })

  const load = () => {
    setLoading(true)
    advApi.list().then((data) => { setList(data); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    advApi.templates()
      .then((data) => {
        setTemplateOptions(data)
        const firstOffer = data.offers?.[0] || 'expert_review'
        setCreateData((prev) => ({ ...prev, template: prev.template || firstOffer }))
      })
      .catch(() => {})

    configs.getPLSettings()
      .then((s) => setCloakTemplate(s?.cloak_template || 'expert_review'))
      .catch(() => {})
  }, [])

  const startEdit = (adv: Advertiser) => {
    setEditing(adv.id)
    setEditData({ ...adv })
  }

  const cancelEdit = () => { setEditing(null); setEditData({}) }

  const save = async () => {
    if (!editing) return
    setMsg(null)
    try {
      await advApi.update(editing, {
        ...editData,
        rate: editData.rate !== undefined ? Number(editData.rate) : undefined,
        geo: Array.isArray(editData.geo) ? editData.geo : [],
        device: Array.isArray(editData.device) ? editData.device : [],
        time_from: editData.time_from || undefined,
        time_to: editData.time_to || undefined,
        template: editData.template || undefined,
        backup_offer_id: editData.backup_offer_id || undefined,
        hmac_secret: editData.hmac_secret || undefined,
        allowed_ips: Array.isArray(editData.allowed_ips) ? editData.allowed_ips : [],
        max_postbacks_per_min: editData.max_postbacks_per_min !== undefined
          ? Math.max(1, Number(editData.max_postbacks_per_min))
          : undefined,
      })
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

  const create = async () => {
    setMsg(null)
    if (!createData.name.trim()) {
      setMsg('✗ Укажите название рекламодателя')
      return
    }
    if (!createData.url.trim()) {
      setMsg('✗ Укажите URL рекламодателя')
      return
    }
    try {
      await advApi.create({
        name: createData.name.trim(),
        url: createData.url.trim(),
        rate: Number(createData.rate || 0),
        geo: createData.geo.split(',').map(s => s.trim()).filter(Boolean),
        device: createData.device.split(',').map(s => s.trim()).filter(Boolean),
        time_from: createData.time_from.trim() || '00:00',
        time_to: createData.time_to.trim() || '23:59',
        template: createData.template.trim() || 'expert_review',
        status: createData.status || 'active',
        backup_offer_id: createData.backup_offer_id.trim() || null,
        hmac_secret: createData.hmac_secret.trim() || null,
        allowed_ips: createData.allowed_ips.split(',').map(s => s.trim()).filter(Boolean),
        max_postbacks_per_min: Math.max(1, Number(createData.max_postbacks_per_min || 60)),
      })
      setMsg('✓ Рекламодатель создан')
      setCreateData({
        name: '',
        url: '',
        rate: 0,
        geo: '',
        device: '',
        time_from: '00:00',
        time_to: '23:59',
        template: 'expert_review',
        status: 'active',
        backup_offer_id: '',
        hmac_secret: '',
        allowed_ips: '',
        max_postbacks_per_min: 60,
      })
      load()
    } catch (e: any) {
      setMsg(`✗ ${e.message}`)
    }
  }

  const saveCloakTemplate = async () => {
    setMsg(null)
    setSavingCloak(true)
    try {
      await configs.putPLSettings({ cloak_template: cloakTemplate })
      setMsg('✓ Шаблон клоаки сохранён')
    } catch (e: any) {
      setMsg(`✗ ${e.message}`)
    } finally {
      setSavingCloak(false)
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

      {canEdit && (
        <div className="mb-4 rounded-xl border border-gray-700 bg-gray-800/50 p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-200">Шаблон клоаки</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <label className="block">
              <span className="text-xs text-gray-400">Cloaked template</span>
              <select
                value={cloakTemplate}
                onChange={(e) => setCloakTemplate(e.target.value)}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              >
                {(templateOptions.cloaked.length ? templateOptions.cloaked : ['expert_review']).map((tpl) => (
                  <option key={tpl} value={tpl}>{tpl}</option>
                ))}
              </select>
            </label>
            <div className="flex items-end">
              <button
                type="button"
                onClick={saveCloakTemplate}
                disabled={savingCloak}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded text-sm"
              >
                {savingCloak ? 'Сохраняю…' : 'Сохранить клоаку'}
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            Этот шаблон используется для клоаки (bot, offgeo, offhours) и показывается вместо оффера.
          </p>

          <h3 className="mb-3 text-sm font-semibold text-gray-200">Новый рекламодатель</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
            <label className="block">
              <span className="text-xs text-gray-400">Название</span>
              <input
                type="text"
                value={createData.name}
                onChange={(e) => setCreateData({ ...createData, name: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="Например, Nutra CPA"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">URL</span>
              <input
                type="text"
                value={createData.url}
                onChange={(e) => setCreateData({ ...createData, url: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="https://..."
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Ставка ($)</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={createData.rate}
                onChange={(e) => setCreateData({ ...createData, rate: Number(e.target.value || 0) })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Статус</span>
              <select
                value={createData.status}
                onChange={(e) => setCreateData({ ...createData, status: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              >
                <option value="active">active</option>
                <option value="paused">paused</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">ГЕО (через запятую)</span>
              <input
                type="text"
                value={createData.geo}
                onChange={(e) => setCreateData({ ...createData, geo: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="US, CA, DE"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Device (через запятую)</span>
              <input
                type="text"
                value={createData.device}
                onChange={(e) => setCreateData({ ...createData, device: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="mobile, desktop"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">ID резервного оффера</span>
              <input
                type="text"
                value={createData.backup_offer_id}
                onChange={(e) => setCreateData({ ...createData, backup_offer_id: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="adv_xxx"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Время c</span>
              <input
                type="time"
                value={createData.time_from}
                onChange={(e) => setCreateData({ ...createData, time_from: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Время до</span>
              <input
                type="time"
                value={createData.time_to}
                onChange={(e) => setCreateData({ ...createData, time_to: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Template</span>
              <select
                value={createData.template}
                onChange={(e) => setCreateData({ ...createData, template: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              >
                {(templateOptions.offers.length ? templateOptions.offers : ['expert_review']).map((tpl) => (
                  <option key={tpl} value={tpl}>{tpl}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">HMAC secret</span>
              <input
                type="text"
                value={createData.hmac_secret}
                onChange={(e) => setCreateData({ ...createData, hmac_secret: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="Оставь пустым для null"
              />
              <button
                type="button"
                onClick={() => setCreateData({ ...createData, hmac_secret: generateHmacSecret() })}
                className="mt-2 px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded border border-gray-600"
              >
                Сгенерировать secret
              </button>
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Allowed IPs (через запятую)</span>
              <input
                type="text"
                value={createData.allowed_ips}
                onChange={(e) => setCreateData({ ...createData, allowed_ips: e.target.value })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="1.2.3.4, 5.6.7.8"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-400">Лимит постбеков/мин</span>
              <input
                type="number"
                min="1"
                value={createData.max_postbacks_per_min}
                onChange={(e) => setCreateData({ ...createData, max_postbacks_per_min: Number(e.target.value || 60) })}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </label>
          </div>
          <button onClick={create} className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded text-sm">
            Добавить рекламодателя
          </button>
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
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-3">
                        <label className="block">
                          <span className="text-xs text-gray-400">Название</span>
                          <input
                            type="text"
                            value={editData.name || ''}
                            onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">URL</span>
                          <input
                            type="text"
                            value={editData.url || ''}
                            onChange={(e) => setEditData({ ...editData, url: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          />
                        </label>
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
                          <span className="text-xs text-gray-400">Device (через запятую)</span>
                          <input
                            type="text"
                            value={(editData.device || []).join(', ')}
                            onChange={(e) => setEditData({ ...editData, device: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">Время c</span>
                          <input
                            type="time"
                            value={editData.time_from || '00:00'}
                            onChange={(e) => setEditData({ ...editData, time_from: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">Время до</span>
                          <input
                            type="time"
                            value={editData.time_to || '23:59'}
                            onChange={(e) => setEditData({ ...editData, time_to: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">Template</span>
                          <select
                            value={editData.template || 'expert_review'}
                            onChange={(e) => setEditData({ ...editData, template: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          >
                            {(templateOptions.offers.length ? templateOptions.offers : ['expert_review']).map((tpl) => (
                              <option key={tpl} value={tpl}>{tpl}</option>
                            ))}
                          </select>
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">ID резервного оффера</span>
                          <input type="text" value={editData.backup_offer_id || ''} onChange={(e) => setEditData({ ...editData, backup_offer_id: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm" placeholder="adv_xxx" />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">HMAC secret</span>
                          <input
                            type="text"
                            value={editData.hmac_secret || ''}
                            onChange={(e) => setEditData({ ...editData, hmac_secret: e.target.value })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                            placeholder="Оставь пустым чтобы не менять"
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">Allowed IPs (через запятую)</span>
                          <input
                            type="text"
                            value={(editData.allowed_ips || []).join(', ')}
                            onChange={(e) => setEditData({ ...editData, allowed_ips: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs text-gray-400">Лимит постбеков/мин</span>
                          <input
                            type="number"
                            min="1"
                            value={editData.max_postbacks_per_min || 60}
                            onChange={(e) => setEditData({ ...editData, max_postbacks_per_min: Number(e.target.value || 60) })}
                            className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                          />
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

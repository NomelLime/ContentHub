import React, { useEffect, useMemo, useState } from 'react'
import { dashboard as dashApi } from '../lib/api'

type Row = {
  platform: string
  account_name: string
  video_stem: string
  url: string
  uploaded_at?: string
  collected_at?: string
  metrics?: {
    views?: number | null
    likes?: number | null
    comments?: number | null
    engagement_rate?: number | null
  }
}

type SortKey = 'uploaded_at' | 'views' | 'likes' | 'comments' | 'engagement_rate'

export default function PlatformNativeMetricsPage() {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  const [platformFilter, setPlatformFilter] = useState('all')
  const [accountFilter, setAccountFilter] = useState('all')
  const [sortBy, setSortBy] = useState<SortKey>('views')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await dashApi.get()
        const sp = res?.data?.sp || {}
        const native = sp?.platform_native_metrics || {}
        const byPlatform = native?.by_platform || {}
        const allRows: Row[] = []
        Object.entries(byPlatform).forEach(([platform, pdata]: any) => {
          const recent = (pdata?.recent_20 || []) as any[]
          recent.forEach((r) => {
            allRows.push({
              platform,
              account_name: r?.account_name || 'unknown',
              video_stem: r?.video_stem || 'unknown',
              url: r?.url || '',
              uploaded_at: r?.uploaded_at,
              collected_at: r?.collected_at,
              metrics: r?.metrics || {},
            })
          })
        })
        setRows(allRows)
        setUpdatedAt(native?.updated_at || null)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const platforms = useMemo(
    () => ['all', ...Array.from(new Set(rows.map((r) => r.platform))).sort()],
    [rows],
  )
  const accounts = useMemo(
    () => ['all', ...Array.from(new Set(rows.map((r) => r.account_name))).sort()],
    [rows],
  )

  const filtered = useMemo(() => {
    let out = rows
    if (platformFilter !== 'all') out = out.filter((r) => r.platform === platformFilter)
    if (accountFilter !== 'all') out = out.filter((r) => r.account_name === accountFilter)

    const getNum = (r: Row, key: SortKey): number => {
      if (key === 'uploaded_at') return new Date(r.uploaded_at || 0).getTime()
      return Number(r.metrics?.[key] ?? -1)
    }
    out = [...out].sort((a, b) => {
      const av = getNum(a, sortBy)
      const bv = getNum(b, sortBy)
      return sortDir === 'desc' ? bv - av : av - bv
    })
    return out
  }, [rows, platformFilter, accountFilter, sortBy, sortDir])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Platform Native Metrics</h1>
        <p className="text-gray-500 text-sm mt-1">
          {updatedAt ? `Обновлено: ${new Date(updatedAt).toLocaleString('ru')}` : 'Нет данных обновления'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <select className="bg-gray-900 border border-gray-700 rounded px-3 py-2" value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
          {platforms.map((p) => <option key={p} value={p}>{p === 'all' ? 'Все платформы' : p.toUpperCase()}</option>)}
        </select>
        <select className="bg-gray-900 border border-gray-700 rounded px-3 py-2" value={accountFilter} onChange={(e) => setAccountFilter(e.target.value)}>
          {accounts.map((a) => <option key={a} value={a}>{a === 'all' ? 'Все аккаунты' : a}</option>)}
        </select>
        <select className="bg-gray-900 border border-gray-700 rounded px-3 py-2" value={sortBy} onChange={(e) => setSortBy(e.target.value as SortKey)}>
          <option value="views">Сортировка: Views</option>
          <option value="likes">Сортировка: Likes</option>
          <option value="comments">Сортировка: Comments</option>
          <option value="engagement_rate">Сортировка: Engagement Rate</option>
          <option value="uploaded_at">Сортировка: Uploaded At</option>
        </select>
        <select className="bg-gray-900 border border-gray-700 rounded px-3 py-2" value={sortDir} onChange={(e) => setSortDir(e.target.value as 'asc' | 'desc')}>
          <option value="desc">По убыванию</option>
          <option value="asc">По возрастанию</option>
        </select>
      </div>

      <div className="rounded-lg border border-gray-800 overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-gray-300">
            <tr>
              <th className="text-left px-3 py-2">Platform</th>
              <th className="text-left px-3 py-2">Account</th>
              <th className="text-left px-3 py-2">Video</th>
              <th className="text-left px-3 py-2">Views</th>
              <th className="text-left px-3 py-2">Likes</th>
              <th className="text-left px-3 py-2">Comments</th>
              <th className="text-left px-3 py-2">Engagement</th>
              <th className="text-left px-3 py-2">Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td className="px-3 py-3 text-gray-500" colSpan={8}>Загрузка…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td className="px-3 py-3 text-gray-500" colSpan={8}>Нет данных</td></tr>
            ) : (
              filtered.map((r, idx) => (
                <tr key={`${r.platform}-${r.account_name}-${r.video_stem}-${idx}`} className="border-t border-gray-800">
                  <td className="px-3 py-2">{r.platform.toUpperCase()}</td>
                  <td className="px-3 py-2">{r.account_name}</td>
                  <td className="px-3 py-2">
                    <a className="text-blue-300 hover:underline" href={r.url} target="_blank" rel="noreferrer">{r.video_stem}</a>
                  </td>
                  <td className="px-3 py-2">{typeof r.metrics?.views === 'number' ? r.metrics.views.toLocaleString() : '—'}</td>
                  <td className="px-3 py-2">{typeof r.metrics?.likes === 'number' ? r.metrics.likes.toLocaleString() : '—'}</td>
                  <td className="px-3 py-2">{typeof r.metrics?.comments === 'number' ? r.metrics.comments.toLocaleString() : '—'}</td>
                  <td className="px-3 py-2">{typeof r.metrics?.engagement_rate === 'number' ? `${(r.metrics.engagement_rate * 100).toFixed(2)}%` : '—'}</td>
                  <td className="px-3 py-2">{r.uploaded_at ? new Date(r.uploaded_at).toLocaleString('ru') : '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}


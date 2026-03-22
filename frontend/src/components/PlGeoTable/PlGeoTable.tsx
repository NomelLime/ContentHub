/**
 * Таблица PreLend: клики и конверсии по ГЕО с сортировкой по колонкам.
 */

import React, { useEffect, useMemo, useState } from 'react'
import { analytics } from '../../lib/api'

type GeoRow = { geo: string; clicks: number; conversions: number; cr: number }

type SortKey = 'geo' | 'clicks' | 'conversions' | 'cr'

export default function PlGeoTable() {
  const [rows, setRows] = useState<GeoRow[]>([])
  const [period, setPeriod] = useState(24)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('clicks')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    setLoading(true)
    setErr(null)
    analytics
      .pl(period)
      .then((data) => {
        if (!data?.available) {
          setErr(data?.error || 'PreLend недоступен')
          setRows([])
          return
        }
        const br = data.geo_breakdown
        setRows(Array.isArray(br) ? br : [])
      })
      .catch(() => {
        setErr('Не удалось загрузить')
        setRows([])
      })
      .finally(() => setLoading(false))
  }, [period])

  const sorted = useMemo(() => {
    const copy = [...rows]
    const mul = sortDir === 'asc' ? 1 : -1
    copy.sort((a, b) => {
      if (sortKey === 'geo') {
        return mul * a.geo.localeCompare(b.geo, 'en')
      }
      const va = a[sortKey]
      const vb = b[sortKey]
      if (va === vb) return a.geo.localeCompare(b.geo, 'en')
      return mul * (va < vb ? -1 : 1)
    })
    return copy
  }, [rows, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir(key === 'geo' ? 'asc' : 'desc')
    }
  }

  const th = (key: SortKey, label: string) => (
    <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-200 select-none"
        onClick={() => toggleSort(key)}>
      {label}
      {sortKey === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
    </th>
  )

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold">PreLend по ГЕО</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Клики без bot/cloaked; конверсии по статусу клика. Сортировка — по заголовку колонки.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500">Период:</span>
          {[24, 72, 168].map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setPeriod(h)}
              className={`px-2.5 py-1 rounded text-xs ${period === h ? 'bg-indigo-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}`}
            >
              {h === 168 ? '7д' : `${h}ч`}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-32 bg-gray-900/50 animate-pulse rounded" />
      ) : err ? (
        <p className="text-sm text-amber-500">{err}</p>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-gray-500">Нет данных за выбранный период.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-900/80">
              <tr className="border-b border-gray-700">
                {th('geo', 'ГЕО')}
                {th('clicks', 'Клики')}
                {th('conversions', 'Конверсии')}
                {th('cr', 'CR %')}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.geo} className="border-b border-gray-700/80 hover:bg-gray-700/30">
                  <td className="px-3 py-2 font-mono text-gray-200">{r.geo}</td>
                  <td className="px-3 py-2 text-gray-300">{r.clicks.toLocaleString()}</td>
                  <td className="px-3 py-2 text-gray-300">{r.conversions.toLocaleString()}</td>
                  <td className="px-3 py-2 text-violet-300">
                    {(r.cr * 100).toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

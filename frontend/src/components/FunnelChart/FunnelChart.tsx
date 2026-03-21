/**
 * FunnelChart — воронка видео → просмотры → клики → конверсии → деньги
 */

import React, { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { analytics } from '../../lib/api'

const STEPS = [
  { key: 'sp_views',         label: 'Просмотры',   color: '#6366f1' },
  { key: 'pl_clicks',        label: 'Клики',        color: '#8b5cf6' },
  { key: 'pl_conversions',   label: 'Конверсии',    color: '#a78bfa' },
]

export default function FunnelChart() {
  const [data,    setData]    = useState<any>(null)
  const [days,    setDays]    = useState(7)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    analytics.funnel(days).then((res) => {
      setData(res)
      setLoading(false)
    }).catch((e: any) => {
      setLoading(false)
    })
  }, [days])

  const agg = data?.funnel?.[0]  // агрегат если нет детальных линков

  const chartData = agg ? STEPS.map((s) => ({
    name:  s.label,
    value: agg[s.key] || 0,
    color: s.color,
  })) : []

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm text-gray-400">Период:</span>
        {[7, 14, 30].map((d) => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1 rounded text-sm ${days === d ? 'bg-indigo-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}`}>
            {d}д
          </button>
        ))}
      </div>

      {loading ? (
        <div className="h-48 bg-gray-800 animate-pulse rounded" />
      ) : chartData.length ? (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 60 }}>
            <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 12 }} />
            <YAxis dataKey="name" type="category" tick={{ fill: '#9ca3af', fontSize: 12 }} />
            <Tooltip
              contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
              labelStyle={{ color: '#f3f4f6' }}
            />
            <Bar dataKey="value" radius={4}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="text-center text-gray-500 py-8 text-sm">
          {data?.funnel?.[0]?.note || 'Нет данных'}
        </div>
      )}

      {agg && (
        <div className="mt-4 grid grid-cols-3 gap-3">
          <div className="bg-gray-800 rounded-lg p-3 text-center">
            <div className="text-xs text-gray-500">CR</div>
            <div className="text-lg font-bold text-purple-400">{((agg.pl_cr || 0) * 100).toFixed(2)}%</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-3 text-center">
            <div className="text-xs text-gray-500">Просмотры → Клики</div>
            <div className="text-lg font-bold text-indigo-400">
              {agg.sp_views > 0 ? ((agg.pl_clicks / agg.sp_views) * 100).toFixed(2) + '%' : '—'}
            </div>
          </div>
          <div className="bg-gray-800 rounded-lg p-3 text-center">
            <div className="text-xs text-gray-500">Конверсий</div>
            <div className="text-lg font-bold text-violet-400">{agg.pl_conversions || 0}</div>
          </div>
        </div>
      )}
    </div>
  )
}

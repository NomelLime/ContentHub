import React from 'react'
import clsx from 'clsx'

interface Props {
  title:    string
  value:    string | number
  sub?:     string
  color?:   'green' | 'blue' | 'yellow' | 'red' | 'purple'
  loading?: boolean
}

const COLOR_MAP = {
  green:  'border-green-500/30 bg-green-900/10',
  blue:   'border-blue-500/30  bg-blue-900/10',
  yellow: 'border-yellow-500/30 bg-yellow-900/10',
  red:    'border-red-500/30   bg-red-900/10',
  purple: 'border-purple-500/30 bg-purple-900/10',
}

export default function MetricCard({ title, value, sub, color = 'blue', loading }: Props) {
  return (
    <div className={clsx(
      'rounded-xl border p-5',
      COLOR_MAP[color],
    )}>
      <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">{title}</div>
      {loading ? (
        <div className="h-8 w-24 bg-gray-700 animate-pulse rounded" />
      ) : (
        <div className="text-2xl font-bold text-white">{value}</div>
      )}
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

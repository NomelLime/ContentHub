import React from 'react'
import FunnelChart from '../components/FunnelChart/FunnelChart'
import PlGeoTable from '../components/PlGeoTable/PlGeoTable'

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Аналитика</h1>

      <PlGeoTable />

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-base font-semibold mb-1">Воронка: Видео → Конверсии</h2>
        <p className="text-xs text-gray-500 mb-5">
          Связка через prelend_sub_id. Для детальной воронки нужен sub_id в uploader.py (Этап 12).
        </p>
        <FunnelChart />
      </div>
    </div>
  )
}

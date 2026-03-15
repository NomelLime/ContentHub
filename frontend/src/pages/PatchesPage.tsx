import React, { useEffect, useState } from 'react'
import { patches as patchesApi } from '../lib/api'
import PatchReview from '../components/PatchReview/PatchReview'

export default function PatchesPage() {
  const [data,    setData]    = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const role    = localStorage.getItem('role')
  const canAct  = role === 'admin' || role === 'operator'

  const load = () => {
    setLoading(true)
    patchesApi.list().then((d) => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Патчи кода</h1>
        <button onClick={load} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
          Обновить
        </button>
      </div>
      <p className="text-gray-500 text-sm">
        Одобрение/отклонение здесь или через Telegram /approve_N — оба канала пишут в orchestrator.db.
      </p>
      {loading ? (
        <div className="text-gray-500 text-center py-12">Загрузка…</div>
      ) : (
        <PatchReview data={data} canAct={canAct} onRefresh={load} />
      )}
    </div>
  )
}

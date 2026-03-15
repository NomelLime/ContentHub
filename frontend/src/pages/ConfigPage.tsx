import React, { useState } from 'react'
import ConfigEditor from '../components/ConfigEditor/ConfigEditor'
import AdvertiserManager from '../components/AdvertiserManager/AdvertiserManager'

const TABS = ['ShortsProject', 'PreLend — Рекламодатели']

export default function ConfigPage() {
  const [tab, setTab]  = useState(0)
  const role           = localStorage.getItem('role')
  const canEdit        = role === 'admin' || role === 'operator'

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Конфигурация</h1>
      <div className="flex gap-2 border-b border-gray-700 pb-0">
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === i
                ? 'border-indigo-500 text-white'
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 0 && (
        <div>
          {!canEdit && (
            <div className="mb-4 p-3 bg-yellow-900/30 border border-yellow-700/50 rounded text-yellow-400 text-sm">
              Только просмотр. Для изменений нужна роль operator или admin.
            </div>
          )}
          <ConfigEditor />
        </div>
      )}

      {tab === 1 && <AdvertiserManager canEdit={canEdit} />}
    </div>
  )
}

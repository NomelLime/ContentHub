import React, { useState } from 'react'
// [FIX#3] getUserRole() вместо localStorage.getItem('role')
import { getUserRole } from '../lib/api'
import ConfigEditor from '../components/ConfigEditor/ConfigEditor'
import AdvertiserManager from '../components/AdvertiserManager/AdvertiserManager'
import AdvertiserCompare from '../components/AdvertiserCompare/AdvertiserCompare'
import ConfigHistory from '../components/ConfigHistory/ConfigHistory'

const TABS = [
  'ShortsProject',
  'PreLend — Рекламодатели',
  'Сравнение по метрикам',
  'История конфигов',
]

export default function ConfigPage() {
  const [tab, setTab] = useState(0)
  // [FIX#3] role берём из in-memory модуля, не из localStorage
  const role    = getUserRole()
  const canEdit = role === 'admin' || role === 'operator'

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Конфигурация</h1>
      <div className="flex flex-wrap gap-1 border-b border-gray-700 pb-0">
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            className={`px-3 sm:px-5 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors ${
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

      {tab === 2 && <AdvertiserCompare />}

      {tab === 3 && (
        <div>
          {!canEdit && (
            <div className="mb-4 p-3 bg-yellow-900/30 border border-yellow-700/50 rounded text-yellow-400 text-sm">
              Откат к старой версии доступен только ролям operator и admin. Просмотр истории и diff — для всех
              ролей.
            </div>
          )}
          <ConfigHistory canEdit={canEdit} />
        </div>
      )}
    </div>
  )
}

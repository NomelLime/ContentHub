/**
 * ConfigEditor — форм-редактор конфигов по секциям
 */

import React, { useEffect, useState } from 'react'
import { configs } from '../../lib/api'

interface Field {
  env_key: string
  label:   string
  type:    string
  value:   string | null
}

interface Section {
  [key: string]: Field[]
}

const SECTION_LABELS: Record<string, string> = {
  vl:          'VL-анализ (Qwen)',
  ab_test:     'A/B тестирование',
  upload:      'Лимиты загрузок',
  tts:         'TTS / Голос',
  activity:    'Планировщик активности',
  dedup:       'Дедупликация',
  quarantine:  'Карантин аккаунтов',
  subtitle:    'Субтитры (Whisper)',
  voice_clone: 'Голосовой клон (OpenVoice)',
  trend_scout: 'TrendScout агент',
}

export default function ConfigEditor() {
  const [sections, setSections]   = useState<Section>({})
  const [edits, setEdits]         = useState<Record<string, Record<string, string>>>({})
  const [saving, setSaving]       = useState<string | null>(null)
  const [msg, setMsg]             = useState<string | null>(null)
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    configs.getSP().then((data) => {
      setSections(data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const handleChange = (section: string, envKey: string, value: string) => {
    setEdits((prev) => ({
      ...prev,
      [section]: { ...(prev[section] || {}), [envKey]: value },
    }))
  }

  const save = async (section: string) => {
    const updates = edits[section]
    if (!updates || !Object.keys(updates).length) return
    setSaving(section)
    setMsg(null)
    try {
      await configs.updateSP(section, updates)
      setMsg(`✓ Секция "${SECTION_LABELS[section] || section}" сохранена`)
      setEdits((prev) => { const n = { ...prev }; delete n[section]; return n })
    } catch (e: any) {
      setMsg(`✗ Ошибка: ${e.message}`)
    } finally {
      setSaving(null)
    }
  }

  const renderField = (section: string, field: Field) => {
    const currentVal = edits[section]?.[field.env_key] ?? field.value ?? ''
    const placeholder = '(дефолт из config.py)'

    if (field.type === 'bool') {
      return (
        <label key={field.env_key} className="flex items-center gap-3 py-2">
          <input
            type="checkbox"
            checked={currentVal === '1' || currentVal === 'true'}
            onChange={(e) => handleChange(section, field.env_key, e.target.checked ? '1' : '0')}
            className="w-4 h-4 accent-indigo-500"
          />
          <span className="text-sm text-gray-300">{field.label}</span>
        </label>
      )
    }

    return (
      <div key={field.env_key} className="py-2">
        <label className="block text-xs text-gray-400 mb-1">{field.label}</label>
        <input
          type={field.type === 'int' || field.type === 'float' ? 'number' : 'text'}
          step={field.type === 'float' ? '0.01' : '1'}
          value={currentVal}
          placeholder={placeholder}
          onChange={(e) => handleChange(section, field.env_key, e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
        />
      </div>
    )
  }

  if (loading) return <div className="text-gray-500 text-center py-8">Загрузка…</div>

  return (
    <div className="space-y-6">
      {msg && (
        <div className={`p-3 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
          {msg}
        </div>
      )}
      {Object.entries(sections).map(([sectionKey, fields]) => (
        <div key={sectionKey} className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-700 bg-gray-750">
            <h3 className="font-medium">{SECTION_LABELS[sectionKey] || sectionKey}</h3>
            {edits[sectionKey] && Object.keys(edits[sectionKey]).length > 0 && (
              <button
                onClick={() => save(sectionKey)}
                disabled={saving === sectionKey}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded text-sm font-medium transition-colors"
              >
                {saving === sectionKey ? 'Сохраняю…' : 'Сохранить'}
              </button>
            )}
          </div>
          <div className="px-5 divide-y divide-gray-700/50">
            {fields.map((field) => renderField(sectionKey, field))}
          </div>
        </div>
      ))}
    </div>
  )
}

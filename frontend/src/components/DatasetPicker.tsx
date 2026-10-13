import { useEffect, useState } from 'react'
import { listDatasets } from '../services/api'
import type { DatasetListItem } from '../types'

interface DatasetPickerProps {
  value: string
  onChange: (id: string) => void
  theme?: 'light' | 'dark'
  className?: string
}

export default function DatasetPicker({
  value,
  onChange,
  theme = 'light',
  className = '',
}: DatasetPickerProps) {
  const [datasets, setDatasets] = useState<DatasetListItem[]>([])

  useEffect(() => {
    listDatasets()
      .then((r) => {
        setDatasets(r.datasets || [])
        if (!value && r.datasets && r.datasets.length > 0) onChange(r.datasets[0].dataset_id)
      })
      .catch(() => setDatasets([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const baseClasses =
    theme === 'dark'
      ? 'w-full max-w-xs rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-white focus:outline-none focus:border-brand-500 transition-colors'
      : 'w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 shadow-sm focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-colors'

  return (
    <select
      className={`${baseClasses} ${className}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {datasets.length === 0 && <option value="">No datasets connected yet</option>}
      {datasets.map((d) => (
        <option key={d.dataset_id} value={d.dataset_id}>
          {d.dataset_name} ({d.source_type})
        </option>
      ))}
    </select>
  )
}

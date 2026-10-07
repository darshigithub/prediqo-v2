import { useEffect, useState } from 'react'
import { listDatasets } from '../services/api'
import type { DatasetListItem } from '../types'

interface DatasetPickerProps {
  value: string
  onChange: (id: string) => void
}

export default function DatasetPicker({ value, onChange }: DatasetPickerProps) {
  const [datasets, setDatasets] = useState<DatasetListItem[]>([])

  useEffect(() => {
    listDatasets()
      .then((r) => {
        setDatasets(r.datasets)
        if (!value && r.datasets.length > 0) onChange(r.datasets[0].dataset_id)
      })
      .catch(() => setDatasets([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <select
      className="input max-w-xs"
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

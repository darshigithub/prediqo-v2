import { useState } from 'react'

interface DecisionChecklistCardProps {
  type: 'prediction' | 'forecasting'
  className?: string
}

export default function DecisionChecklistCard({
  type,
  className = '',
}: DecisionChecklistCardProps) {
  const [checkedItems, setCheckedItems] = useState<Record<number, boolean>>({})

  const checklistItems = [
    {
      title: 'Data Freshness & Relevance',
      description:
        'Verify that the dataset represents current business conditions and has not suffered from external regime shifts, structural changes, or stale reporting periods.',
    },
    {
      title: 'Operational Error Tolerance',
      description:
        'Confirm that the model’s average expected error (MAE/RMSE/WAPE) fits within your operational or financial risk tolerance.',
    },
    {
      title: 'Uncertainty & Worst-Case Planning',
      description:
        type === 'forecasting'
          ? 'Review the 80% and 95% confidence intervals to ensure your inventory, budget, or staff can handle lower and upper bound swings.'
          : 'Evaluate alternative class probabilities or residual bounds rather than relying solely on the single top prediction.',
    },
    {
      title: 'Non-Causal Action Review',
      description:
        'Do not treat key feature drivers as direct levers. Modifying an input feature in real operations may not produce the predicted statistical uplift.',
    },
    {
      title: 'Human-in-the-Loop Validation',
      description:
        'Cross-check the model recommendation with domain experts before executing major commitments, pricing changes, or automated actions.',
    },
  ]

  const toggleCheck = (idx: number) => {
    setCheckedItems((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }

  const completedCount = Object.values(checkedItems).filter(Boolean).length

  return (
    <div className={`p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
          <span>📋</span>
          <span>Pre-Decision Operational Checklist</span>
        </h3>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
          {completedCount}/{checklistItems.length} Verified
        </span>
      </div>

      <p className="text-xs text-slate-400">
        Review these operational safeguards before committing resources or making policy changes based on this {type}:
      </p>

      <div className="space-y-2.5">
        {checklistItems.map((item, idx) => {
          const isChecked = !!checkedItems[idx]
          return (
            <div
              key={idx}
              onClick={() => toggleCheck(idx)}
              className={`p-3 rounded-lg border text-xs cursor-pointer transition-all flex items-start gap-3 ${
                isChecked
                  ? 'bg-emerald-500/5 border-emerald-500/30'
                  : 'bg-slate-800/40 border-slate-700/60 hover:bg-slate-800/70'
              }`}
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={() => {}}
                className="mt-0.5 rounded border-slate-700 bg-slate-800 text-emerald-500 focus:ring-emerald-500 cursor-pointer"
              />
              <div className="space-y-0.5 flex-1">
                <span className={`font-semibold block ${isChecked ? 'text-emerald-300' : 'text-slate-200'}`}>
                  {item.title}
                </span>
                <p className="text-slate-400 leading-relaxed text-[11px]">{item.description}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

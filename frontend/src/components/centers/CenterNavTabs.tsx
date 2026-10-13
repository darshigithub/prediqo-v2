export type CenterTabId = 'overview' | 'analytics' | 'explanation' | 'technical'

export interface CenterTabItem {
  id: CenterTabId
  label: string
  icon: string
  description?: string
  badge?: string | number
}

interface CenterNavTabsProps {
  activeTab: CenterTabId
  onChange: (tab: CenterTabId) => void
  disabledTabs?: CenterTabId[]
  className?: string
}

export const CENTER_TABS: CenterTabItem[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: '⊞',
    description: 'Executive summary, scenario input, and reliability',
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: '📊',
    description: 'Model fit, feature insights, and evaluation plots',
  },
  {
    id: 'explanation',
    label: 'AI Explanation',
    icon: '✦',
    description: 'Auditable, narrative-driven business explanation',
  },
  {
    id: 'technical',
    label: 'Technical Details',
    icon: '⚙',
    description: 'Algorithm benchmarks, cross-validation, and diagnostics',
  },
]

export default function CenterNavTabs({
  activeTab,
  onChange,
  disabledTabs = [],
  className = '',
}: CenterNavTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Center Views"
      className={`flex flex-wrap items-center gap-1.5 p-1.5 bg-slate-200/80 rounded-xl border border-slate-300/60 shadow-sm ${className}`}
    >
      {CENTER_TABS.map((tab) => {
        const isActive = activeTab === tab.id
        const isDisabled = disabledTabs.includes(tab.id)

        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`tabpanel-${tab.id}`}
            id={`tab-${tab.id}`}
            type="button"
            disabled={isDisabled}
            onClick={() => onChange(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              isActive
                ? 'bg-white text-brand-700 shadow-sm border border-slate-200/80 font-bold'
                : isDisabled
                ? 'text-slate-400 cursor-not-allowed opacity-60'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
            }`}
          >
            <span className={`text-sm ${isActive ? 'text-brand-600' : 'text-slate-400'}`}>
              {tab.icon}
            </span>
            <span>{tab.label}</span>
            {tab.badge && (
              <span
                className={`ml-1 px-1.5 py-0.5 text-[10px] rounded-full font-bold ${
                  isActive
                    ? 'bg-brand-100 text-brand-700'
                    : 'bg-slate-200 text-slate-600'
                }`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

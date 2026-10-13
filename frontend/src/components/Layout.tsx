import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '▦' },
  { to: '/sources', label: 'Data Sources', icon: '⛁' },
  { to: '/datasets', label: 'Datasets', icon: '☰' },
  { to: '/explorer', label: 'Data Explorer', icon: '⌕' },
  { to: '/analyst', label: 'AI Analyst', icon: '✦' },
  { to: '/prediction', label: 'Prediction Center', icon: '⚡' },
  { to: '/forecasting', label: 'Forecasting Center', icon: '📈' },
  { to: '/decisions', label: 'Decision Center', icon: '⚖' },
  { to: '/charts', label: 'Charts & Builder', icon: '◔' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-slate-100 text-slate-800">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 shadow-xl">
        {/* Brand Header */}
        <div className="px-6 py-5 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center text-white font-bold text-base shadow-md shadow-brand-500/20">
              ✦
            </div>
            <div>
              <div className="text-base font-bold text-white tracking-tight flex items-center gap-1.5">
                <span>Prediqo</span>
              </div>
              <div className="text-[11px] text-slate-400 font-medium">
                AI Analytics & Decisions Platform
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-brand-600 text-white font-semibold shadow-sm shadow-brand-900/50'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/80'
                }`
              }
            >
              <span className="w-4 text-center text-sm opacity-80">{item.icon}</span>
              <span className="flex-1">{item.label}</span>
              
            </NavLink>
          ))}
        </nav>

        {/* Engine Footer */}
        <div className="px-6 py-4 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-medium text-slate-300">Local Engine Active</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">FastAPI + DuckDB</span>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-8 max-w-[1440px] w-full overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}

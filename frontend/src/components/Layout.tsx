import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '▦' },
  { to: '/sources', label: 'Data Sources', icon: '⛁' },
  { to: '/datasets', label: 'Datasets', icon: '☰' },
  { to: '/explorer', label: 'Data Explorer', icon: '⌕' },
  { to: '/analyst', label: 'AI Analyst', icon: '✦' },
  { to: '/prediction', label: 'Prediction', icon: '⚡' },
  { to: '/charts', label: 'Charts', icon: '◔' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 bg-slate-900 text-slate-300 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-800">
          <div className="text-lg font-bold text-white">✦ InsightBoard</div>
          <div className="text-[11px] text-slate-500 mt-0.5">AI Analytics Prototype</div>
        </div>
        <nav className="flex-1 py-4">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-brand-600/20 text-white border-r-2 border-brand-500'
                    : 'hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <span className="w-4 text-center opacity-70">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 text-[11px] text-slate-600 border-t border-slate-800">
          Local prototype — no auth
        </div>
      </aside>
      <main className="flex-1 p-8 max-w-[1400px]">
        <Outlet />
      </main>
    </div>
  )
}

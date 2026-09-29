import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

export type SidebarItem = {
  to: string
  label: string
  end?: boolean
  show?: boolean
  icon?: ReactNode
  match?: (pathname: string) => boolean
}

export type SidebarGroup = {
  id: string
  label: string
  items: SidebarItem[]
}

export function SidebarNav({ groups, onNavigate }: { groups: SidebarGroup[]; onNavigate?: () => void }) {
  const { pathname } = useLocation()
  return (
    <nav className="flex flex-col gap-5 px-3 pb-6">
      {groups.map((group) => {
        const items = group.items.filter((item) => item.show !== false)
        if (!items.length) return null
        return (
          <div key={group.id}>
            <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) => {
                    const active = item.match ? item.match(pathname) : isActive
                    return `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                      active
                        ? 'bg-accent text-white shadow-sm'
                        : 'text-slate-300 hover:bg-surface hover:text-white'
                    }`
                  }}
                >
                  <span className="shrink-0 opacity-90">{item.icon}</span>
                  <span className="truncate">{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        )
      })}
    </nav>
  )
}

import { useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { SidebarNav, type SidebarGroup } from '../../components/SidebarNav'
import { IconBuilding, IconCash, IconClose, IconGear, IconGrid, IconMenu } from '../../components/icons'

const groups: SidebarGroup[] = [
  {
    id: 'platform',
    label: 'Platform',
    items: [
      { to: '/platform', label: 'Dashboard', end: true, icon: <IconGrid /> },
      { to: '/platform/companies', label: 'Companies', icon: <IconBuilding /> },
      { to: '/platform/plans', label: 'Plans', icon: <IconCash /> },
      { to: '/platform/settings', label: 'Settings', icon: <IconGear /> },
    ],
  },
]

export function PlatformLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="h-dvh overflow-hidden lg:grid lg:grid-cols-[260px_1fr]">
      {menuOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-dvh w-[260px] flex-col overflow-hidden border-r border-border bg-panel transition-transform duration-200 lg:static lg:h-full lg:translate-x-0 ${
          menuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/20 text-sm font-semibold text-accent">
              SA
            </div>
            <div>
              <h1 className="text-base font-semibold">Super Admin</h1>
              <p className="text-xs text-muted">Platform control</p>
            </div>
          </div>
          <button
            type="button"
            className="rounded-lg p-1.5 text-muted hover:bg-surface hover:text-white lg:hidden"
            onClick={() => setMenuOpen(false)}
            aria-label="Close sidebar"
          >
            <IconClose />
          </button>
        </div>
        <div className="pane-scroll flex-1">
          <SidebarNav groups={groups} onNavigate={() => setMenuOpen(false)} />
        </div>
      </aside>

      <main className="flex h-dvh min-h-0 min-w-0 flex-col overflow-hidden lg:h-full">
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-panel/80 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-border p-2 text-slate-200 hover:bg-surface lg:hidden"
              onClick={() => setMenuOpen(true)}
              aria-label="Open modules"
            >
              <IconMenu />
            </button>
            <p className="truncate text-sm text-muted">Manage companies, plans, and platform settings</p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden truncate text-muted sm:inline">{user?.email}</span>
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/login')
              }}
              className="rounded-lg border border-border px-3 py-1.5 hover:bg-surface"
            >
              Sign out
            </button>
          </div>
        </header>
        <div className="pane-scroll flex-1 p-4 sm:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

import { useMemo, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { canManageOrg, canManagePeople, canOperate, isPortalRole } from '../auth/roles'
import { NotificationBell } from './NotificationBell'
import { SidebarNav, type SidebarGroup } from './SidebarNav'
import {
  IconBuilding,
  IconCalendar,
  IconCamera,
  IconCash,
  IconChart,
  IconCheck,
  IconClock,
  IconClose,
  IconDoc,
  IconExit,
  IconFace,
  IconGear,
  IconGrid,
  IconHome,
  IconMenu,
  IconPeople,
  IconSearch,
  IconShift,
  IconWallet,
  IconAlert,
  IconBadge,
} from './icons'

const SETUP_SHORTCUTS = ['/settings/branches', '/settings/shifts', '/settings/cameras', '/settings/approvals']

function isSettingsHub(pathname: string) {
  if (!pathname.startsWith('/settings')) return false
  return !SETUP_SHORTCUTS.some((path) => pathname === path || pathname.startsWith(`${path}/`))
}

export function Layout() {
  const { organization, role, user, logout, labels } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const portal = isPortalRole(role)
  const trialEnds =
    organization?.trial_active && organization.trial_ends_at
      ? new Date(organization.trial_ends_at).toLocaleDateString()
      : null

  const groups = useMemo<SidebarGroup[]>(() => {
    if (portal) {
      return [
        {
          id: 'today',
          label: 'Overview',
          items: [{ to: '/', label: 'Today', end: true, icon: <IconHome /> }],
        },
        {
          id: 'self-service',
          label: 'Self-service',
          items: [
            { to: '/me/punch', label: 'Camera punch', show: role === 'employee', icon: <IconCamera /> },
            { to: '/me/leave', label: 'Leave', icon: <IconCalendar /> },
            { to: '/me/corrections', label: 'Corrections', icon: <IconClock /> },
            { to: '/me/overtime', label: 'Overtime', icon: <IconClock /> },
            { to: '/me/documents', label: 'Documents', icon: <IconDoc /> },
            { to: '/me/payslips', label: 'Payslips', icon: <IconWallet /> },
            { to: '/me/resign', label: 'Resignation', icon: <IconExit /> },
          ],
        },
      ]
    }

    const peopleLabel = organization?.org_type === 'school' ? 'People' : 'Employees'
    return [
      {
        id: 'overview',
        label: 'Overview',
        items: [{ to: '/', label: 'Dashboard', end: true, icon: <IconGrid /> }],
      },
      {
        id: 'workforce',
        label: 'Workforce',
        items: [
          { to: '/employees', label: peopleLabel, show: canManagePeople(role), icon: <IconPeople /> },
          { to: '/salaries', label: 'Salaries', show: canManageOrg(role), icon: <IconWallet /> },
          { to: '/visitors', label: 'Visitors', icon: <IconBadge /> },
          { to: '/enrollment', label: 'Enrollment', show: canOperate(role), icon: <IconFace /> },
        ],
      },
      {
        id: 'attendance',
        label: 'Attendance',
        items: [
          { to: '/monitor', label: 'Monitor', show: canOperate(role), icon: <IconCamera /> },
          { to: '/attendance', label: 'Attendance', icon: <IconClock /> },
          { to: '/review', label: 'Review', show: canOperate(role), icon: <IconSearch /> },
          { to: '/events', label: 'Events', show: canOperate(role), icon: <IconAlert /> },
        ],
      },
      {
        id: 'hr',
        label: 'HR',
        items: [
          { to: '/leave', label: 'Leave', show: canManageOrg(role), icon: <IconCalendar /> },
          { to: '/payroll', label: 'Payroll', show: canManageOrg(role), icon: <IconCash /> },
          { to: '/exits', label: 'Exits', show: canManageOrg(role), icon: <IconExit /> },
        ],
      },
      {
        id: 'insights',
        label: 'Insights',
        items: [{ to: '/reports', label: 'Reports', icon: <IconChart /> }],
      },
      {
        id: 'setup',
        label: 'Setup',
        items: [
          { to: '/settings/branches', label: labels.branches, show: canManageOrg(role), icon: <IconBuilding /> },
          { to: '/settings/shifts', label: 'Shifts', show: canManageOrg(role), icon: <IconShift /> },
          { to: '/settings/cameras', label: 'Cameras', show: canManageOrg(role), icon: <IconCamera /> },
          { to: '/settings/approvals', label: 'Approvals', show: canManageOrg(role), icon: <IconCheck /> },
          {
            to: '/settings/organization',
            label: 'Settings',
            show: canManageOrg(role),
            icon: <IconGear />,
            match: isSettingsHub,
          },
        ],
      },
    ]
  }, [labels.branches, organization?.org_type, portal, role])

  function closeMenu() {
    setMenuOpen(false)
  }

  return (
    <div className="h-dvh overflow-hidden lg:grid lg:grid-cols-[260px_1fr]">
      {menuOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={closeMenu}
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-dvh w-[260px] flex-col overflow-hidden border-r border-border bg-panel transition-transform duration-200 lg:static lg:h-full lg:translate-x-0 ${
          menuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 px-5 py-5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/20 text-sm font-semibold text-accent">
              AI
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold">{organization?.name || 'AI Attendance'}</h1>
              <p className="truncate text-xs capitalize text-muted">
                {organization?.org_type} · {role} · {organization?.effective_plan}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="rounded-lg p-1.5 text-muted hover:bg-surface hover:text-white lg:hidden"
            onClick={closeMenu}
            aria-label="Close sidebar"
          >
            <IconClose />
          </button>
        </div>
        <div className="pane-scroll flex-1">
          <SidebarNav groups={groups} onNavigate={closeMenu} />
        </div>
      </aside>

      <main className="flex h-dvh min-h-0 min-w-0 flex-col overflow-hidden lg:h-full">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-panel/80 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-border p-2 text-slate-200 hover:bg-surface lg:hidden"
              onClick={() => setMenuOpen(true)}
              aria-label="Open modules"
            >
              <IconMenu />
            </button>
            <p className="truncate text-sm text-muted">
              {trialEnds && !portal
                ? `Starter trial ends ${trialEnds}`
                : portal
                  ? 'Self-service portal'
                  : 'Face recognition attendance'}
            </p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <NotificationBell />
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

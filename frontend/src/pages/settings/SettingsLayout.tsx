import type { ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { canBilling, canManageOrg } from '../../auth/roles'
import { useAuth } from '../../auth/AuthContext'
import {
  IconBuilding,
  IconCalendar,
  IconCamera,
  IconCash,
  IconCheck,
  IconExit,
  IconGear,
  IconGrid,
  IconPeople,
  IconShift,
  IconWallet,
} from '../../components/icons'

type NavItem = { to: string; label: string; show: boolean; end?: boolean }

export default function SettingsLayout() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { role, labels } = useAuth()

  const groups: { id: string; label: string; items: NavItem[] }[] = [
    {
      id: 'company',
      label: 'Company',
      items: [
        { to: '/settings', label: 'Overview', show: canManageOrg(role), end: true },
        { to: '/settings/organization', label: 'Organization', show: canManageOrg(role) },
        { to: '/settings/branches', label: labels.branches, show: canManageOrg(role) },
        { to: '/settings/team', label: 'Team', show: canManageOrg(role) },
        { to: '/settings/billing', label: 'Billing', show: canBilling(role) },
      ],
    },
    {
      id: 'attendance',
      label: 'Attendance rules',
      items: [
        { to: '/settings/shifts', label: 'Shifts & grace', show: canManageOrg(role) },
        { to: '/settings/calendar', label: 'Work calendar', show: canManageOrg(role) },
        { to: '/settings/approvals', label: 'Approvals', show: canManageOrg(role) },
        { to: '/settings/cameras', label: 'Cameras', show: canManageOrg(role) },
      ],
    },
    {
      id: 'pay',
      label: 'Pay & HR',
      items: [
        { to: '/settings/payroll', label: 'Payroll & deductions', show: canManageOrg(role) },
        { to: '/settings/departments', label: labels.department, show: canManageOrg(role) },
        { to: '/settings/exit', label: 'Exit policy', show: canManageOrg(role) },
      ],
    },
    {
      id: 'connect',
      label: 'Connect',
      items: [{ to: '/settings/integrations', label: 'Integrations', show: canManageOrg(role) }],
    },
  ]

  const visible = groups
    .map((group) => ({ ...group, items: group.items.filter((item) => item.show) }))
    .filter((group) => group.items.length)

  const flat = visible.flatMap((group) => group.items)
  const current = flat.find((item) =>
    item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`),
  )

  const icons: Record<string, ReactNode> = {
    '/settings': <IconGrid />,
    '/settings/organization': <IconGear />,
    '/settings/branches': <IconBuilding />,
    '/settings/team': <IconPeople />,
    '/settings/billing': <IconWallet />,
    '/settings/shifts': <IconShift />,
    '/settings/calendar': <IconCalendar />,
    '/settings/approvals': <IconCheck />,
    '/settings/cameras': <IconCamera />,
    '/settings/payroll': <IconCash />,
    '/settings/departments': <IconPeople />,
    '/settings/exit': <IconExit />,
    '/settings/integrations': <IconGear />,
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Company setup</h2>
        <p className="mt-1 text-sm text-muted">
          Organization profile, attendance grace, salary deductions, leave, and billing — in one place.
        </p>
      </div>

      <label className="block lg:hidden">
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-muted">Section</span>
        <select
          className="field"
          value={current?.to || '/settings'}
          onChange={(e) => navigate(e.target.value)}
        >
          {visible.map((group) => (
            <optgroup key={group.id} label={group.label}>
              {group.items.map((item) => (
                <option key={item.to} value={item.to}>
                  {item.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>

      <div className="lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:items-start lg:gap-8">
        <nav className="sticky top-0 hidden space-y-5 lg:block">
          {visible.map((group) => (
            <div key={group.id}>
              <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                        isActive
                          ? 'bg-accent text-white shadow-sm'
                          : 'text-slate-300 hover:bg-panel hover:text-white'
                      }`
                    }
                  >
                    <span className="shrink-0 opacity-90">{icons[item.to]}</span>
                    <span className="truncate">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  )
}

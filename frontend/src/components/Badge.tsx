import type { ReactNode } from 'react'

const styles = {
  present: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  late: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  absent: 'bg-red-500/15 text-red-300 border-red-500/30',
  half_day: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  on_leave: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  active: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  inactive: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  enrolled: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  trained: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
}

interface BadgeProps {
  label: string
  tone?: keyof typeof styles
}

export function Badge({ label, tone = 'pending' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles[tone]}`}>
      {label}
    </span>
  )
}

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: ReactNode
  accent?: string
}

export function StatCard({ title, value, subtitle, icon, accent = 'text-blue-400' }: StatCardProps) {
  return (
    <div className="rounded-xl border border-border bg-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-muted">{title}</p>
          <p className={`mt-2 text-3xl font-semibold ${accent}`}>{value}</p>
          {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
        </div>
        {icon && <div className={`rounded-lg bg-surface p-2 ${accent}`}>{icon}</div>}
      </div>
    </div>
  )
}

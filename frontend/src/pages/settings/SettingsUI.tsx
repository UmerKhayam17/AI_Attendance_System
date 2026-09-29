import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function SettingsPageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h3 className="text-xl font-semibold tracking-tight">{title}</h3>
        {description ? <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

export function SettingsSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-panel shadow-sm">
      <div className="border-b border-border/80 px-5 py-4 sm:px-6">
        <h4 className="font-semibold">{title}</h4>
        {description ? <p className="mt-1 text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      <div className="p-5 sm:p-6">{children}</div>
    </section>
  )
}

export function Field({
  label,
  hint,
  children,
  className = '',
}: {
  label: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={`block space-y-1.5 text-sm ${className}`}>
      <span className="font-medium text-slate-300">{label}</span>
      {children}
      {hint ? <span className="block text-xs leading-5 text-muted">{hint}</span> : null}
    </label>
  )
}

export function Toggle({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: string
  hint?: string
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`flex w-full items-start justify-between gap-4 rounded-xl border p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? 'border-accent/40 bg-accent/10' : 'border-border bg-surface/50 hover:border-slate-500'
      }`}
    >
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        {hint ? <span className="mt-1 block text-xs leading-5 text-muted">{hint}</span> : null}
      </span>
      <span
        className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition ${checked ? 'bg-accent' : 'bg-slate-600'}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
            checked ? 'left-[22px]' : 'left-0.5'
          }`}
        />
      </span>
    </button>
  )
}

export function StickySave({ saving, label }: { saving: boolean; label: string }) {
  return (
    <div className="sticky bottom-0 z-10 mt-6 flex justify-end border-t border-border bg-surface/90 py-3 backdrop-blur">
      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-sm disabled:opacity-60"
      >
        {saving ? 'Saving...' : label}
      </button>
    </div>
  )
}

export function SetupCard({
  to,
  title,
  value,
  hint,
  icon,
}: {
  to: string
  title: string
  value: string
  hint?: string
  icon?: ReactNode
}) {
  return (
    <Link
      to={to}
      className="group flex flex-col rounded-2xl border border-border bg-panel p-5 transition hover:border-accent/50 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">{title}</p>
        {icon ? <div className="rounded-lg bg-surface p-2 text-accent">{icon}</div> : null}
      </div>
      <p className="mt-3 text-base font-semibold leading-6 text-white">{value}</p>
      {hint ? <p className="mt-1 text-xs leading-5 text-muted">{hint}</p> : null}
      <p className="mt-4 text-xs font-medium text-accent">Configure →</p>
    </Link>
  )
}

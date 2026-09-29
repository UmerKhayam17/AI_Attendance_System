export type DatePeriod = 'day' | 'week' | 'month' | 'year' | 'custom'

const PERIODS: Array<{ id: DatePeriod; label: string }> = [
  { id: 'day', label: 'Day' },
  { id: 'week', label: 'Week' },
  { id: 'month', label: 'Month' },
  { id: 'year', label: 'Year' },
  { id: 'custom', label: 'Custom' },
]

export function isoDate(d = new Date()) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function rangeForPeriod(
  period: DatePeriod,
  customFrom: string,
  customTo: string,
  day: string,
) {
  const now = new Date()
  const to = isoDate(now)
  if (period === 'day') {
    const value = day || to
    return { from: value, to: value }
  }
  if (period === 'week') {
    const start = new Date(now)
    const dow = start.getDay()
    start.setDate(start.getDate() - (dow === 0 ? 6 : dow - 1))
    return { from: isoDate(start), to }
  }
  if (period === 'month') {
    return { from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`, to }
  }
  if (period === 'year') {
    return { from: `${now.getFullYear()}-01-01`, to }
  }
  return { from: customFrom || to, to: customTo || to }
}

export function PeriodFilter({
  period,
  onPeriod,
  day,
  onDay,
  customFrom,
  customTo,
  onCustomFrom,
  onCustomTo,
}: {
  period: DatePeriod
  onPeriod: (period: DatePeriod) => void
  day: string
  onDay: (value: string) => void
  customFrom: string
  customTo: string
  onCustomFrom: (value: string) => void
  onCustomTo: (value: string) => void
}) {
  const max = isoDate()
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1 rounded-lg border border-border p-1">
        {PERIODS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`rounded-md px-3 py-1.5 text-sm ${
              period === item.id ? 'bg-accent text-white' : 'text-muted hover:bg-surface hover:text-slate-100'
            }`}
            onClick={() => onPeriod(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {period === 'day' ? (
        <input
          type="date"
          value={day}
          max={max}
          onChange={(e) => onDay(e.target.value)}
          className="field !w-auto"
        />
      ) : null}
      {period === 'custom' ? (
        <>
          <input
            type="date"
            value={customFrom}
            max={customTo || max}
            onChange={(e) => onCustomFrom(e.target.value)}
            className="field !w-auto"
          />
          <span className="text-xs text-muted">to</span>
          <input
            type="date"
            value={customTo}
            min={customFrom}
            max={max}
            onChange={(e) => onCustomTo(e.target.value)}
            className="field !w-auto"
          />
        </>
      ) : null}
    </div>
  )
}

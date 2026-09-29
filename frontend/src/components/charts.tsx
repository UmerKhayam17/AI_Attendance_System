import { useState, type MouseEvent, type ReactNode } from 'react'

export type ChartSlice = { label: string; value: number; color: string }

const R = 42
const C = 2 * Math.PI * R

export function formatNumber(value: number, digits = 0) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

export function pct(part: number, whole: number) {
  if (!whole) return 0
  return Math.round((part / whole) * 1000) / 10
}

export function deltaPct(current: number, previous: number) {
  if (!previous) return current ? 100 : 0
  return Math.round(((current - previous) / Math.abs(previous)) * 1000) / 10
}

export type TrendDay = {
  date: string
  is_workday?: boolean
  present: number
  late: number
  half_day?: number
  on_leave?: number
  absent: number
}

export function dayRate(day: TrendDay) {
  const half = day.half_day ?? 0
  const den = day.present + day.late + half + day.absent
  return den ? ((day.present + day.late + half) / den) * 100 : 0
}

export function sumTrend(days: TrendDay[]) {
  return days.reduce(
    (acc, day) => ({
      present: acc.present + day.present,
      late: acc.late + day.late,
      half_day: acc.half_day + (day.half_day ?? 0),
      on_leave: acc.on_leave + (day.on_leave ?? 0),
      absent: acc.absent + day.absent,
    }),
    { present: 0, late: 0, half_day: 0, on_leave: 0, absent: 0 },
  )
}

export function weeklyBuckets(days: TrendDay[]) {
  const weeks = Math.floor(days.length / 7)
  if (weeks < 2) return []
  const out: Array<ReturnType<typeof sumTrend> & { label: string; rate: number }> = []
  for (let i = weeks; i >= 1; i -= 1) {
    const slice = days.slice(days.length - 7 * i, days.length - 7 * (i - 1))
    const sum = sumTrend(slice)
    const label = i === 1 ? 'This week' : i === 2 ? 'Last week' : `${i - 1}w ago`
    out.push({ label, ...sum, rate: dayRate({ date: '', ...sum }) })
  }
  return out
}

export function weekdayCompare(days: TrendDay[]) {
  if (days.length < 14) return []
  const names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const last = days.slice(-14, -7)
  const cur = days.slice(-7)
  const mapDays = (list: TrendDay[]) => {
    const mapped = new Map<number, TrendDay>()
    for (const day of list) {
      mapped.set(new Date(`${day.date}T12:00:00`).getDay(), day)
    }
    return mapped
  }
  const previous = mapDays(last)
  const current = mapDays(cur)
  return [1, 2, 3, 4, 5, 6, 0].map((dow) => ({
    label: names[dow],
    last: previous.get(dow),
    current: current.get(dow),
  }))
}

export function attendanceRateBins(days: TrendDay[]) {
  const work = days.filter((d) => d.is_workday !== false)
  const edges = [
    { label: '<60%', lo: 0, hi: 60, color: '#ef4444' },
    { label: '60–70', lo: 60, hi: 70, color: '#f97316' },
    { label: '70–80', lo: 70, hi: 80, color: '#f59e0b' },
    { label: '80–90', lo: 80, hi: 90, color: '#3b82f6' },
    { label: '90–100', lo: 90, hi: 101, color: '#22c55e' },
  ]
  return edges.map((bin) => ({
    label: bin.label,
    color: bin.color,
    value: work.filter((d) => {
      const rate = dayRate(d)
      return rate >= bin.lo && rate < bin.hi
    }).length,
  }))
}

function niceMax(value: number) {
  if (value <= 0) return 1
  const pow = 10 ** Math.floor(Math.log10(value))
  return Math.ceil(value / pow) * pow
}

type ChartTipState = { x: number; y: number; title: string; lines: string[] } | null

function useChartTip() {
  const [tip, setTip] = useState<ChartTipState>(null)
  function move(e: MouseEvent, title: string, lines: string[]) {
    const root = (e.currentTarget as Element).closest('[data-chart]') as HTMLElement | null
    const box = root?.getBoundingClientRect()
    if (!box) return
    const x = e.clientX - box.left + 16
    const y = e.clientY - box.top - 12
    setTip({
      x: Math.min(Math.max(8, x), Math.max(8, box.width - 170)),
      y: Math.min(Math.max(8, y), Math.max(8, box.height - 72)),
      title,
      lines,
    })
  }
  return { tip, move, hide: () => setTip(null) }
}

function ChartTip({ tip }: { tip: ChartTipState }) {
  if (!tip) return null
  return (
    <div
      className="pointer-events-none absolute z-20 min-w-40 rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-xs shadow-xl"
      style={{ left: tip.x, top: tip.y }}
    >
      <p className="font-medium text-white">{tip.title}</p>
      {tip.lines.map((line, i) => (
        <p key={`${i}-${line}`} className="mt-0.5 text-slate-300">
          {line}
        </p>
      ))}
    </div>
  )
}

export function KpiCard({
  label,
  value,
  hint,
  tone = 'text-slate-100',
  percent,
  spark,
}: {
  label: string
  value: ReactNode
  hint?: string
  tone?: string
  percent?: number
  spark?: number[]
}) {
  return (
    <article className="rounded-xl border border-border bg-panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
          <p className={`mt-2 truncate text-2xl font-semibold ${tone}`}>{value}</p>
          {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
        </div>
        {typeof percent === 'number' ? <Ring percent={percent} /> : null}
      </div>
      {spark && spark.length > 1 ? (
        <div className="mt-3">
          <Sparkline values={spark} />
        </div>
      ) : null}
    </article>
  )
}

function Ring({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent))
  const dash = (clamped / 100) * C
  const tone = clamped >= 90 ? '#22c55e' : clamped >= 75 ? '#3b82f6' : clamped >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <svg width="56" height="56" viewBox="0 0 100 100" className="shrink-0" aria-hidden>
      <circle cx="50" cy="50" r={R} fill="none" stroke="#334155" strokeWidth="10" />
      <circle
        cx="50"
        cy="50"
        r={R}
        fill="none"
        stroke={tone}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${C}`}
        transform="rotate(-90 50 50)"
      />
      <text x="50" y="54" textAnchor="middle" className="fill-slate-200" fontSize="18" fontWeight="600">
        {Math.round(clamped)}
      </text>
    </svg>
  )
}

export function Sparkline({ values, color = '#3b82f6' }: { values: number[]; color?: string }) {
  const w = 160
  const h = 28
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const span = Math.max(max - min, 1)
  const step = values.length > 1 ? w / (values.length - 1) : w
  const points = values
    .map((v, i) => {
      const x = i * step
      const y = h - ((v - min) / span) * (h - 4) - 2
      return `${x},${y}`
    })
    .join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-7 w-full" preserveAspectRatio="none" aria-hidden>
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
    </svg>
  )
}

export function DonutChart({
  title,
  slices,
  center,
}: {
  title: string
  slices: ChartSlice[]
  center?: string
}) {
  const { tip, move, hide } = useChartTip()
  const [active, setActive] = useState<string | null>(null)
  const total = slices.reduce((sum, s) => sum + Math.max(0, s.value), 0)
  const arcs: Array<ChartSlice & { length: number; offset: number }> = []
  let offset = 0
  for (const slice of slices) {
    if (slice.value <= 0) continue
    const length = (slice.value / Math.max(total, 1)) * C
    arcs.push({ ...slice, length, offset })
    offset += length
  }
  function onSlice(e: MouseEvent, slice: ChartSlice) {
    setActive(slice.label)
    move(e, slice.label, [`${formatNumber(slice.value)}`, `${pct(slice.value, total)}% of total`])
  }
  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <h3 className="mb-4 font-medium">{title}</h3>
      {total === 0 ? (
        <p className="text-sm text-muted">No data in this range.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-6">
          <svg width="160" height="160" viewBox="0 0 100 100" className="shrink-0 overflow-visible">
            {arcs.map((slice) => (
              <circle
                key={slice.label}
                cx="50"
                cy="50"
                r={R}
                fill="none"
                stroke={slice.color}
                strokeWidth={active === slice.label ? 16 : 14}
                strokeDasharray={`${slice.length} ${C}`}
                strokeDashoffset={-slice.offset}
                transform="rotate(-90 50 50)"
                className="cursor-pointer"
                opacity={active && active !== slice.label ? 0.35 : 1}
                onMouseMove={(e) => onSlice(e, slice)}
                onMouseLeave={() => {
                  setActive(null)
                  hide()
                }}
              />
            ))}
            <circle cx="50" cy="50" r="28" fill="#1e293b" />
            <text x="50" y="48" textAnchor="middle" className="fill-slate-100" fontSize="11" fontWeight="600">
              {center ?? formatNumber(total)}
            </text>
            <text x="50" y="60" textAnchor="middle" className="fill-slate-400" fontSize="6">
              total
            </text>
          </svg>
          <ul className="min-w-40 flex-1 space-y-2 text-sm">
            {slices.map((slice) => (
              <li
                key={slice.label}
                className={`flex cursor-pointer items-center justify-between gap-3 rounded-md px-1 py-0.5 ${active === slice.label ? 'bg-surface' : ''}`}
                onMouseEnter={(e) => onSlice(e, slice)}
                onMouseMove={(e) => onSlice(e, slice)}
                onMouseLeave={() => {
                  setActive(null)
                  hide()
                }}
              >
                <span className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: slice.color }} />
                  {slice.label}
                </span>
                <span className="text-muted">
                  {formatNumber(slice.value)} · {pct(slice.value, total)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 90) * Math.PI) / 180
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)] as const
}

export function PieChart({
  title,
  caption = 'Pie chart',
  slices,
}: {
  title: string
  caption?: string
  slices: ChartSlice[]
}) {
  const { tip, move, hide } = useChartTip()
  const [active, setActive] = useState<string | null>(null)
  const total = slices.reduce((sum, s) => sum + Math.max(0, s.value), 0)
  const cx = 50
  const cy = 50
  const r = 42
  let angle = 0
  const paths = slices
    .filter((s) => s.value > 0)
    .map((slice) => {
      const sweep = (slice.value / total) * 360
      const start = angle
      const end = angle + sweep
      angle = end
      if (sweep >= 359.99) {
        return { ...slice, d: `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx} ${cy + r} A ${r} ${r} 0 1 1 ${cx} ${cy - r}` }
      }
      const [sx, sy] = polar(cx, cy, r, start)
      const [ex, ey] = polar(cx, cy, r, end)
      const large = sweep > 180 ? 1 : 0
      return {
        ...slice,
        d: `M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey} Z`,
      }
    })

  function onSlice(e: MouseEvent, slice: ChartSlice) {
    setActive(slice.label)
    move(e, slice.label, [`${formatNumber(slice.value)}`, `${pct(slice.value, total)}% of total`])
  }

  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">{caption}</p>
      <h3 className="mt-1 font-medium">{title}</h3>
      {total === 0 ? (
        <p className="mt-4 text-sm text-muted">No data in this range.</p>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-6">
          <svg width="176" height="176" viewBox="0 0 100 100" className="shrink-0 overflow-visible">
            {paths.map((slice) => (
              <path
                key={slice.label}
                d={slice.d}
                fill={slice.color}
                stroke="#0f172a"
                strokeWidth="0.6"
                className="cursor-pointer"
                opacity={active && active !== slice.label ? 0.4 : 1}
                onMouseMove={(e) => onSlice(e, slice)}
                onMouseLeave={() => {
                  setActive(null)
                  hide()
                }}
              />
            ))}
          </svg>
          <ul className="min-w-40 flex-1 space-y-2 text-sm">
            {slices.map((slice) => (
              <li
                key={slice.label}
                className={`flex cursor-pointer items-center justify-between gap-3 rounded-md px-1 py-0.5 ${active === slice.label ? 'bg-surface' : ''}`}
                onMouseMove={(e) => onSlice(e, slice)}
                onMouseLeave={() => {
                  setActive(null)
                  hide()
                }}
              >
                <span className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: slice.color }} />
                  {slice.label}
                </span>
                <span className="text-muted">
                  {formatNumber(slice.value)} · {pct(slice.value, total)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

export function HorizontalBars({
  title,
  rows,
  empty = 'No data in this range.',
}: {
  title: string
  rows: Array<{ label: string; value: number; color?: string }>
  empty?: string
}) {
  const { tip, move, hide } = useChartTip()
  const max = Math.max(1, ...rows.map((r) => r.value))
  const total = rows.reduce((sum, r) => sum + r.value, 0)
  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <h3 className="mb-4 font-medium">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li
              key={row.label}
              className="cursor-pointer"
              onMouseMove={(e) =>
                move(e, row.label, [`${formatNumber(row.value)}`, `${pct(row.value, total)}% of total`])
              }
              onMouseLeave={hide}
            >
              <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                <span className="truncate">{row.label}</span>
                <span className="shrink-0 text-muted">{formatNumber(row.value)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${(row.value / max) * 100}%`,
                    background: row.color || '#3b82f6',
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

export function ColumnChart({
  title,
  caption,
  bars,
  color = '#3b82f6',
  empty = 'No data yet.',
}: {
  title: string
  caption?: string
  bars: Array<{ label: string; value: number }>
  color?: string
  empty?: string
}) {
  const { tip, move, hide } = useChartTip()
  const max = Math.max(1, ...bars.map((b) => b.value))
  const hasValue = bars.some((b) => b.value > 0)
  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <h3 className="font-medium">{title}</h3>
      {caption ? <p className="mt-1 text-xs text-muted">{caption}</p> : null}
      {!hasValue ? (
        <p className="mt-4 text-sm text-muted">{empty}</p>
      ) : (
        <div className="mt-4 flex h-40 items-end gap-1">
          {bars.map((bar) => (
            <div
              key={bar.label}
              className="flex h-full min-w-0 flex-1 cursor-pointer flex-col justify-end"
              onMouseMove={(e) => move(e, bar.label, [`${formatNumber(bar.value)}`])}
              onMouseLeave={hide}
            >
              <div
                className="w-full rounded-t-sm"
                style={{ height: `${(bar.value / max) * 100}%`, background: color, minHeight: bar.value ? 4 : 0 }}
              />
              <span className="mt-1 truncate text-center text-[9px] text-muted">{bar.label}</span>
            </div>
          ))}
        </div>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

export function HistogramChart({
  title,
  caption = 'Histogram',
  bins,
  unit = 'count',
  empty = 'No distribution yet.',
}: {
  title: string
  caption?: string
  bins: Array<{ label: string; value: number; color?: string }>
  unit?: string
  empty?: string
}) {
  const W = 640
  const H = 240
  const pad = { l: 40, r: 12, t: 16, b: 36 }
  const innerW = W - pad.l - pad.r
  const innerH = H - pad.t - pad.b
  const max = Math.max(1, ...bins.map((b) => b.value))
  const barW = bins.length ? innerW / bins.length : innerW
  const hasValue = bins.some((b) => b.value > 0)
  const { tip, move, hide } = useChartTip()

  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">{caption}</p>
      <h3 className="mt-1 font-medium">{title}</h3>
      {!hasValue ? (
        <p className="mt-4 text-sm text-muted">{empty}</p>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 h-56 w-full" role="img" onMouseLeave={hide}>
          {[0, 0.5, 1].map((p) => {
            const y = pad.t + innerH - p * innerH
            return (
              <g key={p}>
                <line x1={pad.l} x2={W - pad.r} y1={y} y2={y} stroke="#334155" />
                <text x={pad.l - 6} y={y + 3} textAnchor="end" className="fill-slate-400" fontSize="10">
                  {Math.round(max * p)}
                </text>
              </g>
            )
          })}
          {bins.map((bin, i) => {
            const h = (bin.value / max) * innerH
            const x = pad.l + i * barW
            return (
              <g key={bin.label}>
                <rect
                  x={x}
                  y={pad.t + innerH - h}
                  width={Math.max(barW - 1, 2)}
                  height={Math.max(h, bin.value ? 2 : 0)}
                  fill={bin.color || '#3b82f6'}
                />
                <rect
                  x={x}
                  y={pad.t}
                  width={Math.max(barW, 2)}
                  height={innerH}
                  fill="#000"
                  fillOpacity={0}
                  className="cursor-pointer"
                  onMouseMove={(e) => move(e, bin.label, [`${formatNumber(bin.value)} ${unit}`])}
                />
                <text
                  x={x + barW / 2}
                  y={H - 12}
                  textAnchor="middle"
                  className="fill-slate-400"
                  fontSize="10"
                >
                  {bin.label}
                </text>
              </g>
            )
          })}
        </svg>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

export function GrowthKpi({
  label,
  value,
  delta,
  hint,
  invert = false,
}: {
  label: string
  value: ReactNode
  delta: number
  hint?: string
  invert?: boolean
}) {
  const good = invert ? delta < 0 : delta > 0
  const tone = delta === 0 ? 'text-muted' : good ? 'text-emerald-400' : 'text-red-400'
  const arrow = delta > 0 ? '▲' : delta < 0 ? '▼' : '•'
  return (
    <article className="rounded-xl border border-border bg-panel p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-100">{value}</p>
      <p className={`mt-1 text-sm font-medium ${tone}`}>
        {arrow} {delta > 0 ? '+' : ''}
        {formatNumber(delta, 1)}% vs last week
      </p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </article>
  )
}

export function LineChart({
  title,
  caption,
  labels,
  series,
  unit = '',
}: {
  title: string
  caption?: string
  labels: string[]
  series: Array<{ label: string; color: string; values: number[] }>
  unit?: string
}) {
  const { tip, move, hide } = useChartTip()
  const [hoverI, setHoverI] = useState<number | null>(null)
  const W = 640
  const H = 240
  const pad = { l: 40, r: 16, t: 16, b: 32 }
  const innerW = W - pad.l - pad.r
  const innerH = H - pad.t - pad.b
  const all = series.flatMap((s) => s.values)
  const max = niceMax(Math.max(0, ...all, unit === '%' ? 100 : 0))
  const min = 0
  const span = Math.max(max - min, 1)
  const n = Math.max(labels.length, 1)
  const xAt = (i: number) => pad.l + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW)
  const yAt = (v: number) => pad.t + innerH - ((v - min) / span) * innerH
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => min + span * p)
  const labelStep = n > 14 ? Math.ceil(n / 7) : 1
  const colW = n <= 1 ? innerW : innerW / n
  const digits = unit === '%' ? 1 : 0

  function onCol(e: MouseEvent, i: number) {
    setHoverI(i)
    move(
      e,
      labels[i],
      series.map((s) => `${s.label}: ${formatNumber(s.values[i] ?? 0, digits)}${unit}`),
    )
  }

  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <h3 className="font-medium">{title}</h3>
      {caption ? <p className="mt-1 text-xs text-muted">{caption}</p> : null}
      {n === 0 || all.every((v) => !v) ? (
        <p className="mt-4 text-sm text-muted">No trend yet.</p>
      ) : (
        <>
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="mt-3 h-56 w-full"
            role="img"
            onMouseLeave={() => {
              setHoverI(null)
              hide()
            }}
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line x1={pad.l} x2={W - pad.r} y1={yAt(tick)} y2={yAt(tick)} stroke="#334155" strokeWidth="1" />
                <text x={pad.l - 6} y={yAt(tick) + 3} textAnchor="end" className="fill-slate-400" fontSize="10">
                  {Math.round(tick)}
                  {unit}
                </text>
              </g>
            ))}
            {series.map((s, si) => {
              const pts = s.values.map((v, i) => `${xAt(i)},${yAt(v)}`).join(' ')
              const area = `M ${xAt(0)} ${yAt(s.values[0] || 0)} L ${s.values
                .map((v, i) => `${xAt(i)} ${yAt(v)}`)
                .join(' ')} L ${xAt(s.values.length - 1)} ${pad.t + innerH} L ${xAt(0)} ${pad.t + innerH} Z`
              return (
                <g key={s.label}>
                  {si === 0 ? <path d={area} fill={s.color} fillOpacity="0.12" /> : null}
                  <polyline fill="none" stroke={s.color} strokeWidth="2.4" points={pts} />
                  {s.values.map((v, i) =>
                    i % labelStep === 0 || i === s.values.length - 1 || hoverI === i ? (
                      <circle
                        key={`${s.label}-${i}`}
                        cx={xAt(i)}
                        cy={yAt(v)}
                        r={hoverI === i ? 4 : 2.6}
                        fill={s.color}
                      />
                    ) : null,
                  )}
                </g>
              )
            })}
            {hoverI !== null ? (
              <line
                x1={xAt(hoverI)}
                x2={xAt(hoverI)}
                y1={pad.t}
                y2={pad.t + innerH}
                stroke="#94a3b8"
                strokeDasharray="3 3"
                strokeWidth="1"
              />
            ) : null}
            {labels.map((label, i) =>
              i % labelStep === 0 || i === labels.length - 1 ? (
                <text key={label + i} x={xAt(i)} y={H - 10} textAnchor="middle" className="fill-slate-400" fontSize="10">
                  {label}
                </text>
              ) : null,
            )}
            {labels.map((label, i) => (
              <rect
                key={`hit-${label}-${i}`}
                x={pad.l + i * colW}
                y={pad.t}
                width={colW}
                height={innerH}
                fill="#000"
                fillOpacity={0}
                className="cursor-pointer"
                onMouseMove={(e) => onCol(e, i)}
              />
            ))}
          </svg>
          <ul className="mt-1 flex flex-wrap gap-3 text-xs text-muted">
            {series.map((s) => (
              <li key={s.label} className="flex items-center gap-1.5">
                <span className="h-2 w-4 rounded-sm" style={{ background: s.color }} />
                {s.label}
              </li>
            ))}
          </ul>
        </>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

export function GroupedBarChart({
  title,
  caption,
  groups,
  series,
}: {
  title: string
  caption?: string
  groups: Array<{ label: string; values: number[] }>
  series: Array<{ label: string; color: string }>
}) {
  const { tip, move, hide } = useChartTip()
  const W = 640
  const H = 240
  const pad = { l: 40, r: 12, t: 16, b: 36 }
  const innerW = W - pad.l - pad.r
  const innerH = H - pad.t - pad.b
  const max = niceMax(Math.max(0, ...groups.flatMap((g) => g.values)))
  const groupW = groups.length ? innerW / groups.length : innerW
  const gap = 8
  const barW = Math.max(4, (groupW - gap) / Math.max(series.length, 1))

  function onGroup(e: MouseEvent, group: { label: string; values: number[] }) {
    move(
      e,
      group.label,
      series.map((s, si) => `${s.label}: ${formatNumber(group.values[si] || 0)}`),
    )
  }

  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <h3 className="font-medium">{title}</h3>
      {caption ? <p className="mt-1 text-xs text-muted">{caption}</p> : null}
      {groups.length === 0 || max === 0 ? (
        <p className="mt-4 text-sm text-muted">No comparison data yet.</p>
      ) : (
        <>
          <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 h-56 w-full" role="img" onMouseLeave={hide}>
            {[0, 0.5, 1].map((p) => {
              const y = pad.t + innerH - p * innerH
              return (
                <g key={p}>
                  <line x1={pad.l} x2={W - pad.r} y1={y} y2={y} stroke="#334155" />
                  <text x={pad.l - 6} y={y + 3} textAnchor="end" className="fill-slate-400" fontSize="10">
                    {Math.round(max * p)}
                  </text>
                </g>
              )
            })}
            {groups.map((group, gi) =>
              series.map((s, si) => {
                const value = group.values[si] || 0
                const x = pad.l + gi * groupW + si * barW + gap / 2
                const h = (value / max) * innerH
                const y = pad.t + innerH - h
                return (
                  <rect
                    key={`${group.label}-${s.label}`}
                    x={x}
                    y={y}
                    width={Math.max(barW - 2, 3)}
                    height={Math.max(h, value ? 2 : 0)}
                    rx="2"
                    fill={s.color}
                  />
                )
              }),
            )}
            {groups.map((group, gi) => (
              <g key={group.label}>
                <text
                  x={pad.l + gi * groupW + groupW / 2}
                  y={H - 12}
                  textAnchor="middle"
                  className="fill-slate-400"
                  fontSize="10"
                >
                  {group.label}
                </text>
                <rect
                  x={pad.l + gi * groupW}
                  y={pad.t}
                  width={groupW}
                  height={innerH}
                  fill="#000"
                  fillOpacity={0}
                  className="cursor-pointer"
                  onMouseMove={(e) => onGroup(e, group)}
                />
              </g>
            ))}
          </svg>
          <ul className="mt-1 flex flex-wrap gap-3 text-xs text-muted">
            {series.map((s) => (
              <li key={s.label} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />
                {s.label}
              </li>
            ))}
          </ul>
        </>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

export function ComboChart({
  title,
  caption,
  labels,
  bars,
  line,
}: {
  title: string
  caption?: string
  labels: string[]
  bars: { label: string; color: string; values: number[] }
  line: { label: string; color: string; values: number[] }
}) {
  const { tip, move, hide } = useChartTip()
  const [hoverI, setHoverI] = useState<number | null>(null)
  const W = 640
  const H = 240
  const pad = { l: 40, r: 40, t: 16, b: 32 }
  const innerW = W - pad.l - pad.r
  const innerH = H - pad.t - pad.b
  const barMax = niceMax(Math.max(0, ...bars.values))
  const n = Math.max(labels.length, 1)
  const groupW = innerW / n
  const xAt = (i: number) => pad.l + i * groupW + groupW / 2
  const yBar = (v: number) => pad.t + innerH - (v / Math.max(barMax, 1)) * innerH
  const yLine = (v: number) => pad.t + innerH - (Math.max(0, Math.min(100, v)) / 100) * innerH
  const pts = line.values.map((v, i) => `${xAt(i)},${yLine(v)}`).join(' ')

  function onCol(e: MouseEvent, i: number) {
    setHoverI(i)
    move(e, labels[i], [
      `${bars.label}: ${formatNumber(bars.values[i] ?? 0)}`,
      `${line.label}: ${formatNumber(line.values[i] ?? 0, 1)}%`,
    ])
  }

  return (
    <section className="relative rounded-xl border border-border bg-panel p-5" data-chart>
      <h3 className="font-medium">{title}</h3>
      {caption ? <p className="mt-1 text-xs text-muted">{caption}</p> : null}
      {n === 0 ? (
        <p className="mt-4 text-sm text-muted">No data yet.</p>
      ) : (
        <>
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="mt-3 h-56 w-full"
            role="img"
            onMouseLeave={() => {
              setHoverI(null)
              hide()
            }}
          >
            {[0, 50, 100].map((tick) => (
              <g key={tick}>
                <line x1={pad.l} x2={W - pad.r} y1={yLine(tick)} y2={yLine(tick)} stroke="#334155" />
                <text x={W - pad.r + 6} y={yLine(tick) + 3} className="fill-slate-400" fontSize="10">
                  {tick}%
                </text>
              </g>
            ))}
            <text x={8} y={pad.t + 4} className="fill-slate-400" fontSize="10">
              {barMax}
            </text>
            {bars.values.map((v, i) => {
              const h = (v / Math.max(barMax, 1)) * innerH
              return (
                <rect
                  key={labels[i] || i}
                  x={xAt(i) - groupW * 0.28}
                  y={yBar(v)}
                  width={groupW * 0.56}
                  height={Math.max(h, v ? 2 : 0)}
                  rx="2"
                  fill={bars.color}
                  fillOpacity={hoverI === null || hoverI === i ? 0.85 : 0.35}
                />
              )
            })}
            <polyline fill="none" stroke={line.color} strokeWidth="2.4" points={pts} />
            {line.values.map((v, i) => (
              <circle
                key={`l-${i}`}
                cx={xAt(i)}
                cy={yLine(v)}
                r={hoverI === i ? 4 : 2.4}
                fill={line.color}
              />
            ))}
            {hoverI !== null ? (
              <line
                x1={xAt(hoverI)}
                x2={xAt(hoverI)}
                y1={pad.t}
                y2={pad.t + innerH}
                stroke="#94a3b8"
                strokeDasharray="3 3"
                strokeWidth="1"
              />
            ) : null}
            {labels.map((label, i) =>
              i % Math.ceil(n / 8) === 0 || i === n - 1 ? (
                <text key={label + i} x={xAt(i)} y={H - 10} textAnchor="middle" className="fill-slate-400" fontSize="10">
                  {label}
                </text>
              ) : null,
            )}
            {labels.map((label, i) => (
              <rect
                key={`hit-${label}-${i}`}
                x={pad.l + i * groupW}
                y={pad.t}
                width={groupW}
                height={innerH}
                fill="#000"
                fillOpacity={0}
                className="cursor-pointer"
                onMouseMove={(e) => onCol(e, i)}
              />
            ))}
          </svg>
          <ul className="mt-1 flex flex-wrap gap-3 text-xs text-muted">
            <li className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm" style={{ background: bars.color }} />
              {bars.label}
            </li>
            <li className="flex items-center gap-1.5">
              <span className="h-0.5 w-4" style={{ background: line.color }} />
              {line.label}
            </li>
          </ul>
        </>
      )}
      <ChartTip tip={tip} />
    </section>
  )
}

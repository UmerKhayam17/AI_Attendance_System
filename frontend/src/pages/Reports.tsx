import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiDownload } from '../api/client'
import { dashboardApi } from '../api/services'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { BranchFilter } from '../components/BranchFilter'
import { DonutChart, GroupedBarChart, GrowthKpi, HistogramChart, HorizontalBars, KpiCard, LineChart, ComboChart, PieChart, attendanceRateBins, dayRate, deltaPct, formatNumber, pct, weekdayCompare, weeklyBuckets } from '../components/charts'
import { Loading } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { DailyReport, HrReport, RangeReport, RecognitionReport } from '../types'

const COLORS = {
  present: '#22c55e',
  late: '#f59e0b',
  absent: '#ef4444',
  leave: '#8b5cf6',
  half: '#38bdf8',
  ot: '#f97316',
  recognized: '#22c55e',
  unknown: '#ef4444',
  spoof: '#f59e0b',
  anomaly: '#a78bfa',
  review: '#64748b',
}

type Tab = 'overview' | 'attendance' | 'hr' | 'ai'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function monthStartIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
}

function hoursFromMinutes(minutes: number) {
  return Math.round((minutes / 60) * 10) / 10
}

type Metrics = {
  attendanceRate: number
  lateRate: number
  absenceRate: number
  expected: number
  attended: number
  missing: number
  late: number
  dailyRate: number[]
  otHours: number
  matchRate: number
  aiTotal: number
  netPeople: number
  exceptions: Record<string, number>
}

function pretty(value: string) {
  return value.replace(/_/g, ' ')
}

function toRows(record: Record<string, number> | undefined, color: string) {
  return Object.entries(record || {})
    .map(([label, value]) => ({ label: pretty(label), value, color }))
    .sort((a, b) => b.value - a.value)
}

export default function ReportsPage() {
  const { labels, organization } = useAuth()
  const { toast } = useToast()
  const [date, setDate] = useState(todayIso())
  const [from, setFrom] = useState(monthStartIso())
  const [to, setTo] = useState(todayIso())
  const [branch, setBranch] = useState<number | 'all'>('all')
  const [tab, setTab] = useState<Tab>('overview')
  const [report, setReport] = useState<DailyReport | null>(null)
  const [hr, setHr] = useState<HrReport | null>(null)
  const [ai, setAi] = useState<RecognitionReport | null>(null)
  const [range, setRange] = useState<RangeReport | null>(null)
  const [loading, setLoading] = useState(true)
  const canExport = Boolean(organization?.features?.exports ?? organization?.effective_plan !== 'free')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [daily, month, workforce, recognition] = await Promise.all([
        dashboardApi.dailyReport(date, branch === 'all' ? undefined : branch),
        dashboardApi.rangeReport(from, to, branch === 'all' ? undefined : branch),
        dashboardApi.hrReport(from, to, branch === 'all' ? undefined : branch),
        dashboardApi.recognitionReport(from, to, branch === 'all' ? undefined : branch),
      ])
      setReport(daily)
      setRange(month)
      setHr(workforce)
      setAi(recognition)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load report', 'error')
    } finally {
      setLoading(false)
    }
  }, [date, from, to, branch, toast])

  useEffect(() => {
    load()
  }, [load])

  const metrics = useMemo(() => {
    const workdays = range?.days.filter((d) => d.is_workday) ?? []
    const attended = workdays.reduce((s, d) => s + d.present + d.late + d.half_day, 0)
    const missing = workdays.reduce((s, d) => s + d.absent, 0)
    const late = workdays.reduce((s, d) => s + d.late, 0)
    const expected = attended + missing
    const dailyRate = workdays.map((d) => {
      const den = d.present + d.late + d.half_day + d.absent
      return den ? ((d.present + d.late + d.half_day) / den) * 100 : 0
    })
    const aiTotal = ai ? ai.totals.recognized + ai.totals.unknown + ai.totals.spoof : 0
    const exceptions = (range?.exceptions || []).reduce<Record<string, number>>((acc, row) => {
      acc[row.kind] = (acc[row.kind] || 0) + 1
      return acc
    }, {})
    return {
      attendanceRate: pct(attended, expected),
      lateRate: pct(late, attended),
      absenceRate: pct(missing, expected),
      expected,
      attended,
      missing,
      late,
      dailyRate,
      otHours: hoursFromMinutes(range?.totals.overtime_minutes || 0),
      matchRate: pct(ai?.totals.recognized || 0, aiTotal),
      aiTotal,
      netPeople: (hr?.joiners.length || 0) - (hr?.exits.length || 0),
      exceptions,
    }
  }, [range, ai, hr])

  const download = async (format: 'xlsx' | 'csv' | 'pdf') => {
    try {
      await apiDownload(
        dashboardApi.exportUrl(from, to, format, branch === 'all' ? undefined : branch),
        `attendance_${from}_${to}.${format}`,
      )
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Export failed', 'error')
    }
  }

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: 'overview', label: 'Overview' },
    { id: 'attendance', label: 'Attendance' },
    { id: 'hr', label: 'Workforce' },
    { id: 'ai', label: 'AI' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Reports</h2>
          <p className="text-sm text-muted">
            KPIs, trends, and breakdowns from {from} to {to}.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="field" />
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="field" />
          <BranchFilter value={branch} onChange={setBranch} />
          <button type="button" onClick={() => download('csv')} className="rounded-lg border border-border px-3 py-2 text-sm">
            CSV
          </button>
          <button
            type="button"
            disabled={!canExport}
            onClick={() => download('xlsx')}
            className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40"
          >
            Excel
          </button>
          <button
            type="button"
            disabled={!canExport}
            onClick={() => download('pdf')}
            className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40"
          >
            PDF
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`rounded-lg px-3 py-1.5 text-sm ${tab === item.id ? 'bg-accent text-white' : 'border border-border text-muted'}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Loading label="Generating report..." />
      ) : tab === 'overview' ? (
        <OverviewPanel range={range} hr={hr} ai={ai} metrics={metrics} labels={labels} />
      ) : tab === 'ai' && ai ? (
        <AiPanel ai={ai} metrics={metrics} />
      ) : tab === 'hr' && hr ? (
        <HrPanel hr={hr} labels={labels} />
      ) : (
        <AttendancePanel
          range={range}
          report={report}
          date={date}
          onDate={setDate}
          metrics={metrics}
          labels={labels}
        />
      )}
    </div>
  )
}

function OverviewPanel({
  range,
  hr,
  ai,
  metrics,
  labels,
}: {
  range: RangeReport | null
  hr: HrReport | null
  ai: RecognitionReport | null
  metrics: Metrics
  labels: { branch: string; department: string }
}) {
  const m = metrics
  const days = range?.days ?? []
  const weeks = weeklyBuckets(days)
  const weekdays = weekdayCompare(days)
  const thisWeek = weeks[weeks.length - 1]
  const lastWeek = weeks[weeks.length - 2]
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <KpiCard
          label="Attendance rate"
          value={`${m.attendanceRate}%`}
          hint={`${formatNumber(m.attended)} of ${formatNumber(m.expected)} expected punches`}
          tone="text-emerald-400"
          percent={m.attendanceRate}
          spark={m.dailyRate}
        />
        <KpiCard
          label="Late rate"
          value={`${m.lateRate}%`}
          hint={`${formatNumber(range?.totals.late || 0)} late arrivals`}
          tone="text-amber-400"
          percent={100 - m.lateRate}
        />
        <KpiCard
          label="Absence rate"
          value={`${m.absenceRate}%`}
          hint={`${formatNumber(range?.totals.absent || 0)} missed workdays`}
          tone="text-red-400"
          percent={100 - m.absenceRate}
        />
        <KpiCard
          label="Headcount"
          value={formatNumber(hr?.headcount.active || range?.people_count || 0)}
          hint={`${m.netPeople >= 0 ? '+' : ''}${m.netPeople} net this period`}
          tone="text-sky-400"
        />
        <KpiCard
          label="Overtime"
          value={`${formatNumber(m.otHours, 1)}h`}
          hint={`${formatNumber(range?.totals.overtime_minutes || 0)} minutes`}
          tone="text-orange-400"
        />
        <KpiCard
          label="Face match rate"
          value={`${m.matchRate}%`}
          hint={`${formatNumber(ai?.totals.recognized || 0)} recognized events`}
          tone="text-violet-400"
          percent={m.matchRate}
        />
      </div>

      {thisWeek && lastWeek ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <GrowthKpi
            label="Attendance vs last week"
            value={`${pct(thisWeek.present + thisWeek.late + thisWeek.half_day, thisWeek.present + thisWeek.late + thisWeek.half_day + thisWeek.absent)}%`}
            delta={deltaPct(dayRate({ date: '', ...thisWeek }), dayRate({ date: '', ...lastWeek }))}
          />
          <GrowthKpi
            label="Present growth"
            value={formatNumber(thisWeek.present + thisWeek.late)}
            delta={deltaPct(thisWeek.present + thisWeek.late, lastWeek.present + lastWeek.late)}
          />
          <GrowthKpi
            label="Late growth"
            value={formatNumber(thisWeek.late)}
            delta={deltaPct(thisWeek.late, lastWeek.late)}
            invert
          />
          <GrowthKpi
            label="Absence growth"
            value={formatNumber(thisWeek.absent)}
            delta={deltaPct(thisWeek.absent, lastWeek.absent)}
            invert
          />
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <PieChart
          title="Attendance mix"
          caption="Pie chart"
          slices={[
            { label: 'Present', value: range?.totals.present || 0, color: COLORS.present },
            { label: 'Late', value: range?.totals.late || 0, color: COLORS.late },
            { label: 'Half day', value: range?.totals.half_day || 0, color: COLORS.half },
            { label: 'Leave', value: range?.totals.on_leave || 0, color: COLORS.leave },
            { label: 'Absent', value: range?.totals.absent || 0, color: COLORS.absent },
          ]}
        />
        <HistogramChart
          title="Daily attendance rate"
          caption="Histogram"
          unit="days"
          bins={attendanceRateBins(days)}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <LineChart
          title="Attendance & late rate"
          caption="Line graph"
          unit="%"
          labels={days.map((d) => d.date.slice(5))}
          series={[
            { label: 'Attendance rate', color: '#22c55e', values: days.map((d) => dayRate(d)) },
            { label: 'Late rate', color: '#f59e0b', values: days.map((d) => pct(d.late, d.present + d.late + d.half_day)) },
          ]}
        />
        <ComboChart
          title="Headcount vs attendance rate"
          caption="Bars are people present; the line is attendance %"
          labels={days.map((d) => d.date.slice(8))}
          bars={{
            label: 'Present + late',
            color: '#3b82f6',
            values: days.map((d) => d.present + d.late),
          }}
          line={{
            label: 'Attendance rate',
            color: '#22c55e',
            values: days.map((d) => dayRate(d)),
          }}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <GroupedBarChart
          title="This week vs last week"
          caption="Bar chart · present punches by weekday"
          series={[
            { label: 'Last week', color: '#64748b' },
            { label: 'This week', color: '#22c55e' },
          ]}
          groups={weekdays.map((row) => ({
            label: row.label,
            values: [
              (row.last?.present || 0) + (row.last?.late || 0),
              (row.current?.present || 0) + (row.current?.late || 0),
            ],
          }))}
        />
        <GroupedBarChart
          title="Weekly growth"
          caption="Bar chart · present, late, absent"
          series={[
            { label: 'Present', color: '#22c55e' },
            { label: 'Late', color: '#f59e0b' },
            { label: 'Absent', color: '#ef4444' },
          ]}
          groups={weeks.map((week) => ({
            label: week.label,
            values: [week.present, week.late, week.absent],
          }))}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <DonutChart
          title="Attendance mix"
          slices={[
            { label: 'Present', value: range?.totals.present || 0, color: COLORS.present },
            { label: 'Late', value: range?.totals.late || 0, color: COLORS.late },
            { label: 'Half day', value: range?.totals.half_day || 0, color: COLORS.half },
            { label: 'Leave', value: range?.totals.on_leave || 0, color: COLORS.leave },
            { label: 'Absent', value: range?.totals.absent || 0, color: COLORS.absent },
          ]}
        />
        <DonutChart
          title="AI events"
          slices={[
            { label: 'Recognized', value: ai?.totals.recognized || 0, color: COLORS.recognized },
            { label: 'Unknown', value: ai?.totals.unknown || 0, color: COLORS.unknown },
            { label: 'Spoof', value: ai?.totals.spoof || 0, color: COLORS.spoof },
            { label: 'Anomaly', value: ai?.totals.anomaly || 0, color: COLORS.anomaly },
            { label: 'Review', value: ai?.totals.review || 0, color: COLORS.review },
          ]}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <HorizontalBars
          title={`Headcount by ${labels.department.toLowerCase()}`}
          rows={toRows(hr?.headcount.by_department, '#3b82f6')}
        />
        <HorizontalBars
          title="Exceptions this period"
          rows={toRows(m.exceptions, '#f59e0b')}
          empty="No late, absence, or overtime exceptions."
        />
      </div>
    </div>
  )
}

function AttendancePanel({
  range,
  report,
  date,
  onDate,
  metrics,
  labels,
}: {
  range: RangeReport | null
  report: DailyReport | null
  date: string
  onDate: (value: string) => void
  metrics: Metrics
  labels: { person: string; people: string }
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Present" value={formatNumber(range?.totals.present || 0)} tone="text-emerald-400" hint="Range total" />
        <KpiCard
          label="Attendance rate"
          value={`${metrics.attendanceRate}%`}
          tone="text-sky-400"
          percent={metrics.attendanceRate}
          spark={metrics.dailyRate}
        />
        <KpiCard label="Late" value={formatNumber(range?.totals.late || 0)} tone="text-amber-400" hint={`${metrics.lateRate}% of attended`} />
        <KpiCard label="Overtime" value={`${formatNumber(metrics.otHours, 1)}h`} tone="text-orange-400" hint="Recorded in range" />
      </div>

      {range ? (
        <LineChart
          title="Attendance & late rate"
          caption="Line graph"
          unit="%"
          labels={range.days.filter((d) => d.is_workday).map((d) => d.date.slice(5))}
          series={[
            {
              label: 'Attendance rate',
              color: COLORS.present,
              values: range.days.filter((d) => d.is_workday).map((d) => dayRate(d)),
            },
            {
              label: 'Late rate',
              color: COLORS.late,
              values: range.days
                .filter((d) => d.is_workday)
                .map((d) => pct(d.late, d.present + d.late + d.half_day)),
            },
          ]}
        />
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <DonutChart
          title="Range mix"
          slices={[
            { label: 'Present', value: range?.totals.present || 0, color: COLORS.present },
            { label: 'Late', value: range?.totals.late || 0, color: COLORS.late },
            { label: 'Half day', value: range?.totals.half_day || 0, color: COLORS.half },
            { label: 'Leave', value: range?.totals.on_leave || 0, color: COLORS.leave },
            { label: 'Absent', value: range?.totals.absent || 0, color: COLORS.absent },
          ]}
        />
        <DonutChart
          title={`Selected day · ${date}`}
          slices={[
            { label: 'Present', value: report?.totals.present || 0, color: COLORS.present },
            { label: 'Late', value: report?.totals.late || 0, color: COLORS.late },
            { label: 'Half day', value: report?.totals.half_day || 0, color: COLORS.half },
            { label: 'Leave', value: report?.totals.on_leave || 0, color: COLORS.leave },
            { label: 'Absent', value: report?.totals.absent || 0, color: COLORS.absent },
          ]}
        />
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <h3 className="font-medium">Daily detail</h3>
        <input type="date" value={date} onChange={(e) => onDate(e.target.value)} className="field max-w-48" />
      </div>

      {report ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <section className="rounded-xl border border-border bg-panel">
            <div className="border-b border-border px-5 py-4">
              <h3 className="font-medium">Present / Late — {report.date}</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-muted">
                  <tr>
                    <th className="px-5 py-3">{labels.person}</th>
                    <th className="px-5 py-3">Check In</th>
                    <th className="px-5 py-3">Check Out</th>
                    <th className="px-5 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {report.attendance.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-5 py-8 text-center text-muted">
                        No attendance for this date
                      </td>
                    </tr>
                  ) : (
                    report.attendance.map((record) => (
                      <tr key={record.id} className="border-t border-border/70">
                        <td className="px-5 py-3">
                          <p>{record.employee_name}</p>
                          <p className="text-xs text-muted">{record.employee_id}</p>
                        </td>
                        <td className="px-5 py-3">
                          {record.check_in
                            ? new Date(record.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                            : '—'}
                        </td>
                        <td className="px-5 py-3">
                          {record.check_out
                            ? new Date(record.check_out).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                            : '—'}
                        </td>
                        <td className="px-5 py-3">
                          <Badge label={record.status} tone={record.status} />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-xl border border-border bg-panel">
            <div className="border-b border-border px-5 py-4">
              <h3 className="font-medium">Absent {labels.people}</h3>
            </div>
            <div className="divide-y divide-border/70">
              {report.absent.length === 0 ? (
                <p className="px-5 py-8 text-center text-sm text-muted">No absences</p>
              ) : (
                report.absent.map((emp) => (
                  <div key={emp.employee_id} className="flex items-center justify-between px-5 py-4">
                    <div>
                      <p className="font-medium">{emp.name}</p>
                      <p className="text-xs text-muted">
                        {emp.employee_id} · {emp.department}
                      </p>
                    </div>
                    <Badge label="Absent" tone="absent" />
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}

function HrPanel({ hr, labels }: { hr: HrReport; labels: { branch: string; department: string } }) {
  const otHours = hoursFromMinutes(hr.overtime_minutes)
  const approvedHours = hoursFromMinutes(hr.approved_overtime_minutes)
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Active headcount" value={formatNumber(hr.headcount.active)} hint={`${hr.headcount.total} including inactive`} tone="text-emerald-400" />
        <KpiCard label="Joiners" value={formatNumber(hr.joiners.length)} tone="text-sky-400" hint="Joined in this range" />
        <KpiCard label="Exits" value={formatNumber(hr.exits.length)} tone="text-red-400" hint="Completed exits" />
        <KpiCard
          label="Overtime"
          value={`${formatNumber(otHours, 1)}h`}
          hint={`${formatNumber(approvedHours, 1)}h approved`}
          tone="text-amber-400"
        />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <DonutChart title="Employment type" slices={toRows(hr.headcount.by_employment_type, '#3b82f6').map((row, i) => ({
          ...row,
          color: ['#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6', '#38bdf8'][i % 5],
        }))} />
        <DonutChart
          title="Leave utilization"
          slices={toRows(hr.leave_utilization, '#8b5cf6').map((row, i) => ({
            ...row,
            color: ['#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#38bdf8'][i % 5],
          }))}
        />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <HorizontalBars title={`By ${labels.branch.toLowerCase()}`} rows={toRows(hr.headcount.by_branch, '#22c55e')} />
        <HorizontalBars title={`By ${labels.department.toLowerCase()}`} rows={toRows(hr.headcount.by_department, '#3b82f6')} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-border bg-panel p-5">
          <h3 className="mb-3 font-medium">Joiners</h3>
          {hr.joiners.length === 0 ? (
            <p className="text-sm text-muted">No joiners in this range.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {hr.joiners.map((row) => (
                <li key={row.employee_id} className="flex justify-between gap-3">
                  <span>
                    {row.name} <span className="text-muted">· {row.employee_id}</span>
                  </span>
                  <span className="text-muted">{row.joining_date}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="rounded-xl border border-border bg-panel p-5">
          <h3 className="mb-3 font-medium">Exits</h3>
          {hr.exits.length === 0 ? (
            <p className="text-sm text-muted">No completed exits in this range.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {hr.exits.map((row) => (
                <li key={`${row.employee_id}-${row.last_working_day}`} className="flex justify-between gap-3">
                  <span>
                    {row.name} <span className="text-muted">· {pretty(row.exit_type)}</span>
                  </span>
                  <span className="text-muted">{row.last_working_day}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

function AiPanel({
  ai,
  metrics,
}: {
  ai: RecognitionReport
  metrics: Metrics
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Match rate"
          value={`${metrics.matchRate}%`}
          hint={`${formatNumber(metrics.aiTotal)} face events`}
          tone="text-emerald-400"
          percent={metrics.matchRate}
        />
        <KpiCard label="Recognized" value={formatNumber(ai.totals.recognized)} tone="text-emerald-400" />
        <KpiCard label="Unknown" value={formatNumber(ai.totals.unknown)} tone="text-red-400" />
        <KpiCard label="Spoof / anomaly" value={formatNumber(ai.totals.spoof + ai.totals.anomaly)} tone="text-amber-400" />
      </div>
      <LineChart
        title="Recognition trend"
        caption="Line graph"
        labels={ai.days.map((d) => d.date.slice(5))}
        series={[
          { label: 'Recognized', color: COLORS.recognized, values: ai.days.map((d) => d.recognized) },
          { label: 'Unknown', color: COLORS.unknown, values: ai.days.map((d) => d.unknown) },
          { label: 'Spoof', color: COLORS.spoof, values: ai.days.map((d) => d.spoof) },
        ]}
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <DonutChart
          title="Event mix"
          slices={[
            { label: 'Recognized', value: ai.totals.recognized, color: COLORS.recognized },
            { label: 'Unknown', value: ai.totals.unknown, color: COLORS.unknown },
            { label: 'Spoof', value: ai.totals.spoof, color: COLORS.spoof },
            { label: 'Anomaly', value: ai.totals.anomaly, color: COLORS.anomaly },
            { label: 'Review', value: ai.totals.review, color: COLORS.review },
          ]}
        />
        <HorizontalBars
          title="By camera"
          rows={ai.cameras.map((row) => ({
            label: row.camera_name,
            value: row.recognized + row.unknown + row.spoof,
            color: '#22c55e',
          }))}
          empty="No recognition events in this range."
        />
      </div>
    </div>
  )
}

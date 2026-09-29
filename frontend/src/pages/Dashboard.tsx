import { useCallback, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { dashboardApi } from '../api/services'
import { Badge, StatCard } from '../components/Badge'
import { BranchFilter } from '../components/BranchFilter'
import { ComboChart, DonutChart, GroupedBarChart, GrowthKpi, HistogramChart, HorizontalBars, KpiCard, LineChart, PieChart, attendanceRateBins, dayRate, deltaPct, pct, weekdayCompare, weeklyBuckets } from '../components/charts'
import { PeriodFilter, isoDate, rangeForPeriod, type DatePeriod } from '../components/PeriodFilter'
import { Loading } from '../components/Modal'
import { useAuth } from '../auth/AuthContext'
import { usePolling } from '../hooks/usePolling'
import type { DashboardSummary } from '../types'

const SOURCE_META: Record<string, { label: string; color: string }> = {
  cctv: { label: 'CCTV', color: '#22c55e' },
  mobile: { label: 'Mobile', color: '#3b82f6' },
  webcam: { label: 'Webcam', color: '#38bdf8' },
  manual: { label: 'Manual', color: '#f59e0b' },
}

function formatTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function hourLabel(hour: number) {
  const suffix = hour < 12 ? 'a' : 'p'
  const n = hour % 12 || 12
  return `${n}${suffix}`
}

export default function DashboardPage() {
  const { labels } = useAuth()
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [branch, setBranch] = useState<number | 'all'>('all')
  const [period, setPeriod] = useState<DatePeriod>('day')
  const [dayDate, setDayDate] = useState(isoDate)
  const [customFrom, setCustomFrom] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  })
  const [customTo, setCustomTo] = useState(isoDate)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { from, to } = rangeForPeriod(period, customFrom, customTo, dayDate)
  const singleDay = from === to

  const load = useCallback(async () => {
    try {
      const summary = await dashboardApi.summary(branch === 'all' ? undefined : branch, from, to)
      setData(summary)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [branch, from, to])

  usePolling(load, period === 'year' ? 120000 : period === 'month' || period === 'custom' ? 60000 : 15000, true)

  const charts = data?.charts
  const trend = charts?.trend ?? []
  const dailyRate = useMemo(
    () =>
      trend
        .filter((d) => d.is_workday)
        .map((d) => {
          const den = d.present + d.late + d.half_day + d.absent
          return den ? ((d.present + d.late + d.half_day) / den) * 100 : 0
        }),
    [trend],
  )
  const weeks = useMemo(() => weeklyBuckets(trend), [trend])
  const weekdays = useMemo(() => weekdayCompare(trend), [trend])
  const thisWeek = weeks[weeks.length - 1]
  const lastWeek = weeks[weeks.length - 2]

  if (loading && !data) return <Loading label="Loading dashboard..." />
  if (error && !data) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-6 text-red-200">
        {error}
      </div>
    )
  }
  if (!data) return null

  const { summary } = data
  const onTime = Math.max((summary.present_today || 0) - (summary.late_today || 0), 0)
  const clocked = onTime + summary.late_today + (summary.half_day_today ?? 0)
  const expectedToday = clocked + summary.absent_today
  const attendanceRate = pct(clocked, expectedToday)
  const checkoutRate = pct(summary.checked_out_today, summary.present_today)
  const trained = summary.trained_faces
  const untrained = Math.max(summary.total_employees - trained, 0)
  const cameras = summary.cameras
  const hourly = (charts?.hourly ?? []).filter((row) => row.hour >= 6 && row.hour <= 21)
  const workTrend = trend.filter((d) => d.is_workday)
  const rangeFrom = data.from || from
  const rangeTo = data.to || to
  const isToday = singleDay && rangeFrom === data.date
  const when = isToday ? 'today' : singleDay ? rangeFrom : `${rangeFrom} to ${rangeTo}`
  const comboWeeks = workTrend.length > 31 ? weeklyBuckets(trend) : null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Dashboard</h2>
          <p className="text-sm text-muted">
            {data.workday && !data.workday.is_workday
              ? `${data.workday.reason || 'Non-working day'} · ${rangeFrom}`
              : isToday
                ? `Live overview for ${data.date}`
                : `Overview for ${when}`}
            {' · '}
            <Link to="/reports" className="text-accent hover:underline">
              Full reports
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <PeriodFilter
            period={period}
            onPeriod={setPeriod}
            day={dayDate}
            onDay={setDayDate}
            customFrom={customFrom}
            customTo={customTo}
            onCustomFrom={setCustomFrom}
            onCustomTo={setCustomTo}
          />
          <BranchFilter value={branch} onChange={setBranch} />
          <button
            type="button"
            onClick={load}
            className="rounded-lg border border-border bg-panel px-4 py-2 text-sm hover:bg-surface"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <KpiCard
          label={isToday ? 'Attendance today' : 'Attendance'}
          value={`${attendanceRate}%`}
          hint={`${summary.present_today} in · ${summary.absent_today} absent`}
          tone="text-emerald-400"
          percent={attendanceRate}
          spark={dailyRate}
        />
        <KpiCard
          label={`Total ${labels.people}`}
          value={summary.total_employees}
          hint={`${trained} faces enrolled`}
          tone="text-blue-400"
          percent={pct(trained, summary.total_employees)}
        />
        <StatCard title={isToday ? 'Present Today' : 'Present'} value={summary.present_today} accent="text-emerald-400" />
        <StatCard title={isToday ? 'Late Today' : 'Late'} value={summary.late_today} accent="text-amber-400" />
        <StatCard title={isToday ? 'Absent Today' : 'Absent'} value={summary.absent_today} accent="text-red-400" />
        <KpiCard
          label="Checked out"
          value={`${checkoutRate}%`}
          hint={`${summary.checked_out_today} of ${summary.present_today} present`}
          tone="text-cyan-400"
          percent={checkoutRate}
        />
      </div>
      {thisWeek && lastWeek ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <GrowthKpi
            label="Attendance vs last week"
            value={`${pct(thisWeek.present + thisWeek.late + thisWeek.half_day, thisWeek.present + thisWeek.late + thisWeek.half_day + thisWeek.absent)}%`}
            delta={deltaPct(
              dayRate({ date: '', ...thisWeek }),
              dayRate({ date: '', ...lastWeek }),
            )}
            hint={`${thisWeek.present + thisWeek.late} punches this week`}
          />
          <GrowthKpi
            label="Present growth"
            value={thisWeek.present + thisWeek.late}
            delta={deltaPct(thisWeek.present + thisWeek.late, lastWeek.present + lastWeek.late)}
            hint="On-site punches, week to week"
          />
          <GrowthKpi
            label="Late growth"
            value={thisWeek.late}
            delta={deltaPct(thisWeek.late, lastWeek.late)}
            invert
            hint="Lower is better"
          />
          <GrowthKpi
            label="Absence growth"
            value={thisWeek.absent}
            delta={deltaPct(thisWeek.absent, lastWeek.absent)}
            invert
            hint="Missed workdays vs last week"
          />
        </div>
      ) : null}
      {typeof summary.review_pending === 'number' && summary.review_pending > 0 ? (
        <Link
          to="/review"
          className="block rounded-xl border border-amber-500/30 bg-amber-950/20 px-5 py-3 text-sm text-amber-200"
        >
          {summary.review_pending} low-confidence match{summary.review_pending === 1 ? '' : 'es'} waiting for review
        </Link>
      ) : null}
      {typeof summary.unknown_today === 'number' && summary.unknown_today > 0 ? (
        <Link
          to="/events"
          className="block rounded-xl border border-red-500/30 bg-red-950/20 px-5 py-3 text-sm text-red-200"
        >
          {summary.unknown_today} unknown person event{summary.unknown_today === 1 ? '' : 's'} {when}
        </Link>
      ) : null}
      {(summary.visitors_on_site ?? 0) > 0 || (summary.visitors_expected ?? 0) > 0 ? (
        <Link
          to="/visitors"
          className="block rounded-xl border border-cyan-500/30 bg-cyan-950/20 px-5 py-3 text-sm text-cyan-200"
        >
          {summary.visitors_on_site ?? 0} visitor{(summary.visitors_on_site ?? 0) === 1 ? '' : 's'} on site
          {(summary.visitors_expected ?? 0) > 0 ? ` · ${summary.visitors_expected} expected ${isToday ? 'today' : 'in range'}` : ''}
        </Link>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <LineChart
          title="Attendance & late rate"
          caption={singleDay ? 'Line graph · last 4 weeks' : `Line graph · ${when}`}
          unit="%"
          labels={workTrend.map((d) => d.date.slice(5))}
          series={[
            { label: 'Attendance rate', color: '#22c55e', values: workTrend.map((d) => dayRate(d)) },
            {
              label: 'Late rate',
              color: '#f59e0b',
              values: workTrend.map((d) => pct(d.late, d.present + d.late + (d.half_day || 0))),
            },
          ]}
        />
        <ComboChart
          title="Headcount vs attendance rate"
          caption={comboWeeks ? 'Bar + line · weekly' : 'Bar + line · workdays'}
          labels={comboWeeks ? comboWeeks.map((w) => w.label) : workTrend.map((d) => d.date.slice(workTrend.length > 14 ? 5 : 8))}
          bars={{
            label: 'Present + late',
            color: '#3b82f6',
            values: comboWeeks ? comboWeeks.map((w) => w.present + w.late) : workTrend.map((d) => d.present + d.late),
          }}
          line={{
            label: 'Attendance rate',
            color: '#22c55e',
            values: comboWeeks ? comboWeeks.map((w) => w.rate) : workTrend.map((d) => dayRate(d)),
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
        <PieChart
          title={isToday ? "Today's status" : 'Status mix'}
          caption="Pie chart"
          slices={[
            { label: 'On time', value: onTime, color: '#22c55e' },
            { label: 'Late', value: summary.late_today, color: '#f59e0b' },
            { label: 'Half day', value: summary.half_day_today ?? 0, color: '#38bdf8' },
            { label: 'Leave', value: summary.on_leave_today ?? 0, color: '#8b5cf6' },
            { label: 'Absent', value: summary.absent_today, color: '#ef4444' },
          ]}
        />
        <DonutChart
          title="Donut · punch source"
          slices={(charts?.sources ?? []).map((row) => ({
            label: SOURCE_META[row.source]?.label || row.source,
            value: row.count,
            color: SOURCE_META[row.source]?.color || '#64748b',
          }))}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <HistogramChart
          title={isToday ? 'Arrival times today' : 'Arrival times'}
          caption="Histogram"
          unit="check-ins"
          bins={hourly.map((row) => ({
            label: hourLabel(row.hour),
            value: row.count,
            color: '#3b82f6',
          }))}
          empty={isToday ? 'No check-ins recorded yet today.' : 'No check-ins in this range.'}
        />
        <HistogramChart
          title="Daily attendance rate"
          caption={singleDay ? 'Histogram · last 28 workdays' : 'Histogram · workdays in range'}
          unit="days"
          bins={attendanceRateBins(trend)}
          empty="Not enough daily rates to plot yet."
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <DonutChart
          title="Donut · face enrollment"
          slices={[
            { label: 'Enrolled', value: trained, color: '#8b5cf6' },
            { label: 'Not enrolled', value: untrained, color: '#334155' },
          ]}
        />
        <DonutChart
          title="Donut · cameras"
          slices={[
            { label: 'Online', value: cameras?.online ?? 0, color: '#22c55e' },
            { label: 'Degraded', value: cameras?.degraded ?? 0, color: '#f59e0b' },
            { label: 'Offline', value: cameras?.offline ?? 0, color: '#ef4444' },
            { label: 'Stopped', value: cameras?.stopped ?? 0, color: '#64748b' },
          ]}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <LineChart
          title="AI events"
          caption={singleDay ? 'Line graph · 7 days' : `Line graph · ${when}`}
          labels={(charts?.ai_trend ?? []).map((d) => d.date.slice(5))}
          series={[
            { label: 'Recognized', color: '#22c55e', values: (charts?.ai_trend ?? []).map((d) => d.recognized) },
            { label: 'Unknown', color: '#ef4444', values: (charts?.ai_trend ?? []).map((d) => d.unknown) },
            { label: 'Spoof', color: '#f59e0b', values: (charts?.ai_trend ?? []).map((d) => d.spoof) },
          ]}
        />
        <DonutChart
          title={isToday ? 'Donut · AI today' : 'Donut · AI'}
          slices={[
            { label: 'Recognized', value: summary.recognized_today ?? 0, color: '#22c55e' },
            { label: 'Unknown', value: summary.unknown_today ?? 0, color: '#ef4444' },
            { label: 'Spoof', value: summary.spoof_today ?? 0, color: '#f59e0b' },
            { label: 'Open anomalies', value: summary.anomaly_open ?? 0, color: '#a78bfa' },
          ]}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <GroupedBarChart
          title={`${labels.department} · present vs late`}
          caption={isToday ? 'Today' : when}
          series={[
            { label: 'Present', color: '#22c55e' },
            { label: 'Late', color: '#f59e0b' },
          ]}
          groups={data.department_stats.map((dept) => ({
            label: dept.department,
            values: [dept.present_count, dept.late_count],
          }))}
        />
        <HorizontalBars
          title={`${labels.branch} present`}
          rows={(charts?.branches ?? []).map((row) => ({
            label: row.branch,
            value: row.present_count + row.late_count,
            color: '#3b82f6',
          }))}
          empty={isToday ? 'No branch attendance yet today' : 'No branch attendance in this range'}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <DonutChart
          title="Visitors"
          slices={[
            { label: 'On site', value: summary.visitors_on_site ?? 0, color: '#22c55e' },
            { label: 'Expected', value: summary.visitors_expected ?? 0, color: '#f59e0b' },
          ]}
        />
        <DonutChart
          title="Still on site vs checked out"
          slices={[
            { label: 'Still in', value: Math.max(summary.present_today - summary.checked_out_today, 0), color: '#38bdf8' },
            { label: 'Checked out', value: summary.checked_out_today, color: '#22c55e' },
          ]}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-border bg-panel">
          <div className="border-b border-border px-5 py-4">
            <h3 className="font-medium">{labels.department} breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-muted">
                <tr>
                  <th className="px-5 py-3">{labels.department}</th>
                  <th className="px-5 py-3">Present</th>
                  <th className="px-5 py-3">Late</th>
                  <th className="px-5 py-3">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.department_stats.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-8 text-center text-muted">
                      No attendance recorded {when}
                    </td>
                  </tr>
                ) : (
                  data.department_stats.map((dept) => (
                    <tr key={dept.department} className="border-t border-border/70">
                      <td className="px-5 py-3">{dept.department}</td>
                      <td className="px-5 py-3">{dept.present_count}</td>
                      <td className="px-5 py-3">{dept.late_count}</td>
                      <td className="px-5 py-3">{dept.total}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-panel">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h3 className="font-medium">Recent Activity</h3>
            <Link to="/attendance" className="text-sm text-accent hover:underline">
              View all
            </Link>
          </div>
          <div className="divide-y divide-border/70">
            {data.recent_activity.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-muted">No recent activity</p>
            ) : (
              data.recent_activity.map((record) => (
                <div key={record.id} className="flex items-center justify-between gap-4 px-5 py-4">
                  <div>
                    <p className="font-medium">{record.employee_name}</p>
                    <p className="text-xs text-muted">
                      {record.employee_id} · In {formatTime(record.check_in)} · Out{' '}
                      {formatTime(record.check_out)}
                    </p>
                  </div>
                  <Badge label={record.status} tone={record.status} />
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

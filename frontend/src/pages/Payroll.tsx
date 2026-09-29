import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { payrollApi } from '../api/services'
import { Badge } from '../components/Badge'
import { EmptyState, Loading, Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { PayrollRun, Payslip } from '../types'

function money(currency: string, value: string | number) {
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return `${currency} ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export default function PayrollPage() {
  const { toast } = useToast()
  const [runs, setRuns] = useState<PayrollRun[]>([])
  const [currency, setCurrency] = useState('PKR')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState<PayrollRun | null>(null)
  const [slip, setSlip] = useState<Payslip | null>(null)

  const load = useCallback(async () => {
    try {
      const [list, policy, period] = await Promise.all([
        payrollApi.runs(),
        payrollApi.policy(),
        payrollApi.defaultPeriod(),
      ])
      setRuns(list)
      setCurrency(policy.currency)
      setFrom((current) => current || period.period_start)
      setTo((current) => current || period.period_end)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load payroll', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const generate = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const run = await payrollApi.generate(from, to)
      toast(
        run.warnings?.length
          ? `Draft generated with ${run.warnings.length} warning(s)`
          : 'Payroll draft generated',
        run.warnings?.length ? 'info' : 'success',
      )
      setDetail(run)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not generate payroll', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading label="Loading payroll..." />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Payroll Management</h2>
          <p className="text-sm text-muted">
            Generate payslips from attendance, leave, and the company policy.{' '}
            <Link to="/settings/payroll" className="text-accent hover:underline">
              Edit policy
            </Link>
          </p>
        </div>
      </div>

      <form onSubmit={generate} className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-panel p-4">
        <label className="space-y-1.5 text-sm">
          <span className="text-muted">From</span>
          <input required type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="field" />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="text-muted">To</span>
          <input required type="date" value={to} onChange={(e) => setTo(e.target.value)} className="field" />
        </label>
        <button type="submit" disabled={busy} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
          {busy ? 'Generating...' : 'Generate payroll'}
        </button>
      </form>

      {runs.length === 0 ? (
        <EmptyState
          title="No payroll runs yet"
          description="Set salaries first, then generate a run for last month."
          action={
            <Link to="/salaries" className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Open Salaries
            </Link>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">Period</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Payslips</th>
                <th className="px-5 py-3">Net</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-t border-border/70">
                  <td className="px-5 py-4">
                    {run.period_start} → {run.period_end}
                  </td>
                  <td className="px-5 py-4">
                    <Badge
                      label={run.status === 'finalized' ? 'Locked' : run.status}
                      tone={run.status === 'finalized' ? 'present' : 'pending'}
                    />
                  </td>
                  <td className="px-5 py-4">{run.payslip_count}</td>
                  <td className="px-5 py-4">{money(currency, run.totals.net)}</td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                        onClick={async () => setDetail(await payrollApi.run(run.id))}
                      >
                        View
                      </button>
                      {run.status === 'draft' ? (
                        <>
                          <button
                            type="button"
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                            onClick={async () => {
                              const updated = await payrollApi.finalize(run.id)
                              toast('Payroll finalized', 'success')
                              setDetail(updated)
                              await load()
                            }}
                          >
                            Finalize
                          </button>
                          <button
                            type="button"
                            className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300"
                            onClick={async () => {
                              if (!confirm('Delete this draft?')) return
                              await payrollApi.deleteRun(run.id)
                              if (detail?.id === run.id) setDetail(null)
                              await load()
                            }}
                          >
                            Delete
                          </button>
                        </>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detail ? (
        <section className="space-y-3 rounded-xl border border-border bg-panel p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-medium">
                {detail.period_start} → {detail.period_end}
              </h3>
              <p className="text-xs text-muted">
                Gross {money(currency, detail.totals.gross)} · Deductions {money(currency, detail.totals.deductions)} · Net{' '}
                {money(currency, detail.totals.net)}
              </p>
            </div>
            <Badge
              label={detail.status === 'finalized' ? 'Locked' : detail.status}
              tone={detail.status === 'finalized' ? 'present' : 'pending'}
            />
          </div>
          {detail.warnings?.length ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-4 py-3 text-sm text-amber-200">
              {detail.warnings.map((w) => (
                <p key={w}>{w}</p>
              ))}
            </div>
          ) : null}
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-muted">
                <tr>
                  <th className="py-2 pr-4">Person</th>
                  <th className="py-2 pr-4">Present</th>
                  <th className="py-2 pr-4">Absent</th>
                  <th className="py-2 pr-4">Leave</th>
                  <th className="py-2 pr-4">Gross</th>
                  <th className="py-2 pr-4">Deductions</th>
                  <th className="py-2 pr-4">Net</th>
                </tr>
              </thead>
              <tbody>
                {(detail.payslips || []).map((row) => (
                  <tr key={row.id} className="border-t border-border/70">
                    <td className="py-2 pr-4">
                      <button type="button" className="text-left hover:text-accent" onClick={() => setSlip(row)}>
                        <p className="font-medium">{row.employee_name}</p>
                        <p className="text-xs text-muted">{row.employee_id}</p>
                      </button>
                    </td>
                    <td className="py-2 pr-4">{row.present_days}</td>
                    <td className="py-2 pr-4">{row.absent_days}</td>
                    <td className="py-2 pr-4">
                      {row.paid_leave_days} paid / {row.unpaid_leave_days} unpaid
                    </td>
                    <td className="py-2 pr-4">{money(currency, row.gross_pay)}</td>
                    <td className="py-2 pr-4">{money(currency, row.total_deductions)}</td>
                    <td className="py-2 pr-4 font-medium">{money(currency, row.net_pay)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <Modal open={!!slip} onClose={() => setSlip(null)} title={slip ? `Payslip · ${slip.employee_name}` : 'Payslip'}>
        {slip ? (
          <div className="space-y-3 text-sm">
            <p className="text-muted">
              {slip.employee_id}
              {slip.department ? ` · ${slip.department}` : ''} · {slip.pay_type}
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
              <div><dt className="text-xs text-muted">Present / late / half</dt><dd>{slip.present_days} / {slip.late_days} / {slip.half_days}</dd></div>
              <div><dt className="text-xs text-muted">Absent / unpaid leave</dt><dd>{slip.absent_days} / {slip.unpaid_leave_days}</dd></div>
              <div><dt className="text-xs text-muted">Paid leave</dt><dd>{slip.paid_leave_days}</dd></div>
              <div><dt className="text-xs text-muted">Overtime</dt><dd>{slip.overtime_minutes} min</dd></div>
              <div><dt className="text-xs text-muted">Basic</dt><dd>{money(currency, slip.basic_pay)}</dd></div>
              <div><dt className="text-xs text-muted">Allowances</dt><dd>{money(currency, slip.allowances)}</dd></div>
              <div><dt className="text-xs text-muted">Overtime pay</dt><dd>{money(currency, slip.overtime_pay)}</dd></div>
              <div><dt className="text-xs text-muted">Absent deduction</dt><dd>{money(currency, slip.absent_deduction)}</dd></div>
              <div><dt className="text-xs text-muted">Late deduction</dt><dd>{money(currency, slip.late_deduction)}</dd></div>
              <div><dt className="text-xs text-muted">Unpaid leave</dt><dd>{money(currency, slip.unpaid_leave_deduction)}</dd></div>
              <div><dt className="text-xs text-muted">Half-day deduction</dt><dd>{money(currency, slip.half_day_deduction)}</dd></div>
              <div><dt className="text-xs text-muted">Early leave</dt><dd>{money(currency, slip.early_leave_deduction)}</dd></div>
              <div><dt className="text-xs text-muted">Tax / PF</dt><dd>{money(currency, slip.tax)} / {money(currency, slip.provident_fund)}</dd></div>
              <div><dt className="text-xs text-muted">Other deduction</dt><dd>{money(currency, slip.other_deduction)}</dd></div>
            </dl>
            <div className="flex justify-between border-t border-border pt-3 font-medium">
              <span>Net pay</span>
              <span>{money(currency, slip.net_pay)}</span>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

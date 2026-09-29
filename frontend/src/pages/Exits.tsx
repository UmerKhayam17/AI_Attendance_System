import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { employeeApi, exitApi } from '../api/services'
import { Badge } from '../components/Badge'
import { EmptyState, Loading, Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { Employee, ExitCase, ExitStatus, ExitType } from '../types'

const TYPE_LABEL: Record<ExitType, string> = {
  resignation: 'Resignation',
  termination: 'Termination',
  contract_end: 'End of contract',
  retirement: 'Retirement',
  absconding: 'Absconding',
}

function statusTone(status: ExitStatus) {
  if (status === 'completed') return 'present' as const
  if (status === 'cancelled') return 'absent' as const
  if (status === 'in_progress') return 'enrolled' as const
  return 'pending' as const
}

export default function ExitsPage() {
  const { toast } = useToast()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<ExitCase[]>([])
  const [people, setPeople] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'open' | 'all'>('open')
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<ExitCase | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    employee: '' as number | '',
    exit_type: 'resignation' as ExitType,
    resignation_date: new Date().toISOString().slice(0, 10),
    last_working_day: '',
    notice_period_days: 30,
    notice_buyout_days: 0,
    reason: '',
  })

  const load = useCallback(async () => {
    try {
      const [cases, employees] = await Promise.all([exitApi.cases(), employeeApi.list()])
      setRows(cases)
      setPeople(employees.filter((e) => e.is_active))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load exits', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const code = searchParams.get('employee')
    if (!code || !people.length) return
    const emp = people.find((p) => p.employee_id === code)
    if (!emp) return
    setOpen(true)
    onEmployeeChange(emp.id)
    // Prefill once people are loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, people])

  const onEmployeeChange = async (employeePk: number | '') => {
    setForm((f) => ({ ...f, employee: employeePk }))
    const person = people.find((p) => p.id === employeePk)
    if (!person) return
    try {
      const suggest = await exitApi.suggest(person.employee_id, form.resignation_date)
      setForm((f) => ({
        ...f,
        employee: employeePk,
        notice_period_days: suggest.notice_period_days,
        last_working_day: suggest.last_working_day,
      }))
    } catch {
      /* policy still loads with defaults */
    }
  }

  const create = async (e: FormEvent) => {
    e.preventDefault()
    if (form.employee === '') return
    setSaving(true)
    try {
      const created = await exitApi.create({
        employee: Number(form.employee),
        exit_type: form.exit_type,
        resignation_date: form.resignation_date,
        last_working_day: form.last_working_day || undefined,
        notice_period_days: form.notice_period_days,
        notice_buyout_days: form.notice_buyout_days,
        reason: form.reason,
      })
      toast('Exit case started', 'success')
      setOpen(false)
      setDetail(created)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not start exit', 'error')
    } finally {
      setSaving(false)
    }
  }

  const refreshDetail = async (id: number) => {
    const next = await exitApi.case(id)
    setDetail(next)
    await load()
  }

  if (loading) return <Loading label="Loading exit cases..." />

  const visible = filter === 'open'
    ? rows.filter((r) => r.status === 'initiated' || r.status === 'in_progress')
    : rows

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Exit Management</h2>
          <p className="text-sm text-muted">
            Notice, clearance, interview, and offboarding.{' '}
            <Link to="/settings/exit" className="text-accent hover:underline">Edit policy</Link>
          </p>
        </div>
        <div className="flex gap-2">
          <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} className="field">
            <option value="open">Open cases</option>
            <option value="all">All cases</option>
          </select>
          <button type="button" onClick={() => setOpen(true)} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
            Start exit
          </button>
        </div>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          title="No exit cases"
          description="Start an exit to run notice period, department clearance, and final deactivation."
          action={
            <button type="button" onClick={() => setOpen(true)} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Start exit
            </button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">Person</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Last day</th>
                <th className="px-5 py-3">Clearance</th>
                <th className="px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr
                  key={row.id}
                  className="cursor-pointer border-t border-border/70 hover:bg-surface/40"
                  onClick={() => setDetail(row)}
                >
                  <td className="px-5 py-4">
                    <p className="font-medium">{row.employee_name}</p>
                    <p className="text-xs text-muted">{row.employee_id}</p>
                  </td>
                  <td className="px-5 py-4">{TYPE_LABEL[row.exit_type]}</td>
                  <td className="px-5 py-4">{row.last_working_day}</td>
                  <td className="px-5 py-4">
                    {row.checklist_items.filter((i) => i.is_cleared).length}/{row.checklist_items.length}
                  </td>
                  <td className="px-5 py-4">
                    <Badge label={row.status.replace('_', ' ')} tone={statusTone(row.status)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Start exit">
        <form onSubmit={create} className="space-y-4">
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Person</span>
            <select required value={form.employee} onChange={(e) => onEmployeeChange(e.target.value ? Number(e.target.value) : '')} className="field">
              <option value="">Select...</option>
              {people.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.employee_id} — {emp.first_name} {emp.last_name}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Exit type</span>
            <select value={form.exit_type} onChange={(e) => setForm({ ...form, exit_type: e.target.value as ExitType })} className="field">
              {Object.entries(TYPE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Resignation / notice date</span>
              <input required type="date" value={form.resignation_date} onChange={(e) => setForm({ ...form, resignation_date: e.target.value })} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Last working day</span>
              <input type="date" value={form.last_working_day} onChange={(e) => setForm({ ...form, last_working_day: e.target.value })} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Notice days</span>
              <input type="number" min="0" value={form.notice_period_days} onChange={(e) => setForm({ ...form, notice_period_days: Number(e.target.value) })} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Buyout days</span>
              <input type="number" min="0" value={form.notice_buyout_days} onChange={(e) => setForm({ ...form, notice_buyout_days: Number(e.target.value) })} className="field" />
            </label>
          </div>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Reason</span>
            <textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="field min-h-20" />
          </label>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">Cancel</button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Starting...' : 'Start exit'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail ? `Exit · ${detail.employee_name}` : 'Exit'} wide>
        {detail ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted">
                {TYPE_LABEL[detail.exit_type]} · last day {detail.last_working_day}
                {detail.notice_shortfall_days ? ` · ${detail.notice_shortfall_days} notice day(s) short` : ''}
              </p>
              <Badge label={detail.status.replace('_', ' ')} tone={statusTone(detail.status)} />
            </div>
            {detail.reason ? <p className="text-sm">{detail.reason}</p> : null}

            <section>
              <h4 className="mb-2 font-medium">Clearance</h4>
              <ul className="divide-y divide-border/70 rounded-lg border border-border">
                {detail.checklist_items.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                    <div>
                      <p>{item.title}</p>
                      <p className="text-xs text-muted capitalize">{item.category}{item.cleared_by_email ? ` · ${item.cleared_by_email}` : ''}</p>
                    </div>
                    {detail.status === 'completed' || detail.status === 'cancelled' ? (
                      <Badge label={item.is_cleared ? 'Cleared' : 'Pending'} tone={item.is_cleared ? 'present' : 'pending'} />
                    ) : (
                      <button
                        type="button"
                        className={`rounded-lg px-3 py-1.5 text-xs ${item.is_cleared ? 'bg-emerald-700 text-white' : 'border border-border'}`}
                        onClick={async () => {
                          try {
                            await exitApi.toggleItem(detail.id, item.id)
                            await refreshDetail(detail.id)
                          } catch (err) {
                            toast(err instanceof Error ? err.message : 'Update failed', 'error')
                          }
                        }}
                      >
                        {item.is_cleared ? 'Cleared' : 'Mark cleared'}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>

            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Handover notes</span>
              <textarea
                disabled={detail.status === 'completed' || detail.status === 'cancelled'}
                value={detail.handover_notes}
                onChange={(e) => setDetail({ ...detail, handover_notes: e.target.value })}
                onBlur={async () => {
                  if (detail.status === 'completed' || detail.status === 'cancelled') return
                  await exitApi.update(detail.id, { handover_notes: detail.handover_notes })
                }}
                className="field min-h-16"
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Exit interview</span>
              <textarea
                disabled={detail.status === 'completed' || detail.status === 'cancelled'}
                value={detail.interview_notes}
                onChange={(e) => setDetail({ ...detail, interview_notes: e.target.value })}
                onBlur={async () => {
                  if (detail.status === 'completed' || detail.status === 'cancelled') return
                  await exitApi.update(detail.id, { interview_notes: detail.interview_notes })
                }}
                className="field min-h-16"
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Final settlement notes</span>
              <textarea
                disabled={detail.status === 'completed' || detail.status === 'cancelled'}
                value={detail.final_settlement_notes || ''}
                onChange={(e) => setDetail({ ...detail, final_settlement_notes: e.target.value })}
                onBlur={async () => {
                  if (detail.status === 'completed' || detail.status === 'cancelled') return
                  await exitApi.update(detail.id, { final_settlement_notes: detail.final_settlement_notes })
                }}
                className="field min-h-16"
              />
            </label>
            {detail.status !== 'completed' && detail.status !== 'cancelled' ? (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={detail.interview_completed}
                  onChange={async (e) => {
                    const next = await exitApi.update(detail.id, { interview_completed: e.target.checked })
                    setDetail(next)
                  }}
                />
                Interview completed
              </label>
            ) : null}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                disabled={detail.status === 'completed' || detail.status === 'cancelled'}
                checked={detail.rehire_eligible}
                onChange={async (e) => {
                  const next = await exitApi.update(detail.id, { rehire_eligible: e.target.checked })
                  setDetail(next)
                }}
              />
              Eligible for rehire
            </label>

            {detail.status === 'initiated' || detail.status === 'in_progress' ? (
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  className="rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-300"
                  onClick={async () => {
                    if (!confirm('Cancel this exit?')) return
                    try {
                      setDetail(await exitApi.cancel(detail.id))
                      await load()
                    } catch (err) {
                      toast(err instanceof Error ? err.message : 'Cancel failed', 'error')
                    }
                  }}
                >
                  Cancel exit
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
                  onClick={async () => {
                    try {
                      const next = await exitApi.complete(detail.id)
                      setDetail(next)
                      toast('Exit completed — person deactivated', 'success')
                      await load()
                    } catch (err) {
                      toast(err instanceof Error ? err.message : 'Cannot complete yet', 'error')
                    }
                  }}
                >
                  Complete exit
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

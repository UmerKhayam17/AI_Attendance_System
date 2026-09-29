import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { approvalApi, attendanceApi, employeeApi, orgApi, payrollApi } from '../api/services'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { EmptyState, Loading, Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { ApprovalRequest, Employee, LeaveBalance, LeaveRequest, LeaveType } from '../types'

export default function LeavePage() {
  const { labels } = useAuth()
  const { toast } = useToast()
  const [rows, setRows] = useState<LeaveRequest[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [balances, setBalances] = useState<LeaveBalance[]>([])
  const [types, setTypes] = useState<LeaveType[]>([])
  const [inbox, setInbox] = useState<ApprovalRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [employee, setEmployee] = useState<number | ''>('')
  const [leaveType, setLeaveType] = useState('annual')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [leave, people, leaveBalances, leaveTypes, pending] = await Promise.all([
        attendanceApi.leave(),
        employeeApi.list(),
        payrollApi.leaveBalances(),
        orgApi.leaveTypes().catch(() => []),
        approvalApi.inbox().catch(() => []),
      ])
      setRows(leave)
      setEmployees(people.filter((e) => e.is_active))
      setBalances(leaveBalances)
      setTypes(leaveTypes.filter((t) => t.is_active))
      setInbox(pending)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load leave', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (employee === '') return
    setSaving(true)
    try {
      await attendanceApi.createLeave({
        employee: Number(employee),
        leave_type: leaveType,
        start_date: start,
        end_date: end,
        reason,
      })
      toast('Leave request created', 'success')
      setOpen(false)
      setReason('')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not create leave', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading />

  const selectedBalance = balances.find((b) => b.employee_pk === employee)
  const selectedRemaining = selectedBalance?.balances[leaveType]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Leave Management</h2>
          <p className="text-sm text-muted">
            Approved leave is excluded from absence counts and uses the company leave allowance.{' '}
            <Link to="/settings/payroll" className="text-accent hover:underline">
              Edit policy
            </Link>
          </p>
        </div>
        <button type="button" onClick={() => setOpen(true)} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
          New leave
        </button>
      </div>

      {inbox.length > 0 ? (
        <section className="rounded-xl border border-border bg-panel p-5">
          <h3 className="mb-3 font-medium">Inbox</h3>
          <ul className="divide-y divide-border/70 text-sm">
            {inbox.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
                <div>
                  <p className="font-medium">
                    {item.kind_label} · {item.employee_name}
                  </p>
                  <p className="text-xs text-muted">Waiting on {item.current_step_role || 'admin'}</p>
                </div>
                {item.can_act ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="rounded-lg border border-border px-3 py-1.5 text-xs"
                      onClick={async () => {
                        try {
                          await approvalApi.approve(item.id)
                          await load()
                        } catch (err) {
                          toast(err instanceof Error ? err.message : 'Could not approve', 'error')
                        }
                      }}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300"
                      onClick={async () => {
                        await approvalApi.reject(item.id)
                        await load()
                      }}
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title="No leave requests" description={`Add leave for ${labels.people.toLowerCase()} who should not be marked absent.`} />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">{labels.person}</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Dates</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-border/70">
                  <td className="px-5 py-4">
                    <p className="font-medium">{row.employee_name}</p>
                    <p className="text-xs text-muted">{row.employee_id}</p>
                  </td>
                  <td className="px-5 py-4 capitalize">{row.leave_type}</td>
                  <td className="px-5 py-4">
                    {row.start_date} → {row.end_date}
                  </td>
                  <td className="px-5 py-4">
                    <Badge
                      label={row.status}
                      tone={row.status === 'approved' ? 'present' : row.status === 'rejected' ? 'absent' : 'pending'}
                    />
                  </td>
                  <td className="px-5 py-4">
                    {row.status === 'pending' ? (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          className="rounded-lg border border-border px-3 py-1.5 text-xs"
                          onClick={async () => {
                            try {
                              await attendanceApi.approveLeave(row.id)
                              await load()
                            } catch (err) {
                              toast(err instanceof Error ? err.message : 'Could not approve', 'error')
                            }
                          }}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300"
                          onClick={async () => {
                            await attendanceApi.rejectLeave(row.id)
                            await load()
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-muted">{row.decided_by_email || '—'}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="New leave request">
        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">{labels.person}</span>
            <select required value={employee} onChange={(e) => setEmployee(e.target.value ? Number(e.target.value) : '')} className="field">
              <option value="">Select...</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.employee_id} — {emp.first_name} {emp.last_name}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Type</span>
            <select value={leaveType} onChange={(e) => setLeaveType(e.target.value)} className="field">
              {(types.length ? types : [
                { code: 'annual', name: 'Annual' },
                { code: 'sick', name: 'Sick' },
                { code: 'unpaid', name: 'Unpaid' },
                { code: 'other', name: 'Other' },
              ]).map((row) => (
                <option key={row.code} value={row.code}>
                  {row.name}
                </option>
              ))}
            </select>
            {selectedRemaining ? (
              <span className="text-xs text-muted">
                {selectedBalance?.in_probation ? 'In probation. ' : ''}
                {selectedRemaining.remaining == null
                  ? `${selectedRemaining.used} unpaid day(s) used this year`
                  : `${selectedRemaining.remaining} of ${selectedRemaining.entitled} remaining (${selectedRemaining.paid ? 'paid' : 'unpaid'})`}
              </span>
            ) : null}
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Start</span>
              <input required type="date" value={start} onChange={(e) => setStart(e.target.value)} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">End</span>
              <input required type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="field" />
            </label>
          </div>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Reason</span>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} className="field min-h-20" />
          </label>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

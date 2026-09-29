import { useCallback, useEffect, useMemo, useState } from 'react'
import { attendanceApi, employeeApi } from '../api/services'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { BranchFilter } from '../components/BranchFilter'
import { EmptyState, Loading, Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { AttendanceRecord, Employee } from '../types'

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function AttendancePage() {
  const { labels, role } = useAuth()
  const { toast } = useToast()
  const [records, setRecords] = useState<AttendanceRecord[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)
  const [employeeFilter, setEmployeeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [dateFilter, setDateFilter] = useState('')
  const [branchFilter, setBranchFilter] = useState<number | 'all'>('all')
  const [manualOpen, setManualOpen] = useState(false)
  const [correctOpen, setCorrectOpen] = useState(false)
  const [correctRecord, setCorrectRecord] = useState<AttendanceRecord | null>(null)
  const [correctIn, setCorrectIn] = useState('')
  const [correctOut, setCorrectOut] = useState('')
  const [correctReason, setCorrectReason] = useState('')
  const [manualEmployee, setManualEmployee] = useState('')
  const [manualAction, setManualAction] = useState<'check_in' | 'check_out'>('check_in')
  const [manualNotes, setManualNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    try {
      const [recordsData, employeesData] = await Promise.all([
        attendanceApi.list({
          employee_id: employeeFilter !== 'all' ? employeeFilter : undefined,
          date: dateFilter || undefined,
          status: statusFilter !== 'all' ? statusFilter : undefined,
          branch: branchFilter === 'all' ? undefined : branchFilter,
        }),
        employeeApi.list(),
      ])
      setRecords(recordsData)
      setEmployees(employeesData.filter((e) => e.is_active))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load attendance', 'error')
    } finally {
      setLoading(false)
    }
  }, [employeeFilter, statusFilter, dateFilter, branchFilter, toast])

  useEffect(() => {
    load()
  }, [load])

  const stats = useMemo(() => {
    return {
      total: records.length,
      present: records.filter((r) => r.status === 'present').length,
      late: records.filter((r) => r.status === 'late').length,
      checkedOut: records.filter((r) => r.check_out).length,
    }
  }, [records])

  const handleManual = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!manualEmployee) return
    setSubmitting(true)
    try {
      await attendanceApi.manual(manualEmployee, manualAction, manualNotes)
      toast(`Manual ${manualAction.replace('_', ' ')} recorded`, 'success')
      setManualOpen(false)
      setManualNotes('')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Manual attendance failed', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Loading />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Attendance Management</h2>
          <p className="text-sm text-muted">View and manage attendance records</p>
        </div>
        {role !== 'viewer' && (
        <button
          type="button"
          onClick={() => setManualOpen(true)}
          className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
        >
          Manual Entry
        </button>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MiniStat label="Records" value={stats.total} />
        <MiniStat label="Present" value={stats.present} />
        <MiniStat label="Late" value={stats.late} />
        <MiniStat label="Checked Out" value={stats.checkedOut} />
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        <BranchFilter value={branchFilter} onChange={setBranchFilter} />
        <select
          value={employeeFilter}
          onChange={(e) => setEmployeeFilter(e.target.value)}
          className="field"
        >
          <option value="all">All {labels.people.toLowerCase()}</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.employee_id}>
              {emp.employee_id} — {emp.first_name}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={dateFilter}
          onChange={(e) => setDateFilter(e.target.value)}
          className="field"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="field"
        >
          <option value="all">All statuses</option>
          <option value="present">Present</option>
          <option value="late">Late</option>
          <option value="absent">Absent</option>
          <option value="half_day">Half Day</option>
          <option value="on_leave">On Leave</option>
        </select>
        <button
          type="button"
          onClick={() => {
            setEmployeeFilter('all')
            setStatusFilter('all')
            setDateFilter('')
            setBranchFilter('all')
          }}
          className="rounded-lg border border-border px-4 py-2 text-sm"
        >
          Clear Filters
        </button>
      </div>

      {records.length === 0 ? (
        <EmptyState
          title="No attendance records"
          description={`Records appear when ${labels.people.toLowerCase()} are recognized via the live monitor or manual entry.`}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-surface/60 text-left text-muted">
                <tr>
                  <th className="px-5 py-3">{labels.person}</th>
                  <th className="px-5 py-3">Date</th>
                  <th className="px-5 py-3">Check In</th>
                  <th className="px-5 py-3">Check Out</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Source</th>
                  {role !== 'viewer' ? <th className="px-5 py-3" /> : null}
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id} className="border-t border-border/70">
                    <td className="px-5 py-4">
                      <p className="font-medium">{record.employee_name}</p>
                      <p className="text-xs text-muted">{record.employee_id}</p>
                    </td>
                    <td className="px-5 py-4">{record.date}</td>
                    <td className="px-5 py-4">{formatDateTime(record.check_in)}</td>
                    <td className="px-5 py-4">{formatDateTime(record.check_out)}</td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-1">
                        <Badge label={record.status} tone={record.status} />
                        {record.early_leave && record.status !== 'half_day' ? (
                          <Badge label="early" tone="late" />
                        ) : null}
                        {record.overtime_minutes ? (
                          <Badge label={`OT ${record.overtime_minutes}m`} tone="enrolled" />
                        ) : null}
                        {record.missing_checkout ? <Badge label="missing out" tone="late" /> : null}
                      </div>
                    </td>
                    <td className="px-5 py-4 capitalize">{record.source}</td>
                    {role !== 'viewer' ? (
                      <td className="px-5 py-4">
                        <button
                          type="button"
                          className="text-xs text-accent hover:underline"
                          onClick={() => {
                            setCorrectRecord(record)
                            setCorrectIn(record.check_in ? record.check_in.slice(0, 16) : '')
                            setCorrectOut(record.check_out ? record.check_out.slice(0, 16) : '')
                            setCorrectReason('')
                            setCorrectOpen(true)
                          }}
                        >
                          Correct
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={manualOpen} onClose={() => setManualOpen(false)} title="Manual Attendance">
        <form onSubmit={handleManual} className="space-y-4">
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">{labels.person}</span>
            <select
              required
              value={manualEmployee}
              onChange={(e) => setManualEmployee(e.target.value)}
              className="field"
            >
              <option value="">Select {labels.person.toLowerCase()}...</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.employee_id}>
                  {emp.employee_id} — {emp.first_name} {emp.last_name}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Action</span>
            <select
              value={manualAction}
              onChange={(e) => setManualAction(e.target.value as 'check_in' | 'check_out')}
              className="field"
            >
              <option value="check_in">Check In</option>
              <option value="check_out">Check Out</option>
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Notes</span>
            <textarea
              value={manualNotes}
              onChange={(e) => setManualNotes(e.target.value)}
              className="field min-h-24"
            />
          </label>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setManualOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {submitting ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={correctOpen} onClose={() => setCorrectOpen(false)} title="Request correction">
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault()
            if (!correctRecord) return
            const person = employees.find((emp) => emp.employee_id === correctRecord.employee_id)
            if (!person) {
              toast('Employee record not found', 'error')
              return
            }
            setSubmitting(true)
            try {
              await attendanceApi.createCorrection({
                employee: person.id,
                date: correctRecord.date,
                requested_check_in: correctIn ? new Date(correctIn).toISOString() : null,
                requested_check_out: correctOut ? new Date(correctOut).toISOString() : null,
                reason: correctReason,
              })
              toast('Correction submitted for approval', 'success')
              setCorrectOpen(false)
              await load()
            } catch (err) {
              toast(err instanceof Error ? err.message : 'Could not request correction', 'error')
            } finally {
              setSubmitting(false)
            }
          }}
        >
          <p className="text-sm text-muted">
            {correctRecord?.employee_name} · {correctRecord?.date}
          </p>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Check in</span>
            <input type="datetime-local" value={correctIn} onChange={(e) => setCorrectIn(e.target.value)} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Check out</span>
            <input type="datetime-local" value={correctOut} onChange={(e) => setCorrectOut(e.target.value)} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Reason</span>
            <textarea value={correctReason} onChange={(e) => setCorrectReason(e.target.value)} className="field min-h-20" />
          </label>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setCorrectOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {submitting ? 'Saving...' : 'Submit'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  )
}

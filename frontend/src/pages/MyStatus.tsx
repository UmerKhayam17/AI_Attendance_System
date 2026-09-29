import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { orgApi, portalApi } from '../api/services'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { EmptyState, Loading } from '../components/Modal'
import { useToast } from '../components/Toast'
import type {
  AttendanceCorrection,
  EmployeeDocument,
  ExitCase,
  LeaveBalance,
  LeaveRequest,
  LeaveType,
  OvertimeRequest,
  Payslip,
  PortalStatus,
} from '../types'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function formatTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

type Tab = 'status' | 'leave' | 'corrections' | 'overtime' | 'documents' | 'payslips' | 'resign'

function tabFromPath(pathname: string): Tab {
  if (pathname.startsWith('/me/leave')) return 'leave'
  if (pathname.startsWith('/me/corrections')) return 'corrections'
  if (pathname.startsWith('/me/overtime')) return 'overtime'
  if (pathname.startsWith('/me/documents')) return 'documents'
  if (pathname.startsWith('/me/payslips')) return 'payslips'
  if (pathname.startsWith('/me/resign')) return 'resign'
  return 'status'
}

const TAB_TITLES: Record<Tab, { employee: string; parent: string; hint: string }> = {
  status: { employee: 'My status', parent: 'Family status', hint: 'Today’s attendance for linked people.' },
  leave: { employee: 'Leave', parent: 'Leave', hint: 'Balances and leave requests.' },
  corrections: { employee: 'Corrections', parent: 'Corrections', hint: 'Request a check-in or check-out fix.' },
  overtime: { employee: 'Overtime', parent: 'Overtime', hint: 'Claim overtime for approval.' },
  documents: { employee: 'Documents', parent: 'Documents', hint: 'Files shared with you.' },
  payslips: { employee: 'Payslips', parent: 'Payslips', hint: 'Finalized pay periods.' },
  resign: { employee: 'Resignation', parent: 'Resignation', hint: 'Submit a resignation for approval.' },
}

export default function MyStatusPage() {
  const { role, labels } = useAuth()
  const { pathname } = useLocation()
  const { toast } = useToast()
  const tab = tabFromPath(pathname)
  const [date, setDate] = useState(todayIso())
  const [data, setData] = useState<PortalStatus | null>(null)
  const [leave, setLeave] = useState<LeaveRequest[]>([])
  const [types, setTypes] = useState<LeaveType[]>([])
  const [balances, setBalances] = useState<LeaveBalance[]>([])
  const [corrections, setCorrections] = useState<AttendanceCorrection[]>([])
  const [overtime, setOvertime] = useState<OvertimeRequest[]>([])
  const [documents, setDocuments] = useState<EmployeeDocument[]>([])
  const [payslips, setPayslips] = useState<Payslip[]>([])
  const [exits, setExits] = useState<ExitCase[]>([])
  const [loading, setLoading] = useState(true)
  const [leaveType, setLeaveType] = useState('annual')
  const [start, setStart] = useState(todayIso())
  const [end, setEnd] = useState(todayIso())
  const [reason, setReason] = useState('')
  const [person, setPerson] = useState<number | ''>('')
  const [saving, setSaving] = useState(false)
  const [corrDate, setCorrDate] = useState(todayIso())
  const [corrIn, setCorrIn] = useState('')
  const [corrOut, setCorrOut] = useState('')
  const [otMinutes, setOtMinutes] = useState('60')
  const [resignReason, setResignReason] = useState('')

  const load = useCallback(async () => {
    try {
      const [status, rows, leaveTypes, bals, corrs, ots, docs, slips, cases] = await Promise.all([
        portalApi.status(date),
        portalApi.leave(),
        orgApi.leaveTypes().catch(() => []),
        portalApi.balances().catch(() => []),
        portalApi.corrections().catch(() => []),
        portalApi.overtime().catch(() => []),
        portalApi.documents().catch(() => []),
        portalApi.payslips().catch(() => []),
        portalApi.resignation().catch(() => []),
      ])
      setData(status)
      setLeave(rows)
      setTypes(leaveTypes.filter((t) => t.is_active))
      setBalances(bals)
      setCorrections(corrs)
      setOvertime(ots)
      setDocuments(docs)
      setPayslips(slips)
      setExits(cases)
      if (status.people.length === 1) setPerson(status.people[0].employee_pk)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load status', 'error')
    } finally {
      setLoading(false)
    }
  }, [date, toast])

  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  const submitLeave = async (e: FormEvent) => {
    e.preventDefault()
    if (person === '') return
    setSaving(true)
    try {
      await portalApi.createLeave({
        employee: Number(person),
        leave_type: leaveType,
        start_date: start,
        end_date: end,
        reason,
      })
      toast('Leave request submitted', 'success')
      setReason('')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not submit leave', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) return <Loading label="Loading your status..." />
  if (!data) return <EmptyState title="No linked people" description="Ask an admin to invite you as a portal user." />

  const heading = TAB_TITLES[tab]
  const title = role === 'parent' ? heading.parent : heading.employee

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <p className="text-sm text-muted">
            {tab === 'status' ? `Self-service for your linked ${labels.people.toLowerCase()}.` : heading.hint}
          </p>
        </div>
        {tab === 'status' ? (
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="field w-44" />
        ) : null}
      </div>

      {tab === 'status' ? (
        data.people.length === 0 ? (
          <EmptyState title="Nothing to show" description="This login is not linked to a person yet." />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {data.people.map((personRow) => (
              <article key={personRow.employee_id} className="rounded-xl border border-border bg-panel p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-semibold">{personRow.name}</p>
                    <p className="text-xs text-muted">
                      {personRow.employee_id} · {personRow.department}
                    </p>
                  </div>
                  <Badge label={personRow.status.replace('_', ' ')} tone="pending" />
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-muted">Check in</dt>
                    <dd>{formatTime(personRow.check_in)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Check out</dt>
                    <dd>{formatTime(personRow.check_out)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">Shift</dt>
                    <dd>
                      {personRow.shift.start_time}–{personRow.shift.end_time}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Late after</dt>
                    <dd>{personRow.shift.late_after}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )
      ) : null}

      {tab === 'leave' ? (
        <section className="rounded-xl border border-border bg-panel p-5">
          {balances[0] ? (
            <p className="mb-4 text-sm text-muted">
              {Object.values(balances[0].balances)
                .filter((row) => row.remaining != null)
                .map((row) => `${row.label}: ${row.remaining}/${row.entitled}`)
                .join(' · ')}
            </p>
          ) : null}
          <form onSubmit={submitLeave} className="grid gap-3 md:grid-cols-2">
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Type</span>
              <select value={leaveType} onChange={(e) => setLeaveType(e.target.value)} className="field">
                {(types.length ? types : [{ code: 'annual', name: 'Annual' }]).map((row) => (
                  <option key={row.code} value={row.code}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Start</span>
              <input required type="date" value={start} onChange={(e) => setStart(e.target.value)} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">End</span>
              <input required type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm md:col-span-2">
              <span className="text-muted">Reason</span>
              <input value={reason} onChange={(e) => setReason(e.target.value)} className="field" />
            </label>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              Submit leave
            </button>
          </form>
          <ul className="mt-4 divide-y divide-border/70 text-sm">
            {leave.map((row) => (
              <li key={row.id} className="flex items-center justify-between py-2">
                <span>
                  {row.leave_type} · {row.start_date} → {row.end_date}
                </span>
                <Badge label={row.status} tone={row.status === 'approved' ? 'present' : 'pending'} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {tab === 'corrections' ? (
        <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
          <form
            className="grid gap-3 md:grid-cols-2"
            onSubmit={async (e) => {
              e.preventDefault()
              if (person === '') return
              setSaving(true)
              try {
                await portalApi.createCorrection({
                  employee: Number(person),
                  date: corrDate,
                  requested_check_in: corrIn ? new Date(corrIn).toISOString() : null,
                  requested_check_out: corrOut ? new Date(corrOut).toISOString() : null,
                  reason,
                })
                toast('Correction submitted', 'success')
                await load()
              } catch (err) {
                toast(err instanceof Error ? err.message : 'Could not submit', 'error')
              } finally {
                setSaving(false)
              }
            }}
          >
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Date</span>
              <input type="date" value={corrDate} onChange={(e) => setCorrDate(e.target.value)} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Check in</span>
              <input type="datetime-local" value={corrIn} onChange={(e) => setCorrIn(e.target.value)} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Check out</span>
              <input type="datetime-local" value={corrOut} onChange={(e) => setCorrOut(e.target.value)} className="field" />
            </label>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Request correction
            </button>
          </form>
          {corrections.map((row) => (
            <p key={row.id} className="text-sm">
              {row.date} · {row.status}
            </p>
          ))}
        </section>
      ) : null}

      {tab === 'overtime' ? (
        <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
          <form
            className="grid gap-3 md:grid-cols-3"
            onSubmit={async (e) => {
              e.preventDefault()
              if (person === '') return
              setSaving(true)
              try {
                await portalApi.createOvertime({
                  employee: Number(person),
                  date: corrDate,
                  minutes: Number(otMinutes),
                  reason,
                })
                toast('Overtime submitted', 'success')
                await load()
              } catch (err) {
                toast(err instanceof Error ? err.message : 'Could not submit', 'error')
              } finally {
                setSaving(false)
              }
            }}
          >
            <input type="date" value={corrDate} onChange={(e) => setCorrDate(e.target.value)} className="field" />
            <input type="number" min="1" value={otMinutes} onChange={(e) => setOtMinutes(e.target.value)} className="field" />
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Claim overtime
            </button>
          </form>
          {overtime.map((row) => (
            <p key={row.id} className="text-sm">
              {row.date} · {row.minutes}m · {row.status}
            </p>
          ))}
        </section>
      ) : null}

      {tab === 'documents' ? (
        <section className="rounded-xl border border-border bg-panel p-5">
          {documents.length === 0 ? (
            <p className="text-sm text-muted">No documents uploaded yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {documents.map((doc) => (
                <li key={doc.id}>
                  <a href={doc.file_url} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                    {doc.title}
                  </a>
                  <span className="text-muted"> · {doc.category}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {tab === 'payslips' ? (
        <section className="rounded-xl border border-border bg-panel p-5">
          {payslips.length === 0 ? (
            <p className="text-sm text-muted">No finalized payslips yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {payslips.map((slip) => (
                <li key={slip.id} className="flex justify-between">
                  <span>
                    {slip.period_start} → {slip.period_end}
                  </span>
                  <span>{slip.net_pay}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {tab === 'resign' ? (
        <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
          <form
            onSubmit={async (e) => {
              e.preventDefault()
              if (person === '') return
              setSaving(true)
              try {
                await portalApi.requestResignation({ employee: Number(person), reason: resignReason })
                toast('Resignation submitted for approval', 'success')
                await load()
              } catch (err) {
                toast(err instanceof Error ? err.message : 'Could not submit', 'error')
              } finally {
                setSaving(false)
              }
            }}
            className="space-y-3"
          >
            <textarea value={resignReason} onChange={(e) => setResignReason(e.target.value)} className="field min-h-20" placeholder="Reason" />
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Request resignation
            </button>
          </form>
          {exits.map((row) => (
            <p key={row.id} className="text-sm">
              {row.status} · last day {row.last_working_day}
            </p>
          ))}
        </section>
      ) : null}
    </div>
  )
}

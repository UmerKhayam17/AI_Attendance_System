import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { employeeApi, orgApi, visitorApi } from '../api/services'
import { useAuth } from '../auth/AuthContext'
import { canManageOrg, canOperate } from '../auth/roles'
import { Badge, StatCard } from '../components/Badge'
import { BranchFilter } from '../components/BranchFilter'
import { EmptyState, Loading, Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { Branch, Employee, Visit, VisitPurpose, VisitStatus, Visitor, VisitorIdType, VisitSummary } from '../types'

const PURPOSES: { id: VisitPurpose; label: string }[] = [
  { id: 'meeting', label: 'Meeting' },
  { id: 'interview', label: 'Interview' },
  { id: 'delivery', label: 'Delivery' },
  { id: 'contractor', label: 'Contractor' },
  { id: 'parent', label: 'Parent / guardian' },
  { id: 'vendor', label: 'Vendor' },
  { id: 'other', label: 'Other' },
]

const ID_TYPES: { id: VisitorIdType; label: string }[] = [
  { id: 'cnic', label: 'CNIC / National ID' },
  { id: 'passport', label: 'Passport' },
  { id: 'license', label: 'Driving license' },
  { id: 'other', label: 'Other' },
]

type Tab = 'onsite' | 'expected' | 'today' | 'all' | 'directory' | 'watchlist'
type FormMode = 'walkin' | 'preregister'

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function localInputValue(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function toIso(local: string) {
  if (!local) return undefined
  const d = new Date(local)
  if (Number.isNaN(d.getTime())) return undefined
  return d.toISOString()
}

function formatWhen(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function statusTone(status: VisitStatus) {
  if (status === 'checked_in') return 'present' as const
  if (status === 'expected') return 'pending' as const
  if (status === 'checked_out') return 'enrolled' as const
  if (status === 'denied' || status === 'no_show') return 'absent' as const
  return 'inactive' as const
}

const emptyForm = {
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  company: '',
  id_type: 'cnic' as VisitorIdType,
  id_number: '',
  visitor: '' as number | '',
  host: '' as number | '',
  branch: '' as number | '',
  purpose: 'meeting' as VisitPurpose,
  expected_at: localInputValue(),
  expected_end: '',
  vehicle_plate: '',
  notes: '',
  check_in_now: true,
}

export default function VisitorsPage() {
  const { toast } = useToast()
  const { role, labels } = useAuth()
  const operate = canOperate(role)
  const manage = canManageOrg(role)
  const [tab, setTab] = useState<Tab>('onsite')
  const [branch, setBranch] = useState<number | 'all'>('all')
  const [query, setQuery] = useState('')
  const [summary, setSummary] = useState<VisitSummary | null>(null)
  const [visits, setVisits] = useState<Visit[]>([])
  const [people, setPeople] = useState<Visitor[]>([])
  const [hosts, setHosts] = useState<Employee[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<number | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState<FormMode>('walkin')
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const isDirectory = tab === 'directory' || tab === 'watchlist'

  const load = useCallback(async () => {
    try {
      const branchId = branch === 'all' ? undefined : branch
      const [desk, hostList, branchList] = await Promise.all([
        visitorApi.summary(branchId),
        employeeApi.list(),
        orgApi.branches(),
      ])
      setSummary(desk)
      setHosts(hostList.filter((e) => e.is_active))
      setBranches(branchList.filter((b) => b.is_active))

      if (tab === 'directory' || tab === 'watchlist') {
        setPeople(await visitorApi.people({ watchlist: tab === 'watchlist', q: query || undefined }))
        setVisits([])
      } else {
        const params: { status?: string; date?: string; q?: string; branch?: number } = {
          q: query || undefined,
          branch: branchId,
        }
        if (tab === 'onsite') params.status = 'checked_in'
        if (tab === 'expected') params.status = 'expected'
        if (tab === 'today') params.date = todayIso()
        setVisits(await visitorApi.visits(params))
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load visitors', 'error')
    } finally {
      setLoading(false)
    }
  }, [branch, query, tab, toast])

  useEffect(() => {
    setLoading(true)
    const timer = window.setTimeout(load, query ? 250 : 0)
    return () => window.clearTimeout(timer)
  }, [load, query])

  const openForm = async (mode: FormMode) => {
    setFormMode(mode)
    setForm({
      ...emptyForm,
      expected_at: localInputValue(),
      check_in_now: mode === 'walkin',
      branch: branch === 'all' ? '' : branch,
    })
    setFormOpen(true)
    try {
      setPeople(await visitorApi.people())
    } catch {
      /* directory is optional for new walk-ins */
    }
  }

  const submitVisit = async (e: FormEvent) => {
    e.preventDefault()
    if (!form.visitor && !form.first_name.trim()) {
      toast('Visitor name is required', 'error')
      return
    }
    setSaving(true)
    try {
      await visitorApi.create({
        visitor: form.visitor === '' ? undefined : Number(form.visitor),
        first_name: form.first_name.trim() || undefined,
        last_name: form.last_name.trim() || undefined,
        phone: form.phone.trim() || undefined,
        email: form.email.trim() || undefined,
        company: form.company.trim() || undefined,
        id_type: form.id_type,
        id_number: form.id_number.trim() || undefined,
        host: form.host === '' ? null : Number(form.host),
        branch: form.branch === '' ? null : Number(form.branch),
        purpose: form.purpose,
        source: formMode === 'walkin' ? 'walkin' : 'preregister',
        expected_at: formMode === 'preregister' ? toIso(form.expected_at) : undefined,
        expected_end: toIso(form.expected_end),
        vehicle_plate: form.vehicle_plate.trim() || undefined,
        notes: form.notes.trim() || undefined,
        check_in_now: formMode === 'walkin' && form.check_in_now,
      })
      toast(formMode === 'walkin' ? 'Visitor logged' : 'Visit pre-registered', 'success')
      setFormOpen(false)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save visit', 'error')
    } finally {
      setSaving(false)
    }
  }

  const run = async (id: number, action: () => Promise<unknown>, ok: string) => {
    setBusy(id)
    try {
      await action()
      toast(ok, 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Action failed', 'error')
    } finally {
      setBusy(null)
    }
  }

  const copyGate = async (visit: Visit) => {
    const url = `${window.location.origin}${visit.gate_path}`
    try {
      await navigator.clipboard.writeText(url)
      toast('Gate link copied', 'success')
    } catch {
      toast(url, 'success')
    }
  }

  const selectedVisitor = useMemo(
    () => (form.visitor === '' ? null : people.find((p) => p.id === form.visitor) || null),
    [form.visitor, people],
  )

  if (loading && !summary) return <Loading label="Loading visitors..." />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Visitor management</h2>
          <p className="text-sm text-muted">
            Walk-in desk, pre-registration, badges, and watchlist for guests at your {labels.branch.toLowerCase()}.
          </p>
        </div>
        {operate ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => openForm('preregister')} className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-surface">
              Pre-register
            </button>
            <button type="button" onClick={() => openForm('walkin')} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Walk-in
            </button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="On site" value={summary?.on_site ?? 0} accent="text-emerald-400" />
        <StatCard title="Expected today" value={summary?.expected_today ?? 0} accent="text-amber-400" />
        <StatCard title="Checked in today" value={summary?.checked_in_today ?? 0} accent="text-cyan-400" />
        <StatCard title="Watchlist" value={summary?.watchlist ?? 0} accent="text-red-400" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ['onsite', 'On site'],
            ['expected', 'Expected'],
            ['today', 'Today'],
            ['all', 'All visits'],
            ['directory', 'Directory'],
            ['watchlist', 'Watchlist'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`rounded-lg px-3 py-1.5 text-sm ${tab === id ? 'bg-accent text-white' : 'border border-border hover:bg-surface'}`}
          >
            {label}
          </button>
        ))}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <BranchFilter value={branch} onChange={setBranch} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, phone, badge…"
            className="field w-56"
          />
        </div>
      </div>

      {isDirectory ? (
        people.length === 0 ? (
          <EmptyState
            title={tab === 'watchlist' ? 'Watchlist is empty' : 'No visitors yet'}
            description={
              tab === 'watchlist'
                ? 'Blocked guests appear here and cannot check in.'
                : 'Walk-in or pre-register a guest to start the directory.'
            }
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border bg-panel">
            <table className="min-w-full text-sm">
              <thead className="text-left text-muted">
                <tr>
                  <th className="px-5 py-3">Visitor</th>
                  <th className="px-5 py-3">Phone</th>
                  <th className="px-5 py-3">Company</th>
                  <th className="px-5 py-3">ID</th>
                  <th className="px-5 py-3">Visits</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {people.map((person) => (
                  <tr key={person.id} className="border-t border-border/70">
                    <td className="px-5 py-3">
                      <p className="font-medium">{person.full_name}</p>
                      <p className="text-xs text-muted">{person.email || '—'}</p>
                      {person.is_blacklisted ? <Badge label="Watchlist" tone="absent" /> : null}
                    </td>
                    <td className="px-5 py-3">{person.phone || '—'}</td>
                    <td className="px-5 py-3">{person.company || '—'}</td>
                    <td className="px-5 py-3">
                      {person.id_number ? `${person.id_type.toUpperCase()} ${person.id_number}` : '—'}
                    </td>
                    <td className="px-5 py-3">{person.visit_count ?? 0}</td>
                    <td className="px-5 py-3 text-right">
                      {manage ? (
                        <button
                          type="button"
                          disabled={busy === person.id}
                          onClick={() => {
                            const reason = person.is_blacklisted
                              ? ''
                              : window.prompt('Watchlist reason (optional)') ?? ''
                            void run(
                              person.id,
                              () => visitorApi.watchlist(person.id, !person.is_blacklisted, reason),
                              person.is_blacklisted ? 'Removed from watchlist' : 'Added to watchlist',
                            )
                          }}
                          className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                        >
                          {person.is_blacklisted ? 'Unblock' : 'Watchlist'}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : visits.length === 0 ? (
        <EmptyState
          title="No visits"
          description="Register a walk-in at the desk or pre-register a guest with a host."
          action={
            operate ? (
              <button type="button" onClick={() => openForm('walkin')} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
                Walk-in
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">Visitor</th>
                <th className="px-5 py-3">Host</th>
                <th className="px-5 py-3">Purpose</th>
                <th className="px-5 py-3">When</th>
                <th className="px-5 py-3">Badge</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {visits.map((visit) => (
                <tr key={visit.id} className="border-t border-border/70 align-top">
                  <td className="px-5 py-3">
                    <p className="font-medium">{visit.visitor_detail.full_name}</p>
                    <p className="text-xs text-muted">
                      {[visit.visitor_detail.company, visit.visitor_detail.phone, visit.branch_name]
                        .filter(Boolean)
                        .join(' · ') || '—'}
                    </p>
                    {visit.visitor_detail.is_blacklisted ? <Badge label="Watchlist" tone="absent" /> : null}
                  </td>
                  <td className="px-5 py-3">{visit.host_name || '—'}</td>
                  <td className="px-5 py-3">{visit.purpose_label}</td>
                  <td className="px-5 py-3">
                    <p>{formatWhen(visit.check_in_at || visit.expected_at)}</p>
                    {visit.check_out_at ? <p className="text-xs text-muted">Out {formatWhen(visit.check_out_at)}</p> : null}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs">{visit.badge_code || '—'}</td>
                  <td className="px-5 py-3">
                    <Badge label={visit.status_label} tone={statusTone(visit.status)} />
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap justify-end gap-1.5">
                      {operate && visit.status === 'expected' ? (
                        <>
                          <button
                            type="button"
                            disabled={busy === visit.id}
                            onClick={() => run(visit.id, () => visitorApi.checkIn(visit.id), 'Checked in')}
                            className="rounded-lg bg-accent px-2.5 py-1 text-xs text-white disabled:opacity-50"
                          >
                            Check in
                          </button>
                          <button
                            type="button"
                            disabled={busy === visit.id}
                            onClick={() => run(visit.id, () => visitorApi.cancel(visit.id), 'Cancelled')}
                            className="rounded-lg border border-border px-2.5 py-1 text-xs hover:bg-surface"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            disabled={busy === visit.id}
                            onClick={() => run(visit.id, () => visitorApi.noShow(visit.id), 'Marked no-show')}
                            className="rounded-lg border border-border px-2.5 py-1 text-xs hover:bg-surface"
                          >
                            No show
                          </button>
                        </>
                      ) : null}
                      {operate && visit.status === 'checked_in' ? (
                        <button
                          type="button"
                          disabled={busy === visit.id}
                          onClick={() => run(visit.id, () => visitorApi.checkOut(visit.id), 'Checked out')}
                          className="rounded-lg bg-accent px-2.5 py-1 text-xs text-white disabled:opacity-50"
                        >
                          Check out
                        </button>
                      ) : null}
                      {operate && visit.status !== 'denied' && visit.status !== 'cancelled' ? (
                        <button
                          type="button"
                          disabled={busy === visit.id}
                          onClick={() => {
                            const reason = window.prompt('Deny reason (optional)') ?? ''
                            void run(visit.id, () => visitorApi.deny(visit.id, reason), 'Visit denied')
                          }}
                          className="rounded-lg border border-border px-2.5 py-1 text-xs hover:bg-surface"
                        >
                          Deny
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => copyGate(visit)}
                        className="rounded-lg border border-border px-2.5 py-1 text-xs hover:bg-surface"
                      >
                        Gate link
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={formOpen}
        title={formMode === 'walkin' ? 'Walk-in visitor' : 'Pre-register visit'}
        onClose={() => setFormOpen(false)}
        wide
      >
        <form onSubmit={submitVisit} className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1.5 text-sm sm:col-span-2">
            <span className="text-muted">Returning visitor</span>
            <select
              value={form.visitor}
              onChange={(e) => setForm((f) => ({ ...f, visitor: e.target.value ? Number(e.target.value) : '' }))}
              className="field"
            >
              <option value="">New visitor</option>
              {people
                .concat()
                .sort((a, b) => a.full_name.localeCompare(b.full_name))
                .map((person) => (
                  <option key={person.id} value={person.id} disabled={person.is_blacklisted}>
                    {person.full_name}
                    {person.phone ? ` · ${person.phone}` : ''}
                    {person.is_blacklisted ? ' (watchlist)' : ''}
                  </option>
                ))}
            </select>
          </label>
          {!selectedVisitor ? (
            <>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">First name</span>
                <input required value={form.first_name} onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))} className="field" />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Last name</span>
                <input value={form.last_name} onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))} className="field" />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Phone</span>
                <input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} className="field" />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Email</span>
                <input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} className="field" />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Company</span>
                <input value={form.company} onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))} className="field" />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">ID type</span>
                <select value={form.id_type} onChange={(e) => setForm((f) => ({ ...f, id_type: e.target.value as VisitorIdType }))} className="field">
                  {ID_TYPES.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block space-y-1.5 text-sm sm:col-span-2">
                <span className="text-muted">ID number</span>
                <input value={form.id_number} onChange={(e) => setForm((f) => ({ ...f, id_number: e.target.value }))} className="field" />
              </label>
            </>
          ) : (
            <p className="sm:col-span-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
              {selectedVisitor.full_name}
              {selectedVisitor.company ? ` · ${selectedVisitor.company}` : ''}
              {selectedVisitor.phone ? ` · ${selectedVisitor.phone}` : ''}
            </p>
          )}
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Host</span>
            <select value={form.host} onChange={(e) => setForm((f) => ({ ...f, host: e.target.value ? Number(e.target.value) : '' }))} className="field">
              <option value="">No host</option>
              {hosts.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.first_name} {person.last_name} ({person.employee_id})
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">{labels.branch}</span>
            <select value={form.branch} onChange={(e) => setForm((f) => ({ ...f, branch: e.target.value ? Number(e.target.value) : '' }))} className="field">
              <option value="">Default</option>
              {branches.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Purpose</span>
            <select value={form.purpose} onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value as VisitPurpose }))} className="field">
              {PURPOSES.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Vehicle plate</span>
            <input value={form.vehicle_plate} onChange={(e) => setForm((f) => ({ ...f, vehicle_plate: e.target.value }))} className="field" />
          </label>
          {formMode === 'preregister' ? (
            <>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Expected</span>
                <input type="datetime-local" value={form.expected_at} onChange={(e) => setForm((f) => ({ ...f, expected_at: e.target.value }))} className="field" />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Expected end</span>
                <input type="datetime-local" value={form.expected_end} onChange={(e) => setForm((f) => ({ ...f, expected_end: e.target.value }))} className="field" />
              </label>
            </>
          ) : (
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input
                type="checkbox"
                checked={form.check_in_now}
                onChange={(e) => setForm((f) => ({ ...f, check_in_now: e.target.checked }))}
              />
              Check in now and issue badge
            </label>
          )}
          <label className="block space-y-1.5 text-sm sm:col-span-2">
            <span className="text-muted">Notes</span>
            <textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} className="field min-h-20" />
          </label>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50">
              {saving ? 'Saving…' : formMode === 'walkin' ? 'Log visitor' : 'Save visit'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

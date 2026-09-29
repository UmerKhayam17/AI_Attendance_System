import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { orgApi } from '../../api/services'
import { Badge } from '../../components/Badge'
import { EmptyState, Loading, Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { Branch, Shift } from '../../types'
import { Field, SettingsPageHeader, SettingsSection, Toggle } from './SettingsUI'

function toTimeInput(value: string) {
  return (value || '').slice(0, 5)
}

function toApiTime(value: string) {
  return value.length === 5 ? `${value}:00` : value
}

function toMinutes(value: string) {
  const [h, m] = toTimeInput(value).split(':').map(Number)
  if (Number.isNaN(h) || Number.isNaN(m)) return 0
  return h * 60 + m
}

function fromMinutes(total: number) {
  const wrapped = ((total % (24 * 60)) + 24 * 60) % (24 * 60)
  const h = Math.floor(wrapped / 60)
  const m = wrapped % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

function graceFromShift(shift: Shift) {
  const stored = Number(shift.grace_minutes) || 0
  const computed = toMinutes(shift.late_after) - toMinutes(shift.start_time)
  const normalized = computed < 0 ? computed + 24 * 60 : computed
  return stored > 0 ? stored : Math.max(0, normalized)
}

const emptyForm = {
  name: '',
  kind: 'fixed',
  branch: '' as string | number,
  start_time: '09:00',
  late_after: '09:30',
  end_time: '18:00',
  required_hours: '8',
  break_start: '',
  break_end: '',
  second_start: '',
  second_end: '',
  grace_minutes: '0',
  early_leave_grace_minutes: '15',
  overtime_grace_minutes: '15',
  is_default: false,
}

export function ShiftManager() {
  const { toast } = useToast()
  const [shifts, setShifts] = useState<Shift[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Shift | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [rows, orgBranches] = await Promise.all([orgApi.shifts(), orgApi.branches()])
      setShifts(rows)
      setBranches(orgBranches)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load shifts', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...emptyForm, is_default: shifts.length === 0 })
    setOpen(true)
  }

  const openEdit = (shift: Shift) => {
    setEditing(shift)
    setForm({
      name: shift.name,
      kind: shift.kind || 'fixed',
      branch: shift.branch ?? '',
      start_time: toTimeInput(shift.start_time),
      late_after: toTimeInput(shift.late_after),
      end_time: toTimeInput(shift.end_time),
      required_hours: shift.required_hours != null ? String(shift.required_hours) : '8',
      break_start: toTimeInput(shift.break_start || ''),
      break_end: toTimeInput(shift.break_end || ''),
      second_start: toTimeInput(shift.second_start || ''),
      second_end: toTimeInput(shift.second_end || ''),
      grace_minutes: String(graceFromShift(shift)),
      early_leave_grace_minutes: String(shift.early_leave_grace_minutes ?? 15),
      overtime_grace_minutes: String(shift.overtime_grace_minutes ?? 15),
      is_default: shift.is_default,
    })
    setOpen(true)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const grace = Math.max(0, Number(form.grace_minutes) || 0)
      const payload = {
        name: form.name.trim(),
        kind: form.kind,
        branch: form.branch === '' ? null : Number(form.branch),
        start_time: toApiTime(form.start_time),
        late_after: toApiTime(fromMinutes(toMinutes(form.start_time) + grace)),
        end_time: toApiTime(form.end_time),
        required_hours: form.kind === 'flexible' ? Number(form.required_hours) || 8 : null,
        break_start: form.break_start ? toApiTime(form.break_start) : null,
        break_end: form.break_end ? toApiTime(form.break_end) : null,
        second_start: form.kind === 'split' && form.second_start ? toApiTime(form.second_start) : null,
        second_end: form.kind === 'split' && form.second_end ? toApiTime(form.second_end) : null,
        grace_minutes: grace,
        early_leave_grace_minutes: Number(form.early_leave_grace_minutes) || 0,
        overtime_grace_minutes: Number(form.overtime_grace_minutes) || 0,
        is_default: form.is_default,
      }
      if (editing) {
        await orgApi.updateShift(editing.id, payload)
        toast('Shift updated', 'success')
      } else {
        await orgApi.createShift(payload)
        toast('Shift created', 'success')
      }
      setOpen(false)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const setDefault = async (shift: Shift) => {
    try {
      await orgApi.updateShift(shift.id, { is_default: true })
      toast(`${shift.name} is now the default shift`, 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Update failed', 'error')
    }
  }

  const remove = async (shift: Shift) => {
    if (!confirm(`Delete shift "${shift.name}"? Assigned people will move to the default shift.`)) return
    try {
      await orgApi.deleteShift(shift.id)
      toast('Shift deleted', 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Delete failed', 'error')
    }
  }

  if (loading) return <Loading label="Loading shifts..." />

  const lateAfterPreview = fromMinutes(toMinutes(form.start_time) + (Number(form.grace_minutes) || 0))

  return (
    <div>
      <SettingsPageHeader
        title="Shifts & grace"
        description="Working hours plus how many minutes someone can be late, leave early, or stay after end before overtime starts."
        action={
          <button type="button" onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
            Add shift
          </button>
        }
      />

      {shifts.length === 0 ? (
        <EmptyState
          title="No shifts yet"
          description="Add a shift such as Morning 09:00–18:00 with a late grace, then assign it on the people page."
          action={
            <button type="button" onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Add shift
            </button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">Shift</th>
                <th className="px-5 py-3">Hours</th>
                <th className="px-5 py-3">Late grace</th>
                <th className="px-5 py-3">Early leave</th>
                <th className="px-5 py-3">Overtime</th>
                <th className="px-5 py-3">People</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {shifts.map((shift) => {
                const grace = graceFromShift(shift)
                return (
                  <tr key={shift.id} className="border-t border-border/70">
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{shift.name}</span>
                        {shift.is_default && <Badge label="Default" tone="trained" />}
                        {shift.kind && shift.kind !== 'fixed' && <Badge label={shift.kind} tone="enrolled" />}
                        {shift.end_time <= shift.start_time && <Badge label="Overnight" tone="enrolled" />}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-muted">
                      {toTimeInput(shift.start_time)} – {toTimeInput(shift.end_time)}
                    </td>
                    <td className="px-5 py-4">
                      <span className="font-medium">{grace} min</span>
                      <p className="text-xs text-muted">Late after {toTimeInput(shift.late_after)}</p>
                    </td>
                    <td className="px-5 py-4 text-muted">{shift.early_leave_grace_minutes ?? 15} min</td>
                    <td className="px-5 py-4 text-muted">{shift.overtime_grace_minutes ?? 15} min</td>
                    <td className="px-5 py-4">{shift.employee_count ?? 0}</td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => openEdit(shift)}
                          className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                        >
                          Edit
                        </button>
                        {!shift.is_default && (
                          <button
                            type="button"
                            onClick={() => setDefault(shift)}
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                          >
                            Make default
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => remove(shift)}
                          className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300 hover:bg-red-950/30"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? 'Edit shift' : 'Add shift'} wide>
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name">
              <input
                required
                placeholder="Morning, Evening, Night..."
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="field"
              />
            </Field>
            <Field label="Type">
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className="field">
                <option value="fixed">Fixed hours</option>
                <option value="flexible">Flexible (required hours)</option>
                <option value="night">Night / overnight</option>
                <option value="split">Split shift</option>
              </select>
            </Field>
            <Field label="Branch">
              <select value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })} className="field">
                <option value="">All branches</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <SettingsSection title="Working hours" description="Start and end of the shift. Overnight shifts can end earlier than they start.">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Start">
                <input
                  required
                  type="time"
                  value={form.start_time}
                  onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                  className="field"
                />
              </Field>
              <Field label="End">
                <input
                  required
                  type="time"
                  value={form.end_time}
                  onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                  className="field"
                />
              </Field>
            </div>
            {form.kind === 'flexible' ? (
              <Field className="mt-4" label="Required hours">
                <input
                  type="number"
                  min="1"
                  step="0.5"
                  value={form.required_hours}
                  onChange={(e) => setForm({ ...form, required_hours: e.target.value })}
                  className="field"
                />
              </Field>
            ) : null}
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="Break start">
                <input type="time" value={form.break_start} onChange={(e) => setForm({ ...form, break_start: e.target.value })} className="field" />
              </Field>
              <Field label="Break end">
                <input type="time" value={form.break_end} onChange={(e) => setForm({ ...form, break_end: e.target.value })} className="field" />
              </Field>
            </div>
            {form.kind === 'split' ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <Field label="Second start">
                  <input type="time" value={form.second_start} onChange={(e) => setForm({ ...form, second_start: e.target.value })} className="field" />
                </Field>
                <Field label="Second end">
                  <input type="time" value={form.second_end} onChange={(e) => setForm({ ...form, second_end: e.target.value })} className="field" />
                </Field>
              </div>
            ) : null}
          </SettingsSection>

          <SettingsSection
            title="Grace periods"
            description="How long after start is still on time, how early someone can leave, and when overtime begins."
          >
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Late grace (minutes)" hint={`Check-in after ${lateAfterPreview} is late.`}>
                <input
                  type="number"
                  min="0"
                  value={form.grace_minutes}
                  onChange={(e) => setForm({ ...form, grace_minutes: e.target.value })}
                  className="field"
                />
              </Field>
              <Field label="Early leave grace" hint={`Leaving more than this before ${toTimeInput(form.end_time)} is early leave.`}>
                <input
                  type="number"
                  min="0"
                  value={form.early_leave_grace_minutes}
                  onChange={(e) => setForm({ ...form, early_leave_grace_minutes: e.target.value })}
                  className="field"
                />
              </Field>
              <Field label="Overtime grace" hint={`Overtime starts this many minutes after ${toTimeInput(form.end_time)}.`}>
                <input
                  type="number"
                  min="0"
                  value={form.overtime_grace_minutes}
                  onChange={(e) => setForm({ ...form, overtime_grace_minutes: e.target.value })}
                  className="field"
                />
              </Field>
            </div>
            <p className="mt-4 rounded-xl border border-border bg-surface/60 px-4 py-3 text-sm leading-6 text-slate-300">
              On time until <span className="font-medium text-white">{lateAfterPreview}</span>. Early leave after
              using {form.early_leave_grace_minutes || 0} min before end. Overtime after{' '}
              {form.overtime_grace_minutes || 0} min past end. Salary cuts for late / absent / early leave are set
              under Payroll & deductions.
            </p>
          </SettingsSection>

          <Toggle
            label="Default shift for new people"
            hint="New employees get this shift until you assign another."
            checked={form.is_default}
            onChange={(v) => setForm({ ...form, is_default: v })}
          />

          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Saving...' : editing ? 'Update shift' : 'Create shift'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

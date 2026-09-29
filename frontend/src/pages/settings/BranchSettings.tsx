import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { orgApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import { Badge } from '../../components/Badge'
import { EmptyState, Loading, Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { Branch, Membership } from '../../types'
import { SettingsPageHeader } from './SettingsUI'

const DAYS = [
  { n: 0, label: 'Mon' },
  { n: 1, label: 'Tue' },
  { n: 2, label: 'Wed' },
  { n: 3, label: 'Thu' },
  { n: 4, label: 'Fri' },
  { n: 5, label: 'Sat' },
  { n: 6, label: 'Sun' },
]

const emptyForm = {
  name: '',
  code: '',
  address: '',
  latitude: '',
  longitude: '',
  geofence_radius_m: '',
  timezone: 'Asia/Karachi',
  weekend_days: [5, 6] as number[],
  manager: '' as string | number,
  is_default: false,
  is_active: true,
}

export default function BranchSettingsPage() {
  const { labels, organization } = useAuth()
  const { toast } = useToast()
  const [branches, setBranches] = useState<Branch[]>([])
  const [members, setMembers] = useState<Membership[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Branch | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const noun = labels.branch
  const limit = organization?.limits.branches

  const load = useCallback(async () => {
    try {
      const [rows, staff] = await Promise.all([orgApi.branches(), orgApi.members().catch(() => [])])
      setBranches(rows)
      setMembers(staff)
    } catch (err) {
      toast(err instanceof Error ? err.message : `Failed to load ${noun.toLowerCase()}s`, 'error')
    } finally {
      setLoading(false)
    }
  }, [noun, toast])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm({
      ...emptyForm,
      timezone: organization?.timezone || 'Asia/Karachi',
      weekend_days: organization?.weekend_days?.length ? organization.weekend_days : [5, 6],
      is_default: branches.length === 0,
    })
    setOpen(true)
  }

  const openEdit = (branch: Branch) => {
    setEditing(branch)
    setForm({
      name: branch.name,
      code: branch.code || '',
      address: branch.address || '',
      latitude: branch.latitude == null ? '' : String(branch.latitude),
      longitude: branch.longitude == null ? '' : String(branch.longitude),
      geofence_radius_m: branch.geofence_radius_m == null ? '' : String(branch.geofence_radius_m),
      timezone: branch.timezone || 'Asia/Karachi',
      weekend_days: branch.weekend_days?.length ? branch.weekend_days : [5, 6],
      manager: branch.manager ?? '',
      is_default: branch.is_default,
      is_active: branch.is_active,
    })
    setOpen(true)
  }

  const payload = () => ({
    name: form.name.trim(),
    code: form.code.trim(),
    address: form.address.trim(),
    latitude: form.latitude === '' ? null : Number(form.latitude),
    longitude: form.longitude === '' ? null : Number(form.longitude),
    geofence_radius_m: form.geofence_radius_m === '' ? null : Number(form.geofence_radius_m),
    timezone: form.timezone.trim() || 'Asia/Karachi',
    weekend_days: form.weekend_days,
    manager: form.manager === '' ? null : Number(form.manager),
    is_default: form.is_default,
    is_active: form.is_active,
  })

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        await orgApi.updateBranch(editing.id, payload())
        toast(`${noun} updated`, 'success')
      } else {
        await orgApi.createBranch(payload())
        toast(`${noun} created`, 'success')
      }
      setOpen(false)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (branch: Branch) => {
    if (!confirm(`Delete ${noun.toLowerCase()} "${branch.name}"?`)) return
    try {
      await orgApi.deleteBranch(branch.id)
      toast(`${noun} deleted`, 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Delete failed', 'error')
    }
  }

  if (loading) return <Loading />

  return (
    <div className="space-y-4">
      <SettingsPageHeader
        title={labels.branches}
        description={`${branches.length} ${noun.toLowerCase()}${typeof limit === 'number' ? ` · plan allows ${limit}` : ''}. Locations, weekends, and mobile punch geofence.`}
        action={
          <button type="button" onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
            Add {noun.toLowerCase()}
          </button>
        }
      />

      {branches.length === 0 ? (
        <EmptyState
          title={`No ${noun.toLowerCase()}s`}
          description="Add offices or campuses so people, cameras, and holidays can be scoped by location."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Timezone</th>
                <th className="px-5 py-3">Weekend</th>
                <th className="px-5 py-3">People</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {branches.map((branch) => (
                <tr key={branch.id} className="border-t border-border/70">
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{branch.name}</span>
                      {branch.is_default && <Badge label="Default" tone="trained" />}
                      {!branch.is_active && <Badge label="Inactive" tone="inactive" />}
                    </div>
                    <p className="text-xs text-muted">{branch.address || branch.code || '—'}</p>
                  </td>
                  <td className="px-5 py-4 text-muted">{branch.timezone}</td>
                  <td className="px-5 py-4 text-muted">
                    {(branch.weekend_days || [])
                      .map((n) => DAYS.find((d) => d.n === n)?.label)
                      .filter(Boolean)
                      .join(', ') || '—'}
                  </td>
                  <td className="px-5 py-4">{branch.employee_count ?? 0}</td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openEdit(branch)}
                        className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => remove(branch)}
                        className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300 hover:bg-red-950/30"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? `Edit ${noun}` : `Add ${noun}`}>
        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Name</span>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="field" />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Code</span>
              <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Timezone</span>
              <input required value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} className="field" />
            </label>
          </div>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Address</span>
            <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="field" />
          </label>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Latitude</span>
              <input value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Longitude</span>
              <input value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} className="field" />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Geofence (m)</span>
              <input
                value={form.geofence_radius_m}
                onChange={(e) => setForm({ ...form, geofence_radius_m: e.target.value })}
                className="field"
              />
              <span className="text-xs text-muted">
                Mobile camera punch is rejected if the phone is farther than this from the coordinates.
              </span>
            </label>
          </div>
          <div>
            <p className="mb-2 text-sm text-muted">Weekend</p>
            <div className="flex flex-wrap gap-2">
              {DAYS.map((d) => {
                const on = form.weekend_days.includes(d.n)
                return (
                  <button
                    key={d.n}
                    type="button"
                    onClick={() =>
                      setForm((prev) => ({
                        ...prev,
                        weekend_days: on
                          ? prev.weekend_days.filter((n) => n !== d.n)
                          : [...prev.weekend_days, d.n].sort(),
                      }))
                    }
                    className={`rounded-lg px-3 py-1.5 text-sm ${on ? 'bg-accent text-white' : 'border border-border text-muted'}`}
                  >
                    {d.label}
                  </button>
                )
              })}
            </div>
          </div>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Manager</span>
            <select
              value={form.manager}
              onChange={(e) => setForm({ ...form, manager: e.target.value })}
              className="field"
            >
              <option value="">None</option>
              {members.map((m) => (
                <option key={m.id} value={m.user_id ?? m.id}>
                  {m.email || m.username} ({m.role})
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
            />
            Default {noun.toLowerCase()}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Active
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Saving...' : editing ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

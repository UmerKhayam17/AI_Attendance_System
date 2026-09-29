import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { orgApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import { Badge } from '../../components/Badge'
import { EmptyState, Loading, Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { Branch, Department } from '../../types'
import { Field, SettingsPageHeader } from './SettingsUI'

const emptyForm = {
  name: '',
  branch: '' as string | number,
  is_active: true,
  sort_order: 0,
}

export function DepartmentManager() {
  const { labels } = useAuth()
  const { toast } = useToast()
  const [departments, setDepartments] = useState<Department[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Department | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const noun = labels.department

  const load = useCallback(async () => {
    try {
      const [rows, orgBranches] = await Promise.all([orgApi.departments(), orgApi.branches()])
      setDepartments(rows)
      setBranches(orgBranches)
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
    setForm({ ...emptyForm, sort_order: departments.length, branch: branches.find((b) => b.is_default)?.id ?? branches[0]?.id ?? '' })
    setOpen(true)
  }

  const openEdit = (dept: Department) => {
    setEditing(dept)
    setForm({
      name: dept.name,
      branch: dept.branch ?? '',
      is_active: dept.is_active,
      sort_order: dept.sort_order,
    })
    setOpen(true)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(),
        branch: form.branch === '' ? null : Number(form.branch),
        is_active: form.is_active,
        sort_order: Number(form.sort_order) || 0,
      }
      if (editing) {
        await orgApi.updateDepartment(editing.id, payload)
        toast(`${noun} updated`, 'success')
      } else {
        await orgApi.createDepartment(payload)
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

  const toggleActive = async (dept: Department) => {
    try {
      await orgApi.updateDepartment(dept.id, { is_active: !dept.is_active })
      toast(`${dept.name} ${dept.is_active ? 'hidden from new assignments' : 'is active again'}`, 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Update failed', 'error')
    }
  }

  const remove = async (dept: Department) => {
    if (!confirm(`Delete ${noun.toLowerCase()} "${dept.name}"? Reassign people first if anyone is still assigned.`)) {
      return
    }
    try {
      await orgApi.deleteDepartment(dept.id)
      toast(`${noun} deleted`, 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Delete failed', 'error')
    }
  }

  if (loading) return <Loading label={`Loading ${noun.toLowerCase()}s...`} />

  return (
    <div>
      <SettingsPageHeader
        title={`${noun} catalog`}
        description={`Manage ${noun.toLowerCase()}s here, then assign one to each person on the people page.`}
        action={
          <button type="button" onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
            Add {noun.toLowerCase()}
          </button>
        }
      />

      {departments.length === 0 ? (
        <EmptyState
          title={`No ${noun.toLowerCase()}s yet`}
          description={`Add ${noun.toLowerCase()}s such as Engineering or Grade 1, then assign them when registering people.`}
          action={
            <button type="button" onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
              Add {noun.toLowerCase()}
            </button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">{noun}</th>
                <th className="px-5 py-3">{labels.branch}</th>
                <th className="px-5 py-3">People</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {departments.map((dept) => (
                <tr key={dept.id} className="border-t border-border/70">
                  <td className="px-5 py-4 font-medium">{dept.name}</td>
                  <td className="px-5 py-4 text-muted">{dept.branch_name || '—'}</td>
                  <td className="px-5 py-4">{dept.employee_count ?? 0}</td>
                  <td className="px-5 py-4">
                    <Badge label={dept.is_active ? 'Active' : 'Inactive'} tone={dept.is_active ? 'active' : 'inactive'} />
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openEdit(dept)}
                        className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleActive(dept)}
                        className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                      >
                        {dept.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        type="button"
                        onClick={() => remove(dept)}
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

      <p className="text-xs text-muted">
        Assign {noun.toLowerCase()}s on the{' '}
        <Link to="/employees" className="text-accent hover:underline">
          people
        </Link>{' '}
        page.
      </p>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? `Edit ${noun}` : `Add ${noun}`}>
        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="Name">
            <input
              required
              placeholder={noun === 'Class / Section' ? 'Grade 1-A, Grade 2-B...' : 'Engineering, Sales, HR...'}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="field"
            />
          </Field>
          <Field label={labels.branch}>
            <select
              value={form.branch}
              onChange={(e) => setForm({ ...form, branch: e.target.value })}
              className="field"
            >
              <option value="">Default {labels.branch.toLowerCase()}</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
            </select>
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Available when registering people
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Saving...' : editing ? `Update ${noun.toLowerCase()}` : `Create ${noun.toLowerCase()}`}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

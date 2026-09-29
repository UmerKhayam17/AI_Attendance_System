import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { employeeApi, orgApi } from '../api/services'
import { mediaUrl } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { CompensationModal } from '../components/CompensationModal'
import { EmptyState, Loading, Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { Branch, Department, Employee, EmployeeDocument, EmployeeFormData, Shift, ShiftAssignment } from '../types'

const emptyForm: EmployeeFormData = {
  employee_id: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  national_id: '',
  date_of_birth: '',
  gender: '',
  address: '',
  guardian_name: '',
  guardian_phone: '',
  guardian_email: '',
  branch: null,
  department: null,
  designation: '',
  employment_type: 'full_time',
  joining_date: '',
  manager: null,
  shift: null,
  is_active: true,
}

export default function EmployeesPage() {
  const { labels } = useAuth()
  const { toast } = useToast()
  const [employees, setEmployees] = useState<Employee[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [branchFilter, setBranchFilter] = useState('all')
  const [departmentFilter, setDepartmentFilter] = useState('all')
  const [shiftFilter, setShiftFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Employee | null>(null)
  const [form, setForm] = useState<EmployeeFormData>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [inviteOpen, setInviteOpen] = useState<Employee | null>(null)
  const [inviteRole, setInviteRole] = useState<'employee' | 'parent'>('employee')
  const [inviteEmail, setInviteEmail] = useState('')
  const [payEmployee, setPayEmployee] = useState<Employee | null>(null)

  const load = useCallback(async () => {
    try {
      const [people, orgShifts, orgDepartments, orgBranches] = await Promise.all([
        employeeApi.list(),
        orgApi.shifts(),
        orgApi.departments(),
        orgApi.branches(),
      ])
      setEmployees(people)
      setShifts(orgShifts)
      setDepartments(orgDepartments)
      setBranches(orgBranches)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load employees', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const activeDepartments = useMemo(
    () => departments.filter((dept) => dept.is_active || (editing && editing.department === dept.id)),
    [departments, editing],
  )

  const filtered = useMemo(() => {
    return employees.filter((emp) => {
      const q = search.toLowerCase()
      const matchesSearch =
        !q ||
        emp.employee_id.toLowerCase().includes(q) ||
        emp.first_name.toLowerCase().includes(q) ||
        emp.last_name.toLowerCase().includes(q) ||
        emp.email.toLowerCase().includes(q) ||
        (emp.department_name || '').toLowerCase().includes(q)

      const matchesBranch =
        branchFilter === 'all' ||
        (branchFilter === 'unassigned' && !emp.branch) ||
        String(emp.branch) === branchFilter
      const matchesDept =
        departmentFilter === 'all' ||
        (departmentFilter === 'unassigned' && !emp.department) ||
        String(emp.department) === departmentFilter
      const matchesShift =
        shiftFilter === 'all' ||
        (shiftFilter === 'unassigned' && !emp.shift) ||
        String(emp.shift) === shiftFilter
      const matchesType = typeFilter === 'all' || emp.employment_type === typeFilter
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'active' && emp.is_active) ||
        (statusFilter === 'inactive' && !emp.is_active)

      return matchesSearch && matchesBranch && matchesDept && matchesShift && matchesType && matchesStatus
    })
  }, [employees, search, branchFilter, departmentFilter, shiftFilter, typeFilter, statusFilter])

  const openCreate = () => {
    setEditing(null)
    const defaultShift = shifts.find((s) => s.is_default) || shifts[0]
    const defaultBranch = branches.find((b) => b.is_default) || branches[0]
    setForm({ ...emptyForm, shift: defaultShift?.id ?? null, branch: defaultBranch?.id ?? null })
    setModalOpen(true)
  }

  const openEdit = (employee: Employee) => {
    setEditing(employee)
    setForm({
      employee_id: employee.employee_id,
      first_name: employee.first_name,
      last_name: employee.last_name,
      email: employee.email,
      phone: employee.phone,
      national_id: employee.national_id || '',
      date_of_birth: employee.date_of_birth || '',
      gender: employee.gender || '',
      address: employee.address || '',
      guardian_name: employee.guardian_name || '',
      guardian_phone: employee.guardian_phone || '',
      guardian_email: employee.guardian_email || '',
      branch: employee.branch ?? null,
      department: employee.department,
      designation: employee.designation,
      employment_type: employee.employment_type || 'full_time',
      joining_date: employee.joining_date || '',
      manager: employee.manager ?? null,
      shift: employee.shift,
      is_active: employee.is_active,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        const { employee_id: _id, ...patchData } = form
        await employeeApi.update(editing.employee_id, {
          ...patchData,
          date_of_birth: patchData.date_of_birth || undefined,
          joining_date: patchData.joining_date || undefined,
        })
        toast(`${labels.person} updated`, 'success')
      } else {
        await employeeApi.create({
          ...form,
          date_of_birth: form.date_of_birth || undefined,
          joining_date: form.joining_date || undefined,
        })
        toast(`${labels.person} registered`, 'success')
      }
      setModalOpen(false)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (employee: Employee) => {
    try {
      if (employee.is_active) {
        await employeeApi.deactivate(employee.employee_id)
        toast(`${employee.first_name} deactivated`, 'info')
      } else {
        await employeeApi.activate(employee.employee_id)
        toast(`${employee.first_name} activated`, 'success')
      }
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Action failed', 'error')
    }
  }

  const handleDelete = async (employee: Employee) => {
    if (!confirm(`Delete ${labels.person.toLowerCase()} ${employee.employee_id}?`)) return
    try {
      await employeeApi.remove(employee.employee_id)
      toast(`${labels.person} deleted`, 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Delete failed', 'error')
    }
  }

  if (loading) return <Loading />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">{labels.peopleNav}</h2>
          <p className="text-sm text-muted">{employees.length} registered</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/salaries"
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-surface"
          >
            Salaries
          </Link>
          <button
            type="button"
            onClick={openCreate}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            + Register {labels.person}
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={`Search name, ID, email, ${labels.department.toLowerCase()}...`}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <select
          value={branchFilter}
          onChange={(e) => setBranchFilter(e.target.value)}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        >
          <option value="all">All {labels.branches.toLowerCase()}</option>
          {branches.map((branch) => (
            <option key={branch.id} value={String(branch.id)}>
              {branch.name}
            </option>
          ))}
        </select>
        <select
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value)}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        >
          <option value="all">All {labels.department.toLowerCase()}s</option>
          {departments.map((dept) => (
            <option key={dept.id} value={String(dept.id)}>
              {dept.name}
            </option>
          ))}
          <option value="unassigned">Unassigned</option>
        </select>
        <select
          value={shiftFilter}
          onChange={(e) => setShiftFilter(e.target.value)}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        >
          <option value="all">All shifts</option>
          {shifts.map((shift) => (
            <option key={shift.id} value={String(shift.id)}>
              {shift.name}
            </option>
          ))}
          <option value="unassigned">Unassigned</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        >
          <option value="all">All types</option>
          <option value="full_time">Full-time</option>
          <option value="part_time">Part-time</option>
          <option value="contract">Contract</option>
          <option value="intern">Intern</option>
          <option value="temporary">Temporary</option>
          <option value="remote">Remote</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        >
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title={`No ${labels.people.toLowerCase()} found`}
          description={`Register your first ${labels.person.toLowerCase()} to start face enrollment and attendance tracking.`}
          action={
            <button
              type="button"
              onClick={openCreate}
              className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
            >
              Register {labels.person}
            </button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-surface/60 text-left text-muted">
                <tr>
                  <th className="px-5 py-3">{labels.person}</th>
                  <th className="px-5 py-3">{labels.branch}</th>
                  <th className="px-5 py-3">{labels.department}</th>
                  <th className="px-5 py-3">Shift</th>
                  <th className="px-5 py-3">Face Status</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((employee) => {
                  const enrollment = employee.face_enrollment
                  const profile = mediaUrl(enrollment?.profile_image)
                  return (
                    <tr key={employee.id} className="border-t border-border/70">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 overflow-hidden rounded-full bg-surface">
                            {profile ? (
                              <img src={profile} alt="" className="h-full w-full object-cover" />
                            ) : (
                              <div className="flex h-full w-full items-center justify-center text-xs text-muted">
                                {employee.first_name[0]}
                              </div>
                            )}
                          </div>
                          <div>
                            <p className="font-medium">
                              {employee.first_name} {employee.last_name}
                            </p>
                            <p className="text-xs text-muted">
                              {employee.employee_id} · {employee.email}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-muted">{employee.branch_name || '—'}</td>
                      <td className="px-5 py-4">
                        <p>{employee.department_name || 'Unassigned'}</p>
                        <p className="text-xs text-muted">{employee.designation}</p>
                      </td>
                      <td className="px-5 py-4">
                        {employee.shift_detail ? (
                          <div>
                            <p>{employee.shift_detail.name}</p>
                            <p className="text-xs text-muted">
                              {employee.shift_detail.start_time.slice(0, 5)} – {employee.shift_detail.end_time.slice(0, 5)}
                            </p>
                          </div>
                        ) : (
                          <span className="text-muted">Unassigned</span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          {enrollment?.is_trained ? (
                            <Badge label="Trained" tone="trained" />
                          ) : enrollment?.is_enrolled ? (
                            <Badge label="Enrolled" tone="enrolled" />
                          ) : (
                            <Badge label="Pending" tone="pending" />
                          )}
                          <span className="text-xs text-muted">
                            {enrollment?.total_images ?? 0} images
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <Badge
                          label={employee.is_active ? 'Active' : 'Inactive'}
                          tone={employee.is_active ? 'active' : 'inactive'}
                        />
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          <Link
                            to={`/enrollment?employee=${employee.employee_id}`}
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                          >
                            Enroll
                          </Link>
                          <button
                            type="button"
                            onClick={() => {
                              setInviteOpen(employee)
                              setInviteRole('employee')
                              setInviteEmail(employee.email)
                            }}
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                          >
                            Portal invite
                          </button>
                          <Link
                            to={`/exits?employee=${employee.employee_id}`}
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                          >
                            Start exit
                          </Link>
                          <button
                            type="button"
                            onClick={() => setPayEmployee(employee)}
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                          >
                            Salary
                          </button>
                          <button
                            type="button"
                            onClick={() => openEdit(employee)}
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleActive(employee)}
                            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                          >
                            {employee.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(employee)}
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
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? `Edit ${labels.person}` : `Register ${labels.person}`}
        wide
      >
        <form onSubmit={handleSubmit} className="space-y-6">
          <section className="grid gap-4 md:grid-cols-2">
            <p className="md:col-span-2 text-xs font-medium uppercase tracking-wide text-muted">Personal</p>
            <Field label={labels.id}>
              <input required disabled={!!editing} value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} className="field" />
            </Field>
            <Field label="Email">
              <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="field" />
            </Field>
            <Field label="First Name">
              <input required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="field" />
            </Field>
            <Field label="Last Name">
              <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="field" />
            </Field>
            <Field label="Phone">
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="field" />
            </Field>
            <Field label="CNIC / National ID">
              <input value={form.national_id || ''} onChange={(e) => setForm({ ...form, national_id: e.target.value })} className="field" />
            </Field>
            <Field label="Date of birth">
              <input type="date" value={form.date_of_birth || ''} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} className="field" />
            </Field>
            <Field label="Gender">
              <select value={form.gender || ''} onChange={(e) => setForm({ ...form, gender: e.target.value as EmployeeFormData['gender'] })} className="field">
                <option value="">Unspecified</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <Field label="Address">
              <input value={form.address || ''} onChange={(e) => setForm({ ...form, address: e.target.value })} className="field" />
            </Field>
            <Field label="Guardian name">
              <input value={form.guardian_name || ''} onChange={(e) => setForm({ ...form, guardian_name: e.target.value })} className="field" />
            </Field>
            <Field label="Guardian phone">
              <input value={form.guardian_phone || ''} onChange={(e) => setForm({ ...form, guardian_phone: e.target.value })} className="field" />
            </Field>
            <Field label="Guardian email">
              <input type="email" value={form.guardian_email || ''} onChange={(e) => setForm({ ...form, guardian_email: e.target.value })} className="field" />
            </Field>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <p className="md:col-span-2 text-xs font-medium uppercase tracking-wide text-muted">Employment</p>
            <Field label={labels.branch}>
              <select value={form.branch ?? ''} onChange={(e) => setForm({ ...form, branch: e.target.value ? Number(e.target.value) : null, department: null })} className="field">
                <option value="">Default {labels.branch.toLowerCase()}</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>{branch.name}</option>
                ))}
              </select>
            </Field>
            <Field label={labels.department}>
              <select
                required={activeDepartments.filter((d) => !form.branch || !d.branch || d.branch === form.branch).length > 0}
                value={form.department ?? ''}
                onChange={(e) => setForm({ ...form, department: e.target.value ? Number(e.target.value) : null })}
                className="field"
              >
                <option value="">Unassigned</option>
                {activeDepartments.filter((d) => !form.branch || !d.branch || d.branch === form.branch).map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.name}{dept.is_active ? '' : ' (inactive)'}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={labels.designation}>
              <input required value={form.designation} onChange={(e) => setForm({ ...form, designation: e.target.value })} className="field" />
            </Field>
            <Field label="Employment type">
              <select value={form.employment_type || 'full_time'} onChange={(e) => setForm({ ...form, employment_type: e.target.value as EmployeeFormData['employment_type'] })} className="field">
                <option value="full_time">Full-time</option>
                <option value="part_time">Part-time</option>
                <option value="contract">Contract</option>
                <option value="intern">Intern</option>
                <option value="temporary">Temporary</option>
                <option value="remote">Remote</option>
              </select>
            </Field>
            <Field label="Joining date">
              <input type="date" value={form.joining_date || ''} onChange={(e) => setForm({ ...form, joining_date: e.target.value })} className="field" />
            </Field>
            <Field label="Manager">
              <select value={form.manager ?? ''} onChange={(e) => setForm({ ...form, manager: e.target.value ? Number(e.target.value) : null })} className="field">
                <option value="">None</option>
                {employees.filter((e) => !editing || e.id !== editing.id).map((emp) => (
                  <option key={emp.id} value={emp.id}>{emp.first_name} {emp.last_name} ({emp.employee_id})</option>
                ))}
              </select>
            </Field>
            <Field label="Status">
              <select value={form.is_active ? 'active' : 'inactive'} onChange={(e) => setForm({ ...form, is_active: e.target.value === 'active' })} className="field">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </Field>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <p className="md:col-span-2 text-xs font-medium uppercase tracking-wide text-muted">Attendance</p>
            <Field label="Shift">
              <select value={form.shift ?? ''} onChange={(e) => setForm({ ...form, shift: e.target.value ? Number(e.target.value) : null })} className="field">
                <option value="">Default shift</option>
                {shifts.filter((s) => !form.branch || !s.branch || s.branch === form.branch).map((shift) => (
                  <option key={shift.id} value={shift.id}>
                    {shift.name} ({shift.start_time.slice(0, 5)}–{shift.end_time.slice(0, 5)}{shift.is_default ? ', default' : ''})
                  </option>
                ))}
              </select>
            </Field>
          </section>

          {editing ? <EmployeeExtras employee={editing} shifts={shifts} onChanged={load} /> : null}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setModalOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
              {saving ? 'Saving...' : editing ? `Update ${labels.person}` : `Register ${labels.person}`}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={!!inviteOpen}
        onClose={() => setInviteOpen(null)}
        title={`Portal invite${inviteOpen ? ` · ${inviteOpen.first_name}` : ''}`}
      >
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault()
            if (!inviteOpen) return
            setSaving(true)
            try {
              const invite = await employeeApi.invitePortal(inviteOpen.employee_id, {
                role: inviteRole,
                email: inviteEmail,
              })
              await navigator.clipboard?.writeText(invite.invite_url).catch(() => undefined)
              toast('Invite created — link copied', 'success')
              setInviteOpen(null)
            } catch (err) {
              toast(err instanceof Error ? err.message : 'Invite failed', 'error')
            } finally {
              setSaving(false)
            }
          }}
        >
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Role</span>
            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as 'employee' | 'parent')} className="field">
              <option value="employee">Self-service ({labels.person.toLowerCase()})</option>
              <option value="parent">Parent / guardian</option>
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Email</span>
            <input required type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} className="field" />
          </label>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setInviteOpen(null)} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Inviting...' : 'Create invite'}
            </button>
          </div>
        </form>
      </Modal>

      <CompensationModal employee={payEmployee} onClose={() => setPayEmployee(null)} />
    </div>
  )
}

function EmployeeExtras({
  employee,
  shifts,
  onChanged,
}: {
  employee: Employee
  shifts: Shift[]
  onChanged: () => void
}) {
  const { toast } = useToast()
  const [docs, setDocs] = useState<EmployeeDocument[]>([])
  const [assignments, setAssignments] = useState<ShiftAssignment[]>([])
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('other')
  const [file, setFile] = useState<File | null>(null)
  const [shiftId, setShiftId] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  const reload = useCallback(async () => {
    try {
      const [d, a] = await Promise.all([
        employeeApi.documents(employee.employee_id),
        employeeApi.shiftAssignments(employee.employee_id),
      ])
      setDocs(d)
      setAssignments(a)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load extras', 'error')
    }
  }, [employee.employee_id, toast])

  useEffect(() => {
    reload()
  }, [reload])

  return (
    <div className="space-y-4 md:col-span-2">
      <section className="space-y-3 rounded-lg border border-border p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">Documents</p>
        {docs.map((doc) => (
          <div key={doc.id} className="flex items-center justify-between gap-2 text-sm">
            <a href={doc.file_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
              {doc.title} ({doc.category})
            </a>
            <button
              type="button"
              className="text-xs text-red-300"
              onClick={async () => {
                await employeeApi.deleteDocument(employee.employee_id, doc.id)
                await reload()
                onChanged()
              }}
            >
              Delete
            </button>
          </div>
        ))}
        <div className="grid gap-2 md:grid-cols-[1fr_140px_1fr_auto]">
          <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} className="field" />
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="field">
            <option value="contract">Contract</option>
            <option value="id">ID</option>
            <option value="certificate">Certificate</option>
            <option value="other">Other</option>
          </select>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="field" />
          <button
            type="button"
            className="rounded-lg border border-border px-3 py-2 text-sm"
            onClick={async () => {
              if (!file || !title.trim()) return
              const data = new FormData()
              data.append('title', title.trim())
              data.append('category', category)
              data.append('file', file)
              await employeeApi.uploadDocument(employee.employee_id, data)
              setTitle('')
              setFile(null)
              await reload()
              onChanged()
            }}
          >
            Upload
          </button>
        </div>
      </section>
      <section className="space-y-3 rounded-lg border border-border p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">Shift overrides</p>
        {assignments.map((row) => (
          <div key={row.id} className="flex items-center justify-between gap-2 text-sm">
            <span>
              {row.shift_name}: {row.start_date}
              {row.end_date ? ` → ${row.end_date}` : ' onward'}
            </span>
            <button
              type="button"
              className="text-xs text-red-300"
              onClick={async () => {
                await employeeApi.deleteShiftAssignment(employee.employee_id, row.id)
                await reload()
              }}
            >
              Remove
            </button>
          </div>
        ))}
        <div className="grid gap-2 md:grid-cols-[1fr_140px_140px_auto]">
          <select value={shiftId} onChange={(e) => setShiftId(e.target.value)} className="field">
            <option value="">Shift</option>
            {shifts.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="field" />
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="field" />
          <button
            type="button"
            className="rounded-lg border border-border px-3 py-2 text-sm"
            onClick={async () => {
              if (!shiftId || !start) return
              await employeeApi.createShiftAssignment(employee.employee_id, {
                shift: Number(shiftId),
                start_date: start,
                end_date: end || null,
              })
              setShiftId('')
              setStart('')
              setEnd('')
              await reload()
            }}
          >
            Add
          </button>
        </div>
      </section>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5 text-sm">
      <span className="text-muted">{label}</span>
      {children}
    </label>
  )
}

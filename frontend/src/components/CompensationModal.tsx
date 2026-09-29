import { type FormEvent, useEffect, useState } from 'react'
import { payrollApi } from '../api/services'
import { Modal } from './Modal'
import { useToast } from './Toast'
import type { EmployeeCompensation } from '../types'

const empty: Omit<EmployeeCompensation, 'employee_id' | 'employee_name' | 'updated_at'> = {
  pay_type: 'monthly',
  basic_salary: '0',
  housing_allowance: '0',
  transport_allowance: '0',
  medical_allowance: '0',
  other_allowance: '0',
  other_deduction: '0',
  hire_date: '',
  bank_name: '',
  account_title: '',
  account_number: '',
  notes: '',
}

export function CompensationModal({
  employee,
  onClose,
  onSaved,
}: {
  employee: { employee_id: string; first_name: string; last_name?: string } | null
  onClose: () => void
  onSaved?: () => void
}) {
  const { toast } = useToast()
  const [form, setForm] = useState(empty)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!employee) return
    setLoading(true)
    payrollApi
      .compensation(employee.employee_id)
      .then((data) => {
        setForm({
          pay_type: data.pay_type,
          basic_salary: data.basic_salary,
          housing_allowance: data.housing_allowance,
          transport_allowance: data.transport_allowance,
          medical_allowance: data.medical_allowance,
          other_allowance: data.other_allowance,
          other_deduction: data.other_deduction,
          hire_date: data.hire_date || '',
          bank_name: data.bank_name || '',
          account_title: data.account_title || '',
          account_number: data.account_number || '',
          notes: data.notes || '',
        })
      })
      .catch((err) => toast(err instanceof Error ? err.message : 'Failed to load salary', 'error'))
      .finally(() => setLoading(false))
  }, [employee, toast])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!employee) return
    setSaving(true)
    try {
      await payrollApi.updateCompensation(employee.employee_id, {
        ...form,
        hire_date: form.hire_date || null,
      })
      toast('Salary saved', 'success')
      onSaved?.()
      onClose()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={!!employee}
      onClose={onClose}
      title={employee ? `Salary · ${[employee.first_name, employee.last_name].filter(Boolean).join(' ')}` : 'Salary'}
      wide
    >
      {loading ? (
        <p className="text-sm text-muted">Loading...</p>
      ) : (
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Pay type</span>
            <select
              value={form.pay_type}
              onChange={(e) => setForm({ ...form, pay_type: e.target.value as EmployeeCompensation['pay_type'] })}
              className="field"
            >
              <option value="monthly">Monthly salary</option>
              <option value="daily">Daily wage</option>
              <option value="hourly">Hourly</option>
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Hire date</span>
            <input type="date" value={form.hire_date || ''} onChange={(e) => setForm({ ...form, hire_date: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Basic {form.pay_type === 'monthly' ? 'salary' : form.pay_type === 'daily' ? 'daily wage' : 'hourly rate'}</span>
            <input required type="number" min="0" step="0.01" value={form.basic_salary} onChange={(e) => setForm({ ...form, basic_salary: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Housing allowance</span>
            <input type="number" min="0" step="0.01" value={form.housing_allowance} onChange={(e) => setForm({ ...form, housing_allowance: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Transport allowance</span>
            <input type="number" min="0" step="0.01" value={form.transport_allowance} onChange={(e) => setForm({ ...form, transport_allowance: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Medical allowance</span>
            <input type="number" min="0" step="0.01" value={form.medical_allowance} onChange={(e) => setForm({ ...form, medical_allowance: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Other allowance</span>
            <input type="number" min="0" step="0.01" value={form.other_allowance} onChange={(e) => setForm({ ...form, other_allowance: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Fixed deduction</span>
            <input type="number" min="0" step="0.01" value={form.other_deduction} onChange={(e) => setForm({ ...form, other_deduction: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Bank name</span>
            <input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Account title</span>
            <input value={form.account_title} onChange={(e) => setForm({ ...form, account_title: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm md:col-span-2">
            <span className="text-muted">Account number</span>
            <input value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm md:col-span-2">
            <span className="text-muted">Notes</span>
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="field min-h-16" />
          </label>
          <div className="md:col-span-2 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Saving...' : 'Save salary'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}

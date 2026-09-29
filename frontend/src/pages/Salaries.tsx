import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { payrollApi } from '../api/services'
import { Badge } from '../components/Badge'
import { CompensationModal } from '../components/CompensationModal'
import { EmptyState, Loading } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { EmployeeCompensation } from '../types'

const PAY_LABEL: Record<EmployeeCompensation['pay_type'], string> = {
  monthly: 'Monthly',
  daily: 'Daily',
  hourly: 'Hourly',
}

function money(currency: string, value: string | number) {
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return `${currency} ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function splitName(name: string) {
  const parts = name.trim().split(/\s+/)
  return { first_name: parts[0] || '', last_name: parts.slice(1).join(' ') }
}

export default function SalariesPage() {
  const { toast } = useToast()
  const [rows, setRows] = useState<EmployeeCompensation[]>([])
  const [currency, setCurrency] = useState('PKR')
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'missing' | 'set'>('all')
  const [status, setStatus] = useState<'active' | 'all'>('active')
  const [editing, setEditing] = useState<EmployeeCompensation | null>(null)

  const load = useCallback(async () => {
    try {
      const [list, policy] = await Promise.all([payrollApi.compensations(), payrollApi.policy()])
      setRows(list)
      setCurrency(policy.currency)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load salaries', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim()
    return rows.filter((row) => {
      if (status === 'active' && row.is_active === false) return false
      if (filter === 'missing' && row.salary_set) return false
      if (filter === 'set' && !row.salary_set) return false
      if (!q) return true
      return (
        row.employee_id.toLowerCase().includes(q) ||
        row.employee_name.toLowerCase().includes(q) ||
        (row.department || '').toLowerCase().includes(q) ||
        (row.designation || '').toLowerCase().includes(q)
      )
    })
  }, [rows, search, filter, status])

  const missing = rows.filter((row) => row.is_active !== false && !row.salary_set).length

  if (loading) return <Loading label="Loading salaries..." />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Salaries</h2>
          <p className="text-sm text-muted">
            Set basic pay and allowances for each person. Payroll uses these amounts when you generate payslips.{' '}
            <Link to="/payroll" className="text-accent hover:underline">
              Open payroll
            </Link>
          </p>
        </div>
        {missing > 0 ? (
          <p className="text-sm text-amber-300">
            {missing} active {missing === 1 ? 'person has' : 'people have'} no salary yet
          </p>
        ) : null}
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, ID, department..."
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as typeof filter)}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        >
          <option value="all">All salaries</option>
          <option value="missing">Salary not set</option>
          <option value="set">Salary set</option>
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as typeof status)}
          className="rounded-lg border border-border bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent"
        >
          <option value="active">Active people</option>
          <option value="all">Everyone</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title={rows.length === 0 ? 'No people yet' : 'No matching salaries'}
          description={
            rows.length === 0
              ? 'Register employees first, then come back here to set their pay.'
              : 'Try a different search or filter.'
          }
          action={
            rows.length === 0 ? (
              <Link to="/employees" className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
                Open Employees
              </Link>
            ) : undefined
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">Person</th>
                <th className="px-5 py-3">Pay type</th>
                <th className="px-5 py-3">Basic</th>
                <th className="px-5 py-3">Gross</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.employee_id} className="border-t border-border/70">
                  <td className="px-5 py-4">
                    <p className="font-medium">{row.employee_name}</p>
                    <p className="text-xs text-muted">
                      {row.employee_id}
                      {row.designation ? ` · ${row.designation}` : ''}
                      {row.department ? ` · ${row.department}` : ''}
                    </p>
                  </td>
                  <td className="px-5 py-4">{PAY_LABEL[row.pay_type]}</td>
                  <td className="px-5 py-4">{money(currency, row.basic_salary)}</td>
                  <td className="px-5 py-4">{money(currency, row.gross || row.basic_salary)}</td>
                  <td className="px-5 py-4">
                    <Badge
                      label={row.salary_set ? 'Set' : 'Missing'}
                      tone={row.salary_set ? 'present' : 'pending'}
                    />
                  </td>
                  <td className="px-5 py-4">
                    <button
                      type="button"
                      className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface"
                      onClick={() => setEditing(row)}
                    >
                      {row.salary_set ? 'Edit salary' : 'Set salary'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CompensationModal
        employee={
          editing
            ? { employee_id: editing.employee_id, ...splitName(editing.employee_name) }
            : null
        }
        onClose={() => setEditing(null)}
        onSaved={load}
      />
    </div>
  )
}

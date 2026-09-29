import { useCallback, useEffect, useState } from 'react'
import { approvalApi, orgApi } from '../../api/services'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { ApprovalWorkflow, LeaveType } from '../../types'
import { SettingsPageHeader, SettingsSection } from './SettingsUI'

const KIND_LABEL: Record<string, string> = {
  leave: 'Leave',
  overtime: 'Overtime',
  attendance_correction: 'Attendance correction',
  exit: 'Exit / resignation',
}

const ROLES = [
  { id: 'manager', label: 'Manager' },
  { id: 'admin', label: 'Admin' },
  { id: 'owner', label: 'Owner' },
] as const

export default function ApprovalSettingsPage() {
  const { toast } = useToast()
  const [workflows, setWorkflows] = useState<ApprovalWorkflow[]>([])
  const [types, setTypes] = useState<LeaveType[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      const [wf, leaveTypes] = await Promise.all([approvalApi.workflows(), orgApi.leaveTypes()])
      setWorkflows(wf)
      setTypes(leaveTypes)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load approvals', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const saveWorkflow = async (row: ApprovalWorkflow) => {
    setSaving(row.id)
    try {
      const updated = await approvalApi.updateWorkflow(row.id, {
        is_active: row.is_active,
        steps: row.steps.map((step, index) => ({
          order: index + 1,
          assignee_role: step.assignee_role,
        })),
      })
      setWorkflows((rows) => rows.map((item) => (item.id === updated.id ? updated : item)))
      toast('Workflow saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save workflow', 'error')
    } finally {
      setSaving(null)
    }
  }

  const saveType = async (row: LeaveType) => {
    try {
      const updated = await orgApi.updateLeaveType(row.id, row)
      setTypes((rows) => rows.map((item) => (item.id === updated.id ? updated : item)))
      toast('Leave type saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save leave type', 'error')
    }
  }

  if (loading) return <Loading label="Loading approvals..." />

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Approvals"
        description="Who signs off leave, overtime, attendance corrections, and exits. Leave entitlements can also be edited here."
      />
      <SettingsSection
        title="Approval workflows"
        description="Default is a single admin step. Add a manager step in front when people have a reporting manager."
      >
        {workflows.map((row) => (
          <div key={row.id} className="rounded-lg border border-border/70 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="font-medium">{KIND_LABEL[row.kind] || row.kind}</p>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={row.is_active}
                  onChange={(e) =>
                    setWorkflows((rows) =>
                      rows.map((item) => (item.id === row.id ? { ...item, is_active: e.target.checked } : item)),
                    )
                  }
                />
                Active
              </label>
            </div>
            <div className="space-y-2">
              {row.steps.map((step, index) => (
                <div key={`${row.id}-${index}`} className="flex flex-wrap items-center gap-2">
                  <span className="w-16 text-xs text-muted">Step {index + 1}</span>
                  <select
                    value={step.assignee_role}
                    className="field max-w-xs"
                    onChange={(e) =>
                      setWorkflows((rows) =>
                        rows.map((item) =>
                          item.id === row.id
                            ? {
                                ...item,
                                steps: item.steps.map((s, i) =>
                                  i === index
                                    ? { ...s, assignee_role: e.target.value as ApprovalWorkflow['steps'][0]['assignee_role'] }
                                    : s,
                                ),
                              }
                            : item,
                        ),
                      )
                    }
                  >
                    {ROLES.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.label}
                      </option>
                    ))}
                  </select>
                  {row.steps.length > 1 ? (
                    <button
                      type="button"
                      className="text-xs text-red-300"
                      onClick={() =>
                        setWorkflows((rows) =>
                          rows.map((item) =>
                            item.id === row.id ? { ...item, steps: item.steps.filter((_, i) => i !== index) } : item,
                          ),
                        )
                      }
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="rounded-lg border border-border px-3 py-1.5 text-xs"
                onClick={() =>
                  setWorkflows((rows) =>
                    rows.map((item) =>
                      item.id === row.id
                        ? { ...item, steps: [...item.steps, { order: item.steps.length + 1, assignee_role: 'admin' }] }
                        : item,
                    ),
                  )
                }
              >
                Add step
              </button>
              <button
                type="button"
                disabled={saving === row.id}
                className="rounded-lg bg-accent px-3 py-1.5 text-xs text-white disabled:opacity-60"
                onClick={() => saveWorkflow(row)}
              >
                {saving === row.id ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        ))}
      </SettingsSection>

      <SettingsSection
        title="Leave types"
        description="Entitlement days and paid/unpaid per type. Carry-forward and probation stay on payroll policy."
      >
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="py-2 pr-3">Type</th>
                <th className="py-2 pr-3">Days</th>
                <th className="py-2 pr-3">Paid</th>
                <th className="py-2 pr-3">Active</th>
                <th className="py-2 pr-3" />
              </tr>
            </thead>
            <tbody>
              {types.map((row) => (
                <tr key={row.id} className="border-t border-border/70">
                  <td className="py-2 pr-3">{row.name}</td>
                  <td className="py-2 pr-3">
                    <input
                      type="number"
                      min="0"
                      className="field w-24"
                      value={row.entitlement_days}
                      onChange={(e) =>
                        setTypes((rows) =>
                          rows.map((item) =>
                            item.id === row.id ? { ...item, entitlement_days: Number(e.target.value) } : item,
                          ),
                        )
                      }
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <input
                      type="checkbox"
                      checked={row.paid}
                      onChange={(e) =>
                        setTypes((rows) =>
                          rows.map((item) => (item.id === row.id ? { ...item, paid: e.target.checked } : item)),
                        )
                      }
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <input
                      type="checkbox"
                      checked={row.is_active}
                      onChange={(e) =>
                        setTypes((rows) =>
                          rows.map((item) => (item.id === row.id ? { ...item, is_active: e.target.checked } : item)),
                        )
                      }
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <button type="button" className="rounded-lg border border-border px-3 py-1 text-xs" onClick={() => saveType(row)}>
                      Save
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SettingsSection>
    </div>
  )
}

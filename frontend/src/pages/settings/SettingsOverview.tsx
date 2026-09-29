import { useCallback, useEffect, useState } from 'react'
import { orgApi, payrollApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import {
  IconBuilding,
  IconCalendar,
  IconCamera,
  IconCash,
  IconCheck,
  IconExit,
  IconGear,
  IconPeople,
  IconShift,
} from '../../components/icons'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { PayrollPolicy, Shift } from '../../types'
import { SetupCard } from './SettingsUI'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function timeLabel(value?: string) {
  return (value || '').slice(0, 5) || '—'
}

function lateLabel(policy: PayrollPolicy | null) {
  if (!policy) return 'Not configured'
  if (policy.late_penalty_mode === 'none') return 'No late deduction'
  if (policy.late_penalty_mode === 'fixed') {
    return `${policy.late_count_free} free, then ${policy.currency} ${policy.late_penalty_amount} each`
  }
  return `${policy.late_count_free} free, then ¼ day each`
}

export default function SettingsOverviewPage() {
  const { organization, labels } = useAuth()
  const { toast } = useToast()
  const [policy, setPolicy] = useState<PayrollPolicy | null>(null)
  const [shifts, setShifts] = useState<Shift[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [pay, shiftRows] = await Promise.all([payrollApi.policy(), orgApi.shifts()])
      setPolicy(pay)
      setShifts(shiftRows)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load company setup', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <Loading label="Loading company setup..." />

  const weekend = (organization?.weekend_days?.length ? organization.weekend_days : [5, 6])
    .map((n) => DAYS[n] || '')
    .filter(Boolean)
    .join(', ')
  const defaultShift = shifts.find((s) => s.is_default) || shifts[0]
  const grace = defaultShift
    ? Math.max(
        defaultShift.grace_minutes || 0,
        minutesBetween(defaultShift.start_time, defaultShift.late_after),
      )
    : 0

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-xl font-semibold tracking-tight">{organization?.name || 'Company'} rules</h3>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
          Open a card to change how attendance, pay, and leave work for the whole company.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <SetupCard
          to="/settings/organization"
          title="Organization"
          value={organization?.name || 'Company'}
          hint={`${organization?.org_type === 'school' ? 'School' : 'Company'} · ${organization?.timezone || '—'}`}
          icon={<IconGear />}
        />
        <SetupCard
          to="/settings/branches"
          title={labels.branches}
          value={`${organization?.limits.branches ?? '—'} allowed on plan`}
          hint="Locations, weekends, and mobile punch geofence"
          icon={<IconBuilding />}
        />
        <SetupCard
          to="/settings/shifts"
          title="Shifts & grace"
          value={
            defaultShift
              ? `${defaultShift.name} · ${timeLabel(defaultShift.start_time)}–${timeLabel(defaultShift.end_time)}`
              : 'No shifts yet'
          }
          hint={defaultShift ? `Late grace ${grace} min · early leave ${defaultShift.early_leave_grace_minutes ?? 15} min` : 'Add a default shift first'}
          icon={<IconShift />}
        />
        <SetupCard
          to="/settings/payroll"
          title="Salary deductions"
          value={policy?.absent_deduct ? 'Absent days deducted' : 'Absent days not deducted'}
          hint={lateLabel(policy)}
          icon={<IconCash />}
        />
        <SetupCard
          to="/settings/payroll"
          title="Leave policy"
          value={policy ? `${policy.annual_leave_days} annual · ${policy.sick_leave_days} sick` : 'Not configured'}
          hint={policy?.enforce_leave_balance ? 'Balances are enforced on approval' : 'Balances are not enforced'}
          icon={<IconCalendar />}
        />
        <SetupCard
          to="/settings/calendar"
          title="Work calendar"
          value={weekend ? `Weekend ${weekend}` : 'Weekend not set'}
          hint="Holidays and weekly off days"
          icon={<IconCalendar />}
        />
        <SetupCard
          to="/settings/approvals"
          title="Approvals"
          value="Leave, overtime, corrections, exits"
          hint="Who signs off each request"
          icon={<IconCheck />}
        />
        <SetupCard
          to="/settings/departments"
          title={labels.department}
          value={`Assign ${labels.department.toLowerCase()}s to people`}
          hint="Used on reports and payroll grouping"
          icon={<IconPeople />}
        />
        <SetupCard
          to="/settings/exit"
          title="Exit policy"
          value="Notice, clearance, and access"
          hint="What happens when someone leaves"
          icon={<IconExit />}
        />
        <SetupCard
          to="/settings/cameras"
          title="Cameras"
          value={`${organization?.limits.cameras ?? 0} camera slots`}
          hint="CCTV zones for auto check-in / check-out"
          icon={<IconCamera />}
        />
      </div>
    </div>
  )
}

function minutesBetween(start?: string, late?: string) {
  const a = toMinutes(start)
  const b = toMinutes(late)
  if (a == null || b == null) return 0
  let diff = b - a
  if (diff < 0) diff += 24 * 60
  return diff
}

function toMinutes(value?: string) {
  const part = (value || '').slice(0, 5)
  const [h, m] = part.split(':').map(Number)
  if (Number.isNaN(h) || Number.isNaN(m)) return null
  return h * 60 + m
}

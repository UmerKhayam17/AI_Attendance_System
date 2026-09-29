import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { payrollApi } from '../../api/services'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { PayrollPolicy } from '../../types'
import { Field, SettingsPageHeader, SettingsSection, StickySave, Toggle } from './SettingsUI'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function money(currency: string, amount: number) {
  const n = Number.isFinite(amount) ? amount : 0
  return `${currency} ${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

export default function PayrollSettingsPage() {
  const { toast } = useToast()
  const [form, setForm] = useState<PayrollPolicy | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [exampleSalary, setExampleSalary] = useState('50000')

  const load = useCallback(async () => {
    try {
      setForm(await payrollApi.policy())
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load payroll policy', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!form) return
    setSaving(true)
    try {
      setForm(await payrollApi.updatePolicy(form))
      toast('Payroll policy saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const set = <K extends keyof PayrollPolicy>(key: K, value: PayrollPolicy[K]) => {
    if (!form) return
    setForm({ ...form, [key]: value })
  }

  const preview = useMemo(() => {
    if (!form) return null
    const salary = Number(exampleSalary) || 0
    const days = Number(form.working_days_per_month) || 26
    const hours = Number(form.hours_per_day) || 8
    const daily = days > 0 ? salary / days : 0
    const hourly = hours > 0 ? daily / hours : 0
    const halfFactor = Number(form.half_day_pay_factor) || 0.5
    const lateFixed = Number(form.late_penalty_amount) || 0
    const ot = Number(form.overtime_multiplier) || 1
    return {
      daily,
      hourly,
      absent: form.absent_deduct ? daily : 0,
      half: daily * (1 - halfFactor),
      late:
        form.late_penalty_mode === 'none'
          ? 0
          : form.late_penalty_mode === 'fixed'
            ? lateFixed
            : daily * 0.25,
      early: form.early_leave_deduct ? (form.early_leave_as_half_day ? daily * (1 - halfFactor) : daily) : 0,
      otHour: hourly * ot,
    }
  }, [exampleSalary, form])

  if (loading || !form) return <Loading label="Loading payroll policy..." />

  const lateHint =
    form.late_penalty_mode === 'none'
      ? 'Late arrivals are recorded but do not reduce salary.'
      : form.late_penalty_mode === 'fixed'
        ? `First ${form.late_count_free} lates are free, then ${form.currency} ${form.late_penalty_amount} is deducted for each extra late.`
        : `First ${form.late_count_free} lates are free, then each extra late deducts a quarter day of salary.`

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <SettingsPageHeader
        title="Payroll & deductions"
        description="Company-wide salary rules. Individual basic pay is set on each person; these rules decide what gets deducted or added."
      />

      <SettingsSection title="Pay cycle" description="Currency and how a day’s salary is calculated from monthly pay.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Currency">
            <select value={form.currency} onChange={(e) => set('currency', e.target.value)} className="field">
              {['PKR', 'USD', 'AED', 'SAR', 'GBP', 'EUR', 'INR'].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </Field>
          <Field label="Pay frequency">
            <select
              value={form.pay_frequency}
              onChange={(e) => set('pay_frequency', e.target.value as PayrollPolicy['pay_frequency'])}
              className="field"
            >
              <option value="monthly">Monthly</option>
              <option value="biweekly">Biweekly</option>
              <option value="weekly">Weekly</option>
            </select>
          </Field>
          <Field label="Working days per month" hint="Daily rate = monthly salary ÷ this number. Many companies use 26.">
            <input
              required
              type="number"
              min="1"
              max="31"
              step="0.5"
              value={form.working_days_per_month}
              onChange={(e) => set('working_days_per_month', e.target.value)}
              className="field"
            />
          </Field>
          <Field label="Hours per day" hint="Used for hourly overtime and hourly staff.">
            <input
              required
              type="number"
              min="1"
              max="24"
              step="0.5"
              value={form.hours_per_day}
              onChange={(e) => set('hours_per_day', e.target.value)}
              className="field"
            />
          </Field>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Salary deduction rules"
        description="Turn a rule on, then see the amount on a sample monthly salary. Late grace itself is set on each shift."
      >
        <div className="mb-5 grid gap-3 sm:grid-cols-2">
          <Toggle
            label="Deduct absent working days"
            hint="A missed working day with no approved leave costs one daily rate."
            checked={form.absent_deduct}
            onChange={(v) => set('absent_deduct', v)}
          />
          <Toggle
            label="Deduct early leave"
            hint="Leaving before shift end (after early-leave grace) reduces pay."
            checked={form.early_leave_deduct}
            onChange={(v) => set('early_leave_deduct', v)}
          />
          <Toggle
            label="Treat early leave as a half day"
            hint="If off, a full daily rate is deducted instead of the half-day factor."
            checked={form.early_leave_as_half_day}
            onChange={(v) => set('early_leave_as_half_day', v)}
          />
          <Toggle
            label="Holidays are paid (daily / hourly staff)"
            hint="Monthly staff are already paid for the month; this applies to daily and hourly pay types."
            checked={form.holiday_paid}
            onChange={(v) => set('holiday_paid', v)}
          />
          <Toggle
            label="Weekends are paid (daily / hourly staff)"
            checked={form.weekend_paid}
            onChange={(v) => set('weekend_paid', v)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Half-day pay factor" hint="0.5 means a half day is paid at 50% (50% deducted).">
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={form.half_day_pay_factor}
              onChange={(e) => set('half_day_pay_factor', e.target.value)}
              className="field"
            />
          </Field>
          <Field label="Free lates per period" hint="Lates inside the count are recorded but not fined.">
            <input
              type="number"
              min="0"
              value={form.late_count_free}
              onChange={(e) => set('late_count_free', Number(e.target.value))}
              className="field"
            />
          </Field>
          <Field label="Late penalty after free lates">
            <select
              value={form.late_penalty_mode}
              onChange={(e) => set('late_penalty_mode', e.target.value as PayrollPolicy['late_penalty_mode'])}
              className="field"
            >
              <option value="none">None — no salary cut</option>
              <option value="fixed">Fixed amount per extra late</option>
              <option value="quarter_day">Quarter day per extra late</option>
            </select>
          </Field>
          <Field label="Fixed late amount" hint={form.late_penalty_mode === 'fixed' ? 'Charged after free lates are used.' : 'Only used when penalty is a fixed amount.'}>
            <input
              type="number"
              min="0"
              step="0.01"
              disabled={form.late_penalty_mode !== 'fixed'}
              value={form.late_penalty_amount}
              onChange={(e) => set('late_penalty_amount', e.target.value)}
              className="field disabled:opacity-50"
            />
          </Field>
        </div>
        <p className="mt-4 rounded-xl border border-border bg-surface/60 px-4 py-3 text-sm leading-6 text-slate-300">
          {lateHint}
        </p>

        {preview ? (
          <div className="mt-5 rounded-2xl border border-accent/20 bg-accent/5 p-4 sm:p-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">What this means on a payslip</p>
                <p className="text-xs text-muted">Example monthly salary — change the amount to preview.</p>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted">{form.currency}</span>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={exampleSalary}
                  onChange={(e) => setExampleSalary(e.target.value)}
                  className="field w-36"
                />
              </label>
            </div>
            <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <PreviewStat label="Daily rate" value={money(form.currency, preview.daily)} />
              <PreviewStat label="One absent day" value={form.absent_deduct ? `− ${money(form.currency, preview.absent)}` : 'No deduction'} />
              <PreviewStat label="Half day deducted" value={`− ${money(form.currency, preview.half)}`} />
              <PreviewStat label="One extra late" value={preview.late ? `− ${money(form.currency, preview.late)}` : 'No deduction'} />
              <PreviewStat
                label="Early leave"
                value={form.early_leave_deduct ? `− ${money(form.currency, preview.early)}` : 'No deduction'}
              />
              <PreviewStat label="1 hour overtime" value={form.overtime_paid ? `+ ${money(form.currency, preview.otHour)}` : 'Not paid'} />
            </dl>
          </div>
        ) : null}
      </SettingsSection>

      <SettingsSection title="Leave policy" description="Yearly allowances. Approving leave over the remaining balance is blocked when enforcement is on.">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Annual / casual days">
            <input type="number" min="0" value={form.annual_leave_days} onChange={(e) => set('annual_leave_days', Number(e.target.value))} className="field" />
          </Field>
          <Field label="Sick leave days">
            <input type="number" min="0" value={form.sick_leave_days} onChange={(e) => set('sick_leave_days', Number(e.target.value))} className="field" />
          </Field>
          <Field label="Other leave days">
            <input type="number" min="0" value={form.other_leave_days} onChange={(e) => set('other_leave_days', Number(e.target.value))} className="field" />
          </Field>
          <Field label="Leave year starts">
            <select value={form.leave_year_start_month} onChange={(e) => set('leave_year_start_month', Number(e.target.value))} className="field">
              {MONTHS.map((name, i) => (
                <option key={name} value={i + 1}>{name}</option>
              ))}
            </select>
          </Field>
          <Field label="Probation (months)" hint="0 = annual leave available immediately.">
            <input type="number" min="0" value={form.probation_months} onChange={(e) => set('probation_months', Number(e.target.value))} className="field" />
          </Field>
          <Field label="Carry-forward cap">
            <input type="number" min="0" value={form.carry_forward_max_days} onChange={(e) => set('carry_forward_max_days', Number(e.target.value))} className="field" />
          </Field>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Toggle label="Annual leave is paid" checked={form.annual_leave_paid} onChange={(v) => set('annual_leave_paid', v)} />
          <Toggle label="Sick leave is paid" checked={form.sick_leave_paid} onChange={(v) => set('sick_leave_paid', v)} />
          <Toggle label="Other leave is paid" checked={form.other_leave_paid} onChange={(v) => set('other_leave_paid', v)} />
          <Toggle label="Allow unpaid leave" checked={form.unpaid_leave_allowed} onChange={(v) => set('unpaid_leave_allowed', v)} />
          <Toggle label="Carry unused annual leave into next year" checked={form.carry_forward_annual} onChange={(v) => set('carry_forward_annual', v)} />
          <Toggle label="Block annual leave during probation" checked={form.probation_blocks_annual} onChange={(v) => set('probation_blocks_annual', v)} />
          <Toggle
            label="Enforce leave balances"
            hint="Reject approval when the person has no remaining days of that type."
            checked={form.enforce_leave_balance}
            onChange={(v) => set('enforce_leave_balance', v)}
          />
        </div>
      </SettingsSection>

      <SettingsSection title="Overtime & statutory" description="Overtime minutes come from checkout. Tax and provident fund apply to the payslip.">
        <div className="grid gap-3 sm:grid-cols-2">
          <Toggle
            label="Pay overtime from attendance"
            hint="Uses overtime minutes already calculated at checkout."
            checked={form.overtime_paid}
            onChange={(v) => set('overtime_paid', v)}
          />
          <Toggle
            label="Overtime requires approval"
            hint="Payroll only pays approved overtime requests."
            checked={Boolean(form.overtime_requires_approval)}
            onChange={(v) => set('overtime_requires_approval', v)}
          />
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="OT multiplier" hint="1.5 means time-and-a-half.">
            <input type="number" min="1" step="0.1" value={form.overtime_multiplier} onChange={(e) => set('overtime_multiplier', e.target.value)} className="field" />
          </Field>
          <Field label="Minimum OT minutes" hint="Shorter overtime is ignored.">
            <input type="number" min="0" value={form.overtime_min_minutes} onChange={(e) => set('overtime_min_minutes', Number(e.target.value))} className="field" />
          </Field>
          <Field label="Tax %">
            <input type="number" min="0" max="100" step="0.01" value={form.tax_percent} onChange={(e) => set('tax_percent', e.target.value)} className="field" />
          </Field>
          <Field label="Provident fund %">
            <input type="number" min="0" max="100" step="0.01" value={form.provident_fund_percent} onChange={(e) => set('provident_fund_percent', e.target.value)} className="field" />
          </Field>
        </div>
      </SettingsSection>

      <StickySave saving={saving} label="Save payroll policy" />
    </form>
  )
}

function PreviewStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-panel/80 px-3 py-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-sm font-semibold">{value}</dd>
    </div>
  )
}

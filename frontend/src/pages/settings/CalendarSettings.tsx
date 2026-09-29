import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { attendanceApi, orgApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import { Badge } from '../../components/Badge'
import { BranchFilter } from '../../components/BranchFilter'
import { EmptyState, Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { Holiday } from '../../types'
import { SettingsPageHeader, SettingsSection } from './SettingsUI'

const DAYS = [
  { n: 0, label: 'Mon' },
  { n: 1, label: 'Tue' },
  { n: 2, label: 'Wed' },
  { n: 3, label: 'Thu' },
  { n: 4, label: 'Fri' },
  { n: 5, label: 'Sat' },
  { n: 6, label: 'Sun' },
]

export default function CalendarSettingsPage() {
  const { organization, refreshMe, labels } = useAuth()
  const { toast } = useToast()
  const [weekend, setWeekend] = useState<number[]>(organization?.weekend_days?.length ? organization.weekend_days : [5, 6])
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [date, setDate] = useState('')
  const [yearly, setYearly] = useState(false)
  const [holidayBranch, setHolidayBranch] = useState<number | 'all'>('all')

  const load = useCallback(async () => {
    try {
      setHolidays(await attendanceApi.holidays())
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load holidays', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (organization?.weekend_days?.length) setWeekend(organization.weekend_days)
  }, [organization?.weekend_days])

  const saveWeekend = async () => {
    setSaving(true)
    try {
      await orgApi.update({ weekend_days: weekend })
      await refreshMe()
      toast('Weekend days saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const addHoliday = async (e: FormEvent) => {
    e.preventDefault()
    if (!date || !name.trim()) return
    try {
      await attendanceApi.createHoliday({
        date,
        name: name.trim(),
        repeats_yearly: yearly,
        branch: holidayBranch === 'all' ? null : holidayBranch,
      })
      setName('')
      setDate('')
      setYearly(false)
      toast('Holiday added', 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not add holiday', 'error')
    }
  }

  if (loading) return <Loading />

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Work calendar"
        description="Weekend days are not counted as absences. Holidays apply to all branches unless you scope one."
      />
      <SettingsSection title="Weekend" description="People are not marked absent on these days.">
        <div className="flex flex-wrap gap-2">
          {DAYS.map((d) => {
            const on = weekend.includes(d.n)
            return (
              <button
                key={d.n}
                type="button"
                onClick={() =>
                  setWeekend((prev) => (on ? prev.filter((n) => n !== d.n) : [...prev, d.n].sort()))
                }
                className={`rounded-lg px-3 py-1.5 text-sm ${on ? 'bg-accent text-white' : 'border border-border text-muted'}`}
              >
                {d.label}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          disabled={saving}
          onClick={saveWeekend}
          className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60"
        >
          {saving ? 'Saving...' : 'Save weekend'}
        </button>
      </SettingsSection>

      <SettingsSection title="Holidays" description="Public holidays are paid or unpaid according to payroll policy.">
        <form onSubmit={addHoliday} className="grid gap-3 md:grid-cols-[1fr_160px_1fr_auto_auto]">
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Holiday name"
            className="field"
          />
          <input required type="date" value={date} onChange={(e) => setDate(e.target.value)} className="field" />
          <BranchFilter value={holidayBranch} onChange={setHolidayBranch} />
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={yearly} onChange={(e) => setYearly(e.target.checked)} />
            Repeats yearly
          </label>
          <button type="submit" className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
            Add
          </button>
        </form>

        {holidays.length === 0 ? (
          <div className="mt-4">
            <EmptyState title="No holidays" description="Add public holidays so they are not counted as absences." />
          </div>
        ) : (
          <table className="mt-4 min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="py-2">Date</th>
                <th className="py-2">Name</th>
                <th className="py-2">{labels.branch}</th>
                <th className="py-2">Repeats</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {holidays.map((h) => (
                <tr key={h.id} className="border-t border-border/70">
                  <td className="py-3">{h.date}</td>
                  <td className="py-3">{h.name}</td>
                  <td className="py-3 text-muted">{h.branch_name || 'All'}</td>
                  <td className="py-3">
                    <Badge label={h.repeats_yearly ? 'Yearly' : 'Once'} tone={h.repeats_yearly ? 'enrolled' : 'inactive'} />
                  </td>
                  <td className="py-3 text-right">
                    <button
                      type="button"
                      className="text-xs text-red-300"
                      onClick={async () => {
                        await attendanceApi.deleteHoliday(h.id)
                        await load()
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SettingsSection>
    </div>
  )
}

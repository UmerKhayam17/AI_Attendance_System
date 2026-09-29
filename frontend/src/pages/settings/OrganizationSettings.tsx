import { type FormEvent, useState } from 'react'
import { orgApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import { useToast } from '../../components/Toast'
import { Field, SettingsPageHeader, SettingsSection, StickySave } from './SettingsUI'

const TIMEZONES = [
  'Asia/Karachi',
  'Asia/Dubai',
  'Asia/Riyadh',
  'Asia/Kolkata',
  'Asia/Dhaka',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Europe/London',
  'Europe/Berlin',
  'Africa/Cairo',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'UTC',
]

export default function OrganizationSettingsPage() {
  const { organization, refreshMe } = useAuth()
  const { toast } = useToast()
  const [form, setForm] = useState({
    name: organization?.name || '',
    org_type: organization?.org_type || 'company',
    timezone: organization?.timezone || 'Asia/Karachi',
  })
  const [saving, setSaving] = useState(false)
  const timezoneOptions = TIMEZONES.includes(form.timezone) ? TIMEZONES : [form.timezone, ...TIMEZONES]

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await orgApi.update(form)
      await refreshMe()
      toast('Organization updated', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Update failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <SettingsPageHeader
        title="Organization"
        description="Company name, type, and timezone used for attendance clocks and reports."
      />
      <SettingsSection title="Profile" description="This name appears in the sidebar, emails, and payslips.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Company name" className="sm:col-span-2">
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="field" />
          </Field>
          <Field label="Type" hint="School mode changes labels such as students and classes.">
            <select
              value={form.org_type}
              onChange={(e) => setForm({ ...form, org_type: e.target.value as 'company' | 'school' })}
              className="field"
            >
              <option value="company">Company / office</option>
              <option value="school">School</option>
            </select>
          </Field>
          <Field label="Timezone" hint="Shift times and attendance dates use this timezone.">
            <select value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} className="field">
              {timezoneOptions.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </SettingsSection>
      <StickySave saving={saving} label="Save organization" />
    </form>
  )
}

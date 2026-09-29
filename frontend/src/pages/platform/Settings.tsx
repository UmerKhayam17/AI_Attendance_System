import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../api/services'
import { Badge } from '../../components/Badge'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { PlatformSettings } from '../../types'

export default function PlatformSettingsPage() {
  const { toast } = useToast()
  const [data, setData] = useState<PlatformSettings | null>(null)
  const [trialDays, setTrialDays] = useState(14)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const settings = await platformApi.settings()
      setData(settings)
      setTrialDays(settings.trial_days)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load settings', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const onSave = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload: { trial_days: number; current_password?: string; new_password?: string } = {
        trial_days: trialDays,
      }
      if (newPassword) {
        payload.current_password = currentPassword
        payload.new_password = newPassword
      }
      const settings = await platformApi.updateSettings(payload)
      setData(settings)
      setCurrentPassword('')
      setNewPassword('')
      toast('Settings saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading || !data) return <Loading label="Loading settings..." />

  return (
    <form onSubmit={onSave} className="max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="text-sm text-muted">Platform defaults for trials and the super admin account</p>
      </div>

      <section className="space-y-4 rounded-xl border border-border bg-panel p-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted">Super admin</p>
          <Badge label={data.superadmin_email} tone="trained" />
        </div>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted">Stripe</p>
          <Badge label={data.stripe_configured ? 'Configured' : 'Not configured'} tone={data.stripe_configured ? 'active' : 'pending'} />
        </div>
        <p className="text-xs text-muted">Frontend URL: {data.frontend_url || '—'}</p>
      </section>

      <section className="space-y-4 rounded-xl border border-border bg-panel p-6">
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Self-serve trial length (days)</span>
          <input
            type="number"
            min={1}
            max={365}
            value={trialDays}
            onChange={(e) => setTrialDays(Number(e.target.value))}
            className="field"
          />
        </label>
        <p className="text-xs text-muted">Applies to new signups. Super-admin complimentary companies skip this.</p>
      </section>

      <section className="space-y-4 rounded-xl border border-border bg-panel p-6">
        <h3 className="font-medium">Change password</h3>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Current password</span>
          <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">New password</span>
          <input type="password" minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="field" />
        </label>
      </section>

      <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
        {saving ? 'Saving...' : 'Save settings'}
      </button>
    </form>
  )
}

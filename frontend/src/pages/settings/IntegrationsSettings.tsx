import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { orgApi } from '../../api/services'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { Integrations } from '../../types'
import { Field, SettingsPageHeader, SettingsSection, StickySave, Toggle } from './SettingsUI'

export default function IntegrationsSettingsPage() {
  const { toast } = useToast()
  const [data, setData] = useState<Integrations | null>(null)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({
    webhook_url: '',
    webhook_secret: '',
    notify_late: true,
    notify_absent: true,
    notify_email: true,
    notify_sms: false,
    notify_whatsapp: false,
    twilio_account_sid: '',
    twilio_auth_token: '',
    twilio_from_number: '',
    twilio_whatsapp_from: '',
  })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const integrations = await orgApi.integrations()
      setData(integrations)
      setForm({
        webhook_url: integrations.webhook_url || '',
        webhook_secret: integrations.webhook_secret || '',
        notify_late: integrations.notify_late ?? true,
        notify_absent: integrations.notify_absent ?? true,
        notify_email: integrations.notify_email ?? true,
        notify_sms: integrations.notify_sms ?? false,
        notify_whatsapp: integrations.notify_whatsapp ?? false,
        twilio_account_sid: integrations.twilio_account_sid || '',
        twilio_auth_token: integrations.twilio_auth_token || '',
        twilio_from_number: integrations.twilio_from_number || '',
        twilio_whatsapp_from: integrations.twilio_whatsapp_from || '',
      })
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load integrations', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      setData(await orgApi.updateIntegrations(form))
      toast('Integrations saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading || !data) return <Loading />

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Integrations"
        description="Webhooks, late/absent alerts, and the API key for your HR or school system."
      />
      <form onSubmit={onSubmit} className="space-y-6">
        <SettingsSection title="Attendance webhook" description={!data.can_use_webhooks ? 'Webhooks require Starter or Pro.' : 'POST check-in and check-out events to your system.'}>
          <div className="grid gap-4">
            <Field label="Webhook URL">
              <input value={form.webhook_url} onChange={(e) => setForm({ ...form, webhook_url: e.target.value })} className="field" placeholder="https://..." />
            </Field>
            <Field label="Webhook secret">
              <input value={form.webhook_secret} onChange={(e) => setForm({ ...form, webhook_secret: e.target.value })} className="field" />
            </Field>
          </div>
        </SettingsSection>

        <SettingsSection title="Late / absent alerts" description="Email works on every plan. SMS and WhatsApp use Twilio and need Starter or Pro.">
          <div className="grid gap-3 sm:grid-cols-2">
            <Toggle label="Notify on late check-in" checked={form.notify_late} onChange={(v) => setForm({ ...form, notify_late: v })} />
            <Toggle label="Notify if still absent after late time" checked={form.notify_absent} onChange={(v) => setForm({ ...form, notify_absent: v })} />
            <Toggle label="Email (person + guardian)" checked={form.notify_email} onChange={(v) => setForm({ ...form, notify_email: v })} />
            <Toggle label="SMS via Twilio" checked={form.notify_sms} onChange={(v) => setForm({ ...form, notify_sms: v })} disabled={!data.can_use_alerts} />
            <Toggle label="WhatsApp via Twilio" checked={form.notify_whatsapp} onChange={(v) => setForm({ ...form, notify_whatsapp: v })} disabled={!data.can_use_alerts} />
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Field label="Twilio Account SID">
              <input value={form.twilio_account_sid} onChange={(e) => setForm({ ...form, twilio_account_sid: e.target.value })} className="field" />
            </Field>
            <Field label="Twilio Auth Token">
              <input value={form.twilio_auth_token} onChange={(e) => setForm({ ...form, twilio_auth_token: e.target.value })} className="field" />
            </Field>
            <Field label="SMS from number">
              <input value={form.twilio_from_number} onChange={(e) => setForm({ ...form, twilio_from_number: e.target.value })} className="field" placeholder="+1234567890" />
            </Field>
            <Field label="WhatsApp from">
              <input value={form.twilio_whatsapp_from} onChange={(e) => setForm({ ...form, twilio_whatsapp_from: e.target.value })} className="field" placeholder="whatsapp:+14155238886" />
            </Field>
          </div>
        </SettingsSection>

        <StickySave saving={saving} label="Save integrations" />
      </form>

      <SettingsSection title="API key">
        {!data.can_use_api_key ? (
          <p className="text-sm text-amber-200">API keys require the Pro plan.</p>
        ) : (
          <>
            <code className="block break-all rounded-lg bg-surface px-3 py-2 text-xs">{data.api_key}</code>
            <p className="mt-2 text-xs text-muted">Send as X-API-Key on /api/ requests from your school or HR system.</p>
            <button
              type="button"
              onClick={async () => {
                try {
                  setData(await orgApi.rotateKey())
                  toast('API key rotated', 'info')
                } catch (err) {
                  toast(err instanceof Error ? err.message : 'Rotate failed', 'error')
                }
              }}
              className="mt-4 rounded-lg border border-border px-4 py-2 text-sm"
            >
              Rotate key
            </button>
          </>
        )}
      </SettingsSection>
    </div>
  )
}

import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../api/services'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { PlanId, PlanLimits } from '../../types'

type PlanRow = { id: PlanId } & PlanLimits

export default function PlatformPlansPage() {
  const { toast } = useToast()
  const [plans, setPlans] = useState<PlanRow[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await platformApi.plans()
      setPlans(data.plans)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load plans', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const update = (id: PlanId, patch: Partial<PlanLimits>) => {
    setPlans((prev) => prev.map((plan) => (plan.id === id ? { ...plan, ...patch } : plan)))
  }

  const onSave = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const data = await platformApi.savePlans(plans)
      setPlans(data.plans)
      toast('Plans saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading label="Loading plans..." />

  return (
    <form onSubmit={onSave} className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Plans</h2>
          <p className="text-sm text-muted">Limits shown to every company. Self-serve customers still pay via Stripe.</p>
        </div>
        <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
          {saving ? 'Saving...' : 'Save plans'}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {plans.map((plan) => (
          <article key={plan.id} className="space-y-4 rounded-xl border border-border bg-panel p-5">
            <input
              value={plan.label}
              onChange={(e) => update(plan.id, { label: e.target.value })}
              className="field text-lg font-semibold"
            />
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">People (blank = unlimited)</span>
              <input
                type="number"
                min={0}
                value={plan.people ?? ''}
                onChange={(e) => update(plan.id, { people: e.target.value === '' ? null : Number(e.target.value) })}
                className="field"
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">CCTV cameras</span>
              <input
                type="number"
                min={0}
                value={plan.cameras}
                onChange={(e) => update(plan.id, { cameras: Number(e.target.value) })}
                className="field"
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Staff logins (blank = unlimited)</span>
              <input
                type="number"
                min={0}
                value={plan.staff ?? ''}
                onChange={(e) => update(plan.id, { staff: e.target.value === '' ? null : Number(e.target.value) })}
                className="field"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={plan.webhooks} onChange={(e) => update(plan.id, { webhooks: e.target.checked })} />
              Webhooks
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={plan.api_key} onChange={(e) => update(plan.id, { api_key: e.target.checked })} />
              API key
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={Boolean(plan.alerts)} onChange={(e) => update(plan.id, { alerts: e.target.checked })} />
              SMS / WhatsApp alerts
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={Boolean(plan.exports)} onChange={(e) => update(plan.id, { exports: e.target.checked })} />
              Excel / PDF export
            </label>
          </article>
        ))}
      </div>
    </form>
  )
}

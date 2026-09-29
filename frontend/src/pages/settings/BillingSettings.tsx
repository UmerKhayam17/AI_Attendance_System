import { useCallback, useEffect, useState } from 'react'
import { billingApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import { Badge } from '../../components/Badge'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { BillingSummary, PlanId } from '../../types'
import { SettingsPageHeader } from './SettingsUI'

export default function BillingSettingsPage() {
  const { refreshMe } = useAuth()
  const { toast } = useToast()
  const [data, setData] = useState<BillingSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<PlanId | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await billingApi.summary())
      await refreshMe()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load billing', 'error')
    } finally {
      setLoading(false)
    }
  }, [refreshMe, toast])

  useEffect(() => {
    load()
  }, [load])

  const checkout = async (plan: 'starter' | 'pro') => {
    setBusy(plan)
    try {
      const { url } = await billingApi.checkout(plan)
      window.location.assign(url)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Checkout failed', 'error')
      setBusy(null)
    }
  }

  const portal = async () => {
    try {
      const { url } = await billingApi.portal()
      window.location.assign(url)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Portal failed', 'error')
    }
  }

  if (loading || !data) return <Loading />
  const org = data.organization

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Billing"
        description="Current plan, trial, and upgrades. Limits for people, cameras, and staff logins come from the plan."
      />
      <div className="rounded-2xl border border-border bg-panel p-5">
        <div className="flex flex-wrap items-center gap-3">
          <Badge label={org.effective_plan} tone="trained" />
          <span className="text-sm text-muted capitalize">{org.subscription_status}</span>
          {org.trial_active && org.trial_ends_at && (
            <span className="text-sm text-amber-200">
              Trial ends {new Date(org.trial_ends_at).toLocaleDateString()}
            </span>
          )}
        </div>
        {data.billing_exempt ? (
          <p className="mt-3 text-sm text-emerald-200">
            This workspace is complimentary. Payment is not required — the platform assigned your plan.
          </p>
        ) : (
          <>
            {!data.stripe_configured && (
              <p className="mt-3 text-sm text-amber-200">
                Stripe is not configured. Set STRIPE_SECRET_KEY and price IDs in the backend environment.
              </p>
            )}
            {data.has_stripe_customer && (
              <button type="button" onClick={portal} className="mt-4 rounded-lg border border-border px-4 py-2 text-sm">
                Manage subscription
              </button>
            )}
          </>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {data.plans.map((plan) => (
          <article key={plan.id} className="rounded-xl border border-border bg-panel p-5">
            <h3 className="text-lg font-semibold">{plan.label}</h3>
            <ul className="mt-4 space-y-2 text-sm text-muted">
              <li>{plan.people ?? 'Unlimited'} people</li>
              <li>{plan.cameras} CCTV cameras</li>
              <li>{plan.staff == null ? 'Unlimited' : plan.staff} staff logins</li>
              <li>{plan.webhooks ? 'Webhooks included' : 'No webhooks'}</li>
              <li>{plan.api_key ? 'API key included' : 'No API key'}</li>
              <li>{plan.alerts ? 'SMS / WhatsApp alerts' : 'Email alerts only'}</li>
              <li>{plan.exports ? 'Excel / PDF export' : 'CSV export only'}</li>
            </ul>
            {plan.id !== 'free' && !data.billing_exempt && (
              <button
                type="button"
                disabled={busy !== null || org.effective_plan === plan.id}
                onClick={() => checkout(plan.id as 'starter' | 'pro')}
                className="mt-5 w-full rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {org.effective_plan === plan.id ? 'Current plan' : busy === plan.id ? 'Redirecting...' : `Upgrade to ${plan.label}`}
              </button>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}

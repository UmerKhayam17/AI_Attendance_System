import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { platformApi } from '../../api/services'
import { Badge } from '../../components/Badge'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { PlatformDashboard } from '../../types'

export default function PlatformDashboardPage() {
  const { toast } = useToast()
  const [data, setData] = useState<PlatformDashboard | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setData(await platformApi.dashboard())
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load dashboard', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  if (loading || !data) return <Loading label="Loading dashboard..." />
  const { totals } = data

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Dashboard</h2>
          <p className="text-sm text-muted">Platform-wide overview</p>
        </div>
        <Link to="/platform/companies" className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
          View companies
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <Stat title="Organizations" value={totals.organizations} />
        <Stat title="Active" value={totals.active} accent="text-emerald-400" />
        <Stat title="Complimentary" value={totals.complimentary} accent="text-violet-400" />
        <Stat title="Self-serve" value={totals.self_serve} accent="text-cyan-400" />
        <Stat title="People" value={totals.people} />
        <Stat title="Cameras" value={totals.cameras} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-border bg-panel">
          <div className="border-b border-border px-5 py-4">
            <h3 className="font-medium">Orgs by plan</h3>
          </div>
          <div className="divide-y divide-border/70">
            {data.by_plan.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-muted">No organizations yet</p>
            ) : (
              data.by_plan.map((row) => (
                <div key={row.plan} className="flex items-center justify-between px-5 py-4">
                  <span className="capitalize">{row.plan}</span>
                  <span className="font-medium">{row.total}</span>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-xl border border-border bg-panel">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h3 className="font-medium">Recent companies</h3>
            <Badge label={data.stripe_configured ? 'Stripe on' : 'Stripe off'} tone={data.stripe_configured ? 'active' : 'pending'} />
          </div>
          <div className="divide-y divide-border/70">
            {data.recent.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-muted">No companies yet</p>
            ) : (
              data.recent.map((org) => (
                <div key={org.id} className="flex items-center justify-between gap-3 px-5 py-4">
                  <div>
                    <p className="font-medium">{org.name}</p>
                    <p className="text-xs text-muted">{org.owner_email || 'No owner'} · {org.people_count} people</p>
                  </div>
                  <Badge label={org.billing_exempt ? 'No payment' : org.effective_plan} tone={org.billing_exempt ? 'trained' : 'enrolled'} />
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

function Stat({ title, value, accent = 'text-blue-400' }: { title: string; value: number; accent?: string }) {
  return (
    <div className="rounded-xl border border-border bg-panel p-5">
      <p className="text-sm text-muted">{title}</p>
      <p className={`mt-2 text-3xl font-semibold ${accent}`}>{value}</p>
    </div>
  )
}

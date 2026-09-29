import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../api/services'
import { Badge } from '../../components/Badge'
import { EmptyState, Loading, Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { PlanId, PlatformOrganization, PlatformOverview } from '../../types'

const emptyForm = {
  name: '',
  org_type: 'company' as 'company' | 'school',
  plan: 'starter' as PlanId,
  billing_exempt: true,
  owner_first_name: '',
  owner_last_name: '',
  owner_email: '',
  owner_password: '',
}

export default function CompaniesPage() {
  const { toast } = useToast()
  const [data, setData] = useState<PlatformOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      setData(await platformApi.list())
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load companies', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const onCreate = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await platformApi.create(form)
      toast('Company created without requiring payment', 'success')
      setOpen(false)
      setForm(emptyForm)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Create failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (org: PlatformOrganization) => {
    try {
      await platformApi.update(org.id, { is_active: !org.is_active })
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Update failed', 'error')
    }
  }

  const changePlan = async (org: PlatformOrganization, plan: PlanId) => {
    try {
      await platformApi.update(org.id, { plan })
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Plan update failed', 'error')
    }
  }

  const toggleBilling = async (org: PlatformOrganization) => {
    try {
      await platformApi.update(org.id, { billing_exempt: !org.billing_exempt })
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Billing update failed', 'error')
    }
  }

  if (loading || !data) return <Loading label="Loading companies..." />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Companies</h2>
          <p className="text-sm text-muted">
            Super-admin created companies do not need Stripe. Self-signup customers pay from the app.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
        >
          Add company
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Organizations" value={data.totals.organizations} />
        <Stat label="Active" value={data.totals.active} />
        <Stat label="Complimentary" value={data.totals.complimentary} />
        <Stat label="Self-serve (Stripe)" value={data.totals.self_serve} />
      </div>

      {data.organizations.length === 0 ? (
        <EmptyState title="No companies yet" description="Add a company to grant a plan without payment, or wait for customers to sign up." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-surface/60 text-left text-muted">
                <tr>
                  <th className="px-5 py-3">Company</th>
                  <th className="px-5 py-3">Owner</th>
                  <th className="px-5 py-3">Plan</th>
                  <th className="px-5 py-3">Billing</th>
                  <th className="px-5 py-3">People</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.organizations.map((org) => (
                  <tr key={org.id} className="border-t border-border/70">
                    <td className="px-5 py-4">
                      <p className="font-medium">{org.name}</p>
                      <p className="text-xs text-muted capitalize">{org.org_type} · {org.slug}</p>
                    </td>
                    <td className="px-5 py-4">
                      <p>{org.owner_name || '—'}</p>
                      <p className="text-xs text-muted">{org.owner_email || 'No owner'}</p>
                    </td>
                    <td className="px-5 py-4">
                      <select
                        value={org.plan}
                        onChange={(e) => changePlan(org, e.target.value as PlanId)}
                        className="rounded-lg border border-border bg-surface px-2 py-1 text-xs"
                      >
                        <option value="free">Free</option>
                        <option value="starter">Starter</option>
                        <option value="pro">Pro</option>
                      </select>
                    </td>
                    <td className="px-5 py-4">
                      <Badge
                        label={org.billing_exempt ? 'No payment' : 'Stripe'}
                        tone={org.billing_exempt ? 'trained' : 'enrolled'}
                      />
                    </td>
                    <td className="px-5 py-4">{org.people_count}</td>
                    <td className="px-5 py-4">
                      <Badge label={org.is_active ? 'Active' : 'Suspended'} tone={org.is_active ? 'active' : 'inactive'} />
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => toggleActive(org)} className="rounded-lg border border-border px-3 py-1.5 text-xs">
                          {org.is_active ? 'Suspend' : 'Activate'}
                        </button>
                        <button type="button" onClick={() => toggleBilling(org)} className="rounded-lg border border-border px-3 py-1.5 text-xs">
                          {org.billing_exempt ? 'Require Stripe' : 'Make complimentary'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Add company" wide>
        <form onSubmit={onCreate} className="grid gap-4 md:grid-cols-2">
          <label className="block space-y-1.5 text-sm md:col-span-2">
            <span className="text-muted">Company / school name</span>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Type</span>
            <select value={form.org_type} onChange={(e) => setForm({ ...form, org_type: e.target.value as 'company' | 'school' })} className="field">
              <option value="company">Company</option>
              <option value="school">School</option>
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Plan</span>
            <select value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value as PlanId })} className="field">
              <option value="free">Free</option>
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input
              type="checkbox"
              checked={form.billing_exempt}
              onChange={(e) => setForm({ ...form, billing_exempt: e.target.checked })}
            />
            Complimentary (no Stripe payment required)
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Owner first name</span>
            <input required value={form.owner_first_name} onChange={(e) => setForm({ ...form, owner_first_name: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Owner last name</span>
            <input value={form.owner_last_name} onChange={(e) => setForm({ ...form, owner_last_name: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Owner email</span>
            <input required type="email" value={form.owner_email} onChange={(e) => setForm({ ...form, owner_email: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Owner password</span>
            <input required type="password" minLength={8} value={form.owner_password} onChange={(e) => setForm({ ...form, owner_password: e.target.value })} className="field" />
          </label>
          <div className="md:col-span-2 flex justify-end gap-3">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm">Cancel</button>
            <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
              {saving ? 'Creating...' : 'Create company'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  )
}

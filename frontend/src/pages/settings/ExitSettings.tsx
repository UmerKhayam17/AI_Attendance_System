import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { exitApi } from '../../api/services'
import { Badge } from '../../components/Badge'
import { EmptyState, Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { ExitChecklistTemplate, ExitPolicy } from '../../types'
import { Field, SettingsPageHeader, SettingsSection, StickySave, Toggle } from './SettingsUI'

const CATEGORIES: Array<ExitChecklistTemplate['category']> = ['it', 'finance', 'hr', 'access', 'assets', 'other']

export default function ExitSettingsPage() {
  const { toast } = useToast()
  const [policy, setPolicy] = useState<ExitPolicy | null>(null)
  const [items, setItems] = useState<ExitChecklistTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<ExitChecklistTemplate['category']>('hr')

  const load = useCallback(async () => {
    try {
      const [p, list] = await Promise.all([exitApi.policy(), exitApi.checklist()])
      setPolicy(p)
      setItems(list)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load exit settings', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const savePolicy = async (e: FormEvent) => {
    e.preventDefault()
    if (!policy) return
    setSaving(true)
    try {
      setPolicy(await exitApi.updatePolicy(policy))
      toast('Exit policy saved', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const addItem = async (e: FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    try {
      await exitApi.createChecklistItem({ category, title: title.trim(), sort_order: items.length, is_active: true })
      setTitle('')
      toast('Checklist item added', 'success')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not add item', 'error')
    }
  }

  if (loading || !policy) return <Loading label="Initializing exit module..." />

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Exit policy"
        description="Notice period, clearance, interview, and what happens when an exit is completed."
      />
      <form onSubmit={savePolicy} className="space-y-6">
        <SettingsSection title="Notice & completion">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Notice period (days)">
              <input type="number" min="0" value={policy.notice_period_days} onChange={(e) => setPolicy({ ...policy, notice_period_days: Number(e.target.value) })} className="field" />
            </Field>
            <Field label="Probation notice (days)">
              <input type="number" min="0" value={policy.probation_notice_days} onChange={(e) => setPolicy({ ...policy, probation_notice_days: Number(e.target.value) })} className="field" />
            </Field>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <Toggle label="Require full clearance before complete" checked={policy.require_clearance} onChange={(v) => setPolicy({ ...policy, require_clearance: v })} />
            <Toggle label="Require exit interview before complete" checked={policy.require_interview} onChange={(v) => setPolicy({ ...policy, require_interview: v })} />
            <Toggle label="Deactivate person and revoke face access on complete" checked={policy.auto_deactivate} onChange={(v) => setPolicy({ ...policy, auto_deactivate: v })} />
            <Toggle label="Allow notice-period buyout" checked={policy.allow_notice_buyout} onChange={(v) => setPolicy({ ...policy, allow_notice_buyout: v })} />
          </div>
        </SettingsSection>
        <StickySave saving={saving} label="Save exit policy" />
      </form>

      <SettingsSection title="Clearance checklist" description="These items are copied onto every new exit case.">
        <form onSubmit={addItem} className="flex flex-wrap gap-3">
          <select value={category} onChange={(e) => setCategory(e.target.value as ExitChecklistTemplate['category'])} className="field w-40">
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Laptop returned..." className="field min-w-56 flex-1" />
          <button type="submit" className="rounded-lg bg-accent px-4 py-2 text-sm text-white">Add item</button>
        </form>
        {items.length === 0 ? (
          <EmptyState title="No checklist items" description="Add IT, finance, HR, and access tasks used during offboarding." />
        ) : (
          <ul className="divide-y divide-border/70">
            {items.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-xs text-muted capitalize">{item.category}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge label={item.is_active ? 'Active' : 'Inactive'} tone={item.is_active ? 'active' : 'inactive'} />
                  <button
                    type="button"
                    className="rounded-lg border border-border px-3 py-1.5 text-xs"
                    onClick={async () => {
                      await exitApi.updateChecklistItem(item.id, { is_active: !item.is_active })
                      await load()
                    }}
                  >
                    {item.is_active ? 'Hide' : 'Show'}
                  </button>
                  <button
                    type="button"
                    className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300"
                    onClick={async () => {
                      await exitApi.deleteChecklistItem(item.id)
                      await load()
                    }}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </SettingsSection>
    </div>
  )
}

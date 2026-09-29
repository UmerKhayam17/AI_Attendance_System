import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { orgApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import { Badge } from '../../components/Badge'
import { Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { Invite, Membership, OrgRole } from '../../types'
import { Field, SettingsPageHeader, SettingsSection } from './SettingsUI'

export default function TeamSettingsPage() {
  const { role, user } = useAuth()
  const { toast } = useToast()
  const [members, setMembers] = useState<Membership[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<OrgRole>('operator')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([orgApi.members(), orgApi.invites()])
      setMembers(m)
      setInvites(i)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load team', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const onInvite = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const invite = await orgApi.invite(email, inviteRole)
      toast('Invite created', 'success')
      setEmail('')
      await navigator.clipboard?.writeText(invite.invite_url).catch(() => undefined)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Invite failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading />

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Team"
        description="Invite operators and viewers. Owners and admins can change company setup."
      />
      <form onSubmit={onInvite} className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-panel p-5">
        <Field label="Invite email" className="min-w-56 flex-1">
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="field" />
        </Field>
        <Field label="Role">
          <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as OrgRole)} className="field">
            {role === 'owner' && <option value="admin">Admin</option>}
            <option value="operator">Operator</option>
            <option value="viewer">Viewer</option>
          </select>
        </Field>
        <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
          {saving ? 'Inviting...' : 'Send invite'}
        </button>
      </form>

      <SettingsSection title="Members">
        <div className="-mx-1 divide-y divide-border/70">
          {members.map((member) => (
            <div key={member.id} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0">
              <div>
                <p className="font-medium">{member.first_name} {member.last_name} <span className="text-xs text-muted">{member.email}</span></p>
              </div>
              <div className="flex items-center gap-2">
                <Badge label={member.role} tone={member.role === 'owner' ? 'trained' : 'enrolled'} />
                {member.role !== 'owner' && member.email !== user?.email && (
                  <>
                    <select
                      value={member.role}
                      onChange={async (e) => {
                        try {
                          await orgApi.updateMember(member.id, e.target.value)
                          await load()
                        } catch (err) {
                          toast(err instanceof Error ? err.message : 'Update failed', 'error')
                        }
                      }}
                      className="rounded-lg border border-border bg-surface px-2 py-1 text-xs"
                    >
                      {role === 'owner' && <option value="admin">admin</option>}
                      <option value="operator">operator</option>
                      <option value="viewer">viewer</option>
                    </select>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await orgApi.removeMember(member.id)
                          await load()
                        } catch (err) {
                          toast(err instanceof Error ? err.message : 'Remove failed', 'error')
                        }
                      }}
                      className="text-xs text-red-300"
                    >
                      Remove
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </SettingsSection>

      <SettingsSection title="Pending invites">
        {invites.length === 0 ? (
          <p className="text-sm text-muted">No pending invites</p>
        ) : (
          <div className="divide-y divide-border/70">
            {invites.map((invite) => (
              <div key={invite.id} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0 text-sm">
                <div>
                  <p>{invite.email} · {invite.role}</p>
                  <p className="break-all text-xs text-muted">{invite.invite_url}</p>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    await orgApi.revokeInvite(invite.id)
                    await load()
                  }}
                  className="text-xs text-red-300"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </SettingsSection>
    </div>
  )
}

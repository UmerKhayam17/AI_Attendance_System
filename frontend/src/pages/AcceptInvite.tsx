import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/services'
import { useAuth } from '../auth/AuthContext'
import type { Organization } from '../types'
import { AuthShell } from './Login'

export default function AcceptInvitePage() {
  const { applyAuth } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') || ''
  const [preview, setPreview] = useState<{ email: string; role: string; organization: Organization } | null>(null)
  const [form, setForm] = useState({ first_name: '', last_name: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!token) return
    authApi.invitePreview(token).then(setPreview).catch((err) => {
      setError(err instanceof Error ? err.message : 'Invalid invite')
    })
  }, [token])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const data = await authApi.acceptInvite({ token, ...form })
      applyAuth(data)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not accept invite')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AuthShell title="Join workspace" subtitle={preview ? `${preview.organization.name} · ${preview.role}` : 'Accept your invitation'}>
      <form onSubmit={onSubmit} className="space-y-4">
        {error && <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</p>}
        {preview && <p className="text-sm text-muted">Invited as {preview.email}</p>}
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">First name</span>
          <input required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Last name</span>
          <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Password</span>
          <input required type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="field" />
        </label>
        <button type="submit" disabled={saving || !token} className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
          {saving ? 'Joining...' : 'Accept invite'}
        </button>
        <p className="text-center text-sm text-muted">
          <Link to="/login" className="hover:text-white">Already have an account?</Link>
        </p>
      </form>
    </AuthShell>
  )
}

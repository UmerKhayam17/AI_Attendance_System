import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { AuthShell } from './Login'

export default function SignupPage() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    organization_name: '',
    org_type: 'company' as 'company' | 'school',
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await signup(form)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AuthShell title="Create your workspace" subtitle="14-day Starter trial · company or school">
      <form onSubmit={onSubmit} className="space-y-4">
        {error && <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</p>}
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Organization name</span>
          <input required value={form.organization_name} onChange={(e) => setForm({ ...form, organization_name: e.target.value })} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Type</span>
          <select value={form.org_type} onChange={(e) => setForm({ ...form, org_type: e.target.value as 'company' | 'school' })} className="field">
            <option value="company">Company / office</option>
            <option value="school">School</option>
          </select>
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">First name</span>
            <input required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="field" />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Last name</span>
            <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="field" />
          </label>
        </div>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Work email</span>
          <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Password</span>
          <input required type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="field" />
        </label>
        <button type="submit" disabled={saving} className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
          {saving ? 'Creating...' : 'Start trial'}
        </button>
        <p className="text-center text-sm text-muted">
          Already have an account? <Link to="/login" className="text-white hover:underline">Sign in</Link>
        </p>
      </form>
    </AuthShell>
  )
}

import { type FormEvent, type ReactNode, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const from = (location.state as { from?: string } | null)?.from || '/'

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const user = await login(email, password)
      const fallback = user.is_superadmin ? '/platform' : '/'
      const dest = from && from !== '/' && !from.startsWith('/platform') && user.is_superadmin
        ? '/platform'
        : user.is_superadmin
          ? '/platform'
          : from || fallback
      navigate(dest, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AuthShell title="Sign in" subtitle="Access your AI Attendance workspace">
      <form onSubmit={onSubmit} className="space-y-4">
        {error && <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</p>}
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Email</span>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Password</span>
          <input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="field" />
        </label>
        <button type="submit" disabled={saving} className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
          {saving ? 'Signing in...' : 'Sign in'}
        </button>
        <div className="flex justify-between text-sm text-muted">
          <Link to="/forgot-password" className="hover:text-white">Forgot password?</Link>
          <Link to="/signup" className="hover:text-white">Create organization</Link>
        </div>
      </form>
    </AuthShell>
  )
}

export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface p-6">
      <div className="w-full max-w-md rounded-2xl border border-border bg-panel p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/20 text-accent">AI</div>
          <div>
            <h1 className="text-lg font-semibold">{title}</h1>
            <p className="text-xs text-muted">{subtitle}</p>
          </div>
        </div>
        {children}
      </div>
    </div>
  )
}

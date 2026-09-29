import { type FormEvent, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/services'
import { AuthShell } from './Login'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const uid = params.get('uid') || ''
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await authApi.passwordResetConfirm(uid, token, password)
      navigate('/login', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AuthShell title="Choose a new password" subtitle="Use the link from your reset email">
      <form onSubmit={onSubmit} className="space-y-4">
        {error && <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</p>}
        {!uid || !token ? <p className="text-sm text-amber-200">This reset link is missing parameters.</p> : null}
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">New password</span>
          <input required type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className="field" />
        </label>
        <button type="submit" disabled={saving || !uid || !token} className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
          {saving ? 'Updating...' : 'Update password'}
        </button>
        <p className="text-center text-sm text-muted">
          <Link to="/login" className="hover:text-white">Back to sign in</Link>
        </p>
      </form>
    </AuthShell>
  )
}

import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/services'
import { AuthShell } from './Login'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [debugLink, setDebugLink] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const result = await authApi.passwordReset(email)
      setMessage(result.detail)
      setDebugLink(result.debug_link || null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AuthShell title="Reset password" subtitle="We'll email a reset link (printed in the backend console in development)">
      <form onSubmit={onSubmit} className="space-y-4">
        {error && <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</p>}
        {message && <p className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-100">{message}</p>}
        {debugLink && (
          <p className="break-all text-xs text-muted">
            Dev link: <Link to={debugLink.replace(/^https?:\/\/[^/]+/, '')} className="text-accent">{debugLink}</Link>
          </p>
        )}
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Email</span>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="field" />
        </label>
        <button type="submit" disabled={saving} className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
          {saving ? 'Sending...' : 'Send reset link'}
        </button>
        <p className="text-center text-sm text-muted">
          <Link to="/login" className="hover:text-white">Back to sign in</Link>
        </p>
      </form>
    </AuthShell>
  )
}

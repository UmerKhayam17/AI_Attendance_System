import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { visitorApi } from '../api/services'
import { Badge } from '../components/Badge'
import { Loading } from '../components/Modal'
import { AuthShell } from './Login'
import type { PublicVisit, VisitStatus } from '../types'

function statusTone(status: VisitStatus) {
  if (status === 'checked_in') return 'present' as const
  if (status === 'expected') return 'pending' as const
  if (status === 'checked_out') return 'enrolled' as const
  return 'absent' as const
}

function formatWhen(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function VisitorGatePage() {
  const { token = '' } = useParams()
  const [visit, setVisit] = useState<PublicVisit | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setVisit(await visitorApi.gate(token))
      setError(null)
    } catch (err) {
      setVisit(null)
      setError(err instanceof Error ? err.message : 'Visit not found')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  const act = async (action: 'check_in' | 'check_out') => {
    setBusy(true)
    setError(null)
    try {
      setVisit(await visitorApi.gateAction(token, action))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update visit')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading label="Loading visit..." />

  if (!visit) {
    return (
      <AuthShell title="Visitor gate" subtitle="This check-in link is invalid or expired">
        <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error || 'Visit not found'}
        </p>
      </AuthShell>
    )
  }

  return (
    <AuthShell title={visit.organization_name} subtitle="Visitor self check-in">
      <div className="space-y-4">
        {error ? (
          <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</p>
        ) : null}
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xl font-semibold">{visit.visitor_name}</p>
            <p className="text-sm text-muted">
              {[visit.visitor_company, visit.purpose_label, visit.branch_name].filter(Boolean).join(' · ')}
            </p>
          </div>
          <Badge label={visit.status_label} tone={statusTone(visit.status)} />
        </div>
        <dl className="grid gap-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Host</dt>
            <dd>{visit.host_name || '—'}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Expected</dt>
            <dd>{formatWhen(visit.expected_at)}</dd>
          </div>
          {visit.check_in_at ? (
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Checked in</dt>
              <dd>{formatWhen(visit.check_in_at)}</dd>
            </div>
          ) : null}
          {visit.badge_code ? (
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Badge</dt>
              <dd className="font-mono">{visit.badge_code}</dd>
            </div>
          ) : null}
        </dl>
        {visit.status === 'expected' ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => act('check_in')}
            className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
          >
            {busy ? 'Checking in…' : 'Check in'}
          </button>
        ) : null}
        {visit.status === 'checked_in' ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => act('check_out')}
            className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
          >
            {busy ? 'Checking out…' : 'Check out'}
          </button>
        ) : null}
        {visit.status !== 'expected' && visit.status !== 'checked_in' ? (
          <p className="text-center text-sm text-muted">This visit is {visit.status_label.toLowerCase()}.</p>
        ) : null}
      </div>
    </AuthShell>
  )
}

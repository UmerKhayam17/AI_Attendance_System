import { useCallback, useEffect, useState } from 'react'
import { employeeApi, recognitionApi } from '../api/services'
import { mediaUrl } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { canOperate } from '../auth/roles'
import { AuthImage } from '../components/AuthImage'
import { Badge } from '../components/Badge'
import { EmptyState, Loading } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { Employee, RecognitionEvent } from '../types'

const KINDS = [
  { id: 'all', label: 'All' },
  { id: 'unknown', label: 'Unknown' },
  { id: 'spoof', label: 'Spoof' },
  { id: 'anomaly', label: 'Anomaly' },
  { id: 'recognized', label: 'Recognized' },
  { id: 'camera', label: 'Cameras' },
] as const

function kindTone(kind: RecognitionEvent['kind']) {
  if (kind === 'recognized') return 'present' as const
  if (kind === 'spoof' || kind === 'camera') return 'absent' as const
  if (kind === 'anomaly') return 'late' as const
  return 'pending' as const
}

function todayIso() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export default function EventsPage() {
  const { toast } = useToast()
  const { role } = useAuth()
  const operate = canOperate(role)
  const [rows, setRows] = useState<RecognitionEvent[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [kind, setKind] = useState<(typeof KINDS)[number]['id']>('unknown')
  const [status, setStatus] = useState<'open' | 'all'>('open')
  const [date, setDate] = useState(todayIso())
  const [allDates, setAllDates] = useState(false)
  const [loading, setLoading] = useState(true)
  const [assign, setAssign] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState<number | 'all' | null>(null)

  const load = useCallback(async () => {
    try {
      const [events, people] = await Promise.all([
        recognitionApi.events({
          kind,
          status: kind === 'recognized' ? 'all' : status,
          date: allDates ? undefined : date,
        }),
        employeeApi.list(),
      ])
      setRows(events)
      setEmployees(people.filter((e) => e.is_active))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load events', 'error')
    } finally {
      setLoading(false)
    }
  }, [allDates, date, kind, status, toast])

  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  if (loading && rows.length === 0) return <Loading label="Loading events..." />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Events</h2>
          <p className="text-sm text-muted">
            Each card is one camera sighting of a face that is not in your enrolled staff — not a headcount.
            Guests, delivery, and the same person walking past again all add events.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} className="field w-40">
            {KINDS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value as 'open' | 'all')} className="field w-36">
            <option value="open">Open</option>
            <option value="all">All</option>
          </select>
          <input
            type="date"
            value={date}
            disabled={allDates}
            onChange={(e) => setDate(e.target.value)}
            className="field w-40"
          />
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={allDates} onChange={(e) => setAllDates(e.target.checked)} />
            All dates
          </label>
          {operate && rows.length > 0 && status === 'open' ? (
            <button
              type="button"
              disabled={busy === 'all'}
              onClick={async () => {
                if (!window.confirm(`Dismiss ${rows.length} open event${rows.length === 1 ? '' : 's'} in this view?`)) return
                setBusy('all')
                try {
                  const res = await recognitionApi.dismissAllEvents({
                    kind,
                    status: 'open',
                    date: allDates ? undefined : date,
                  })
                  toast(`Dismissed ${res.dismissed} events`, 'success')
                  await load()
                } catch (err) {
                  toast(err instanceof Error ? err.message : 'Dismiss failed', 'error')
                } finally {
                  setBusy(null)
                }
              }}
              className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-surface"
            >
              Dismiss all
            </button>
          ) : null}
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No events" description="Unknown faces, spoofs, and camera alerts will appear here." />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {rows.map((row) => {
            const src = row.image_url ? mediaUrl(row.image_url) : ''
            return (
              <article key={row.id} className="overflow-hidden rounded-xl border border-border bg-panel">
                {src ? (
                  <div className="aspect-video bg-black">
                    <AuthImage url={src} alt={row.message} className="h-full w-full object-cover" />
                  </div>
                ) : null}
                <div className="space-y-3 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{row.employee_name || row.message || row.kind}</p>
                    <Badge label={row.kind.replace('_', ' ')} tone={kindTone(row.kind)} />
                  </div>
                  <p className="text-xs text-muted">
                    {new Date(row.detected_at).toLocaleString()}
                    {row.camera_name ? ` · ${row.camera_name}` : ''}
                    {row.confidence ? ` · ${(row.confidence * 100).toFixed(0)}%` : ''}
                    {` · ${row.status}`}
                  </p>
                  {row.status === 'open' && (row.kind === 'unknown' || row.kind === 'anomaly') ? (
                    <div className="flex flex-wrap gap-2">
                      <select
                        value={assign[row.id] ?? ''}
                        onChange={(e) => setAssign((prev) => ({ ...prev, [row.id]: e.target.value }))}
                        className="field flex-1"
                      >
                        <option value="">Assign to person…</option>
                        {employees.map((person) => (
                          <option key={person.employee_id} value={person.employee_id}>
                            {person.first_name} {person.last_name} ({person.employee_id})
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        disabled={!assign[row.id] || busy === row.id}
                        onClick={async () => {
                          if (!assign[row.id]) return
                          setBusy(row.id)
                          try {
                            await recognitionApi.assignEvent(row.id, assign[row.id])
                            toast('Assigned and attendance written', 'success')
                            await load()
                          } catch (err) {
                            toast(err instanceof Error ? err.message : 'Assign failed', 'error')
                          } finally {
                            setBusy(null)
                          }
                        }}
                        className="rounded-lg bg-accent px-3 py-2 text-sm text-white disabled:opacity-50"
                      >
                        Assign
                      </button>
                      <button
                        type="button"
                        disabled={busy === row.id}
                        onClick={async () => {
                          setBusy(row.id)
                          try {
                            await recognitionApi.dismissEvent(row.id)
                            await load()
                          } catch (err) {
                            toast(err instanceof Error ? err.message : 'Dismiss failed', 'error')
                          } finally {
                            setBusy(null)
                          }
                        }}
                        className="rounded-lg border border-border px-3 py-2 text-sm"
                      >
                        Dismiss
                      </button>
                    </div>
                  ) : row.status === 'open' ? (
                    <button
                      type="button"
                      disabled={busy === row.id}
                      onClick={async () => {
                        setBusy(row.id)
                        try {
                          await recognitionApi.dismissEvent(row.id)
                          await load()
                        } catch (err) {
                          toast(err instanceof Error ? err.message : 'Dismiss failed', 'error')
                        } finally {
                          setBusy(null)
                        }
                      }}
                      className="rounded-lg border border-border px-3 py-2 text-sm"
                    >
                      Dismiss
                    </button>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

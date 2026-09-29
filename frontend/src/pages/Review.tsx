import { useCallback, useEffect, useState } from 'react'
import { employeeApi, reviewApi } from '../api/services'
import { mediaUrl } from '../api/client'
import { AuthImage } from '../components/AuthImage'
import { Badge } from '../components/Badge'
import { EmptyState, Loading } from '../components/Modal'
import { useToast } from '../components/Toast'
import type { Employee, MatchReview } from '../types'

export default function ReviewPage() {
  const { toast } = useToast()
  const [rows, setRows] = useState<MatchReview[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'pending' | 'all'>('pending')
  const [override, setOverride] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      const [reviews, people] = await Promise.all([reviewApi.list(filter), employeeApi.list()])
      setRows(reviews)
      setEmployees(people.filter((e) => e.is_active))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load reviews', 'error')
    } finally {
      setLoading(false)
    }
  }, [filter, toast])

  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  if (loading && rows.length === 0) return <Loading label="Loading review queue..." />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Review Management</h2>
          <p className="text-sm text-muted">Confirm or reject low-confidence and ambiguous CCTV matches.</p>
        </div>
        <select value={filter} onChange={(e) => setFilter(e.target.value as 'pending' | 'all')} className="field w-40">
          <option value="pending">Pending</option>
          <option value="all">All</option>
        </select>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="Queue is empty" description="Near-miss recognitions will appear here instead of writing attendance." />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {rows.map((row) => {
            const src = row.image_url ? mediaUrl(row.image_url) : ''
            return (
              <article key={row.id} className="overflow-hidden rounded-xl border border-border bg-panel">
                <div className="aspect-video bg-black">
                  {src ? (
                    <AuthImage url={src} alt={row.suggested_employee_id} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-muted">No image</div>
                  )}
                </div>
                <div className="space-y-3 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{row.employee_name || row.suggested_employee_id || 'Unknown'}</p>
                    <Badge label={row.status} tone={row.status === 'confirmed' ? 'present' : row.status === 'rejected' ? 'absent' : 'pending'} />
                  </div>
                  <p className="text-xs text-muted">
                    {(row.confidence * 100).toFixed(0)}% · {row.reason.replace('_', ' ')}
                    {row.camera_name ? ` · ${row.camera_name}` : ''}
                    {row.track_id != null ? ` · track #${row.track_id}` : ''}
                  </p>
                  {row.status === 'pending' ? (
                    <>
                      <select
                        value={override[row.id] ?? row.suggested_employee_id}
                        onChange={(e) => setOverride((prev) => ({ ...prev, [row.id]: e.target.value }))}
                        className="field"
                      >
                        {employees.map((emp) => (
                          <option key={emp.id} value={emp.employee_id}>
                            {emp.employee_id} — {emp.first_name} {emp.last_name}
                          </option>
                        ))}
                      </select>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={busy === row.id}
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs text-white disabled:opacity-50"
                          onClick={async () => {
                            setBusy(row.id)
                            try {
                              await reviewApi.confirm(row.id, override[row.id] || row.suggested_employee_id)
                              toast('Match confirmed', 'success')
                              await load()
                            } catch (err) {
                              toast(err instanceof Error ? err.message : 'Confirm failed', 'error')
                            } finally {
                              setBusy(null)
                            }
                          }}
                        >
                          Confirm attendance
                        </button>
                        <button
                          type="button"
                          disabled={busy === row.id}
                          className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300 disabled:opacity-50"
                          onClick={async () => {
                            setBusy(row.id)
                            try {
                              await reviewApi.reject(row.id)
                              toast('Match rejected', 'info')
                              await load()
                            } catch (err) {
                              toast(err instanceof Error ? err.message : 'Reject failed', 'error')
                            } finally {
                              setBusy(null)
                            }
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-muted">
                      {row.attendance_action || row.status}
                      {row.reviewed_by_email ? ` · ${row.reviewed_by_email}` : ''}
                    </p>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

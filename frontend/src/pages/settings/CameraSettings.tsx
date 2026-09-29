import { useCallback, useEffect, useState } from 'react'
import { recognitionApi } from '../../api/services'
import { useAuth } from '../../auth/AuthContext'
import { Badge } from '../../components/Badge'
import { CameraFormModal, zoneLabel } from '../../components/CameraFormModal'
import { EmptyState, Loading } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import type { Camera } from '../../types'
import { SettingsPageHeader } from './SettingsUI'

export default function CameraSettingsPage() {
  const { organization } = useAuth()
  const { toast } = useToast()
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Camera | null>(null)
  const quota = organization?.limits.cameras ?? 0

  const load = useCallback(async () => {
    try {
      setCameras(await recognitionApi.cameras())
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load cameras', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <Loading />

  return (
    <div className="space-y-4">
      <SettingsPageHeader
        title="Cameras"
        description={`${cameras.length} cameras · plan allows ${quota}. Add RTSP cameras for live CCTV recognition. Webcam monitoring works on every plan.`}
        action={
          <button
            type="button"
            onClick={() => {
              setEditing(null)
              setOpen(true)
            }}
            className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
          >
            Add camera
          </button>
        }
      />

      {cameras.length === 0 ? (
        <EmptyState title="No cameras" description="Add RTSP cameras for live CCTV recognition. Webcam monitoring works on every plan." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-panel">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Location</th>
                <th className="px-5 py-3">Branch</th>
                <th className="px-5 py-3">Zone</th>
                <th className="px-5 py-3">Health</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((camera) => (
                <tr key={camera.id} className="border-t border-border/70">
                  <td className="px-5 py-4">{camera.name}</td>
                  <td className="px-5 py-4 text-muted">{camera.location || '—'}</td>
                  <td className="px-5 py-4 text-muted">{camera.branch_name || '—'}</td>
                  <td className="px-5 py-4">
                    <Badge label={zoneLabel(camera.zone)} tone="enrolled" />
                  </td>
                  <td className="px-5 py-4">
                    <Badge
                      label={camera.health || camera.health_status || 'stopped'}
                      tone={
                        (camera.health || camera.health_status) === 'online'
                          ? 'active'
                          : (camera.health || camera.health_status) === 'degraded'
                            ? 'late'
                            : (camera.health || camera.health_status) === 'offline'
                              ? 'absent'
                              : 'inactive'
                      }
                    />
                    {camera.fps ? <span className="ml-2 text-xs text-muted">{camera.fps.toFixed(1)} fps</span> : null}
                    {camera.last_error ? <p className="mt-1 text-xs text-red-300">{camera.last_error}</p> : null}
                  </td>
                  <td className="px-5 py-4">
                    <Badge label={camera.is_active ? 'Active' : 'Inactive'} tone={camera.is_active ? 'active' : 'inactive'} />
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="rounded-lg border border-border px-3 py-1.5 text-xs"
                        onClick={() => {
                          setEditing(camera)
                          setOpen(true)
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-300"
                        onClick={async () => {
                          if (!confirm(`Delete ${camera.name}?`)) return
                          await recognitionApi.deleteCamera(camera.id)
                          await load()
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CameraFormModal open={open} onClose={() => setOpen(false)} editing={editing} onSaved={load} />
    </div>
  )
}

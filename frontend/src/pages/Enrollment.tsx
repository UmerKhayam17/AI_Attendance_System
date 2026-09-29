import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { employeeApi, recognitionApi } from '../api/services'
import { mediaUrl } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { EmptyState, Loading } from '../components/Modal'
import { useToast } from '../components/Toast'
import { useCamera } from '../hooks/useCamera'
import type { Employee, EnrollmentDetail } from '../types'

const REQUIRED = 5

export default function EnrollmentPage() {
  const { labels } = useAuth()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [employees, setEmployees] = useState<Employee[]>([])
  const [selectedId, setSelectedId] = useState(searchParams.get('employee') || '')
  const [enrollment, setEnrollment] = useState<EnrollmentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [capturing, setCapturing] = useState(false)
  const [training, setTraining] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const { videoRef, canvasRef, active, error, start, stop, captureBase64 } = useCamera()

  const selectedEmployee = useMemo(
    () => employees.find((e) => e.employee_id === selectedId) ?? null,
    [employees, selectedId],
  )

  const loadEmployees = useCallback(async () => {
    try {
      const list = await employeeApi.list()
      setEmployees(list.filter((e) => e.is_active))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load employees', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  const loadEnrollment = useCallback(async () => {
    if (!selectedId) {
      setEnrollment(null)
      return
    }
    try {
      setEnrollment(await recognitionApi.enrollmentStatus(selectedId))
    } catch {
      setEnrollment(null)
    }
  }, [selectedId])

  useEffect(() => {
    loadEmployees()
  }, [loadEmployees])

  useEffect(() => {
    if (selectedId) {
      setSearchParams({ employee: selectedId })
      loadEnrollment()
      start()
    } else {
      stop()
      setEnrollment(null)
    }
    return () => stop()
  }, [selectedId, loadEnrollment, setSearchParams, start, stop])

  const addLog = (message: string) => {
    setLogs((prev) => [message, ...prev].slice(0, 20))
  }

  const handleCapture = async () => {
    if (!selectedId) return
    const image = captureBase64(0.85, 640)
    if (!image) {
      toast('Could not capture frame', 'error')
      return
    }

    setCapturing(true)
    try {
      const result = await recognitionApi.capture(selectedId, image)
      if (result.accepted) {
        addLog(`Captured image ${result.total_images} — ${result.quality?.message}`)
        toast(`Captured ${result.total_images}/${REQUIRED}`, 'success')
        await loadEnrollment()
      } else {
        const msg = result.quality?.message || 'Capture rejected'
        addLog(msg)
        toast(msg, 'error')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Capture failed'
      addLog(msg)
      toast(msg, 'error')
    } finally {
      setCapturing(false)
    }
  }

  const handleTrain = async () => {
    if (!selectedId) return
    setTraining(true)
    try {
      const result = await recognitionApi.train(selectedId)
      addLog(`Training complete — ${result.images_used} images used`)
      toast('Embeddings trained successfully', 'success')
      setEnrollment(result.enrollment)
      await loadEmployees()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Training failed', 'error')
    } finally {
      setTraining(false)
    }
  }

  if (loading) return <Loading />

  const progress = Math.min(100, ((enrollment?.total_images ?? 0) / REQUIRED) * 100)
  const profile = mediaUrl(enrollment?.profile_image)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Enrollment Management</h2>
        <p className="text-sm text-muted">
          Capture {REQUIRED}+ live face images (not a photo of a photo), then train embeddings.
          Matching uses every captured pose, not a single averaged vector.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
        <section className="rounded-xl border border-border bg-panel p-4">
          <label className="mb-2 block text-sm text-muted">Select {labels.person}</label>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="field"
          >
            <option value="">Choose {labels.person.toLowerCase()}...</option>
            {employees.map((emp) => (
              <option key={emp.id} value={emp.employee_id}>
                {emp.employee_id} — {emp.first_name} {emp.last_name}
              </option>
            ))}
          </select>

          {selectedEmployee && (
            <div className="mt-4 space-y-3 rounded-lg bg-surface p-4">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 overflow-hidden rounded-full bg-panel">
                  {profile ? (
                    <img src={profile} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-muted">
                      {selectedEmployee.first_name[0]}
                    </div>
                  )}
                </div>
                <div>
                  <p className="font-medium">
                    {selectedEmployee.first_name} {selectedEmployee.last_name}
                  </p>
                  <p className="text-xs text-muted">{selectedEmployee.department_name || 'Unassigned'}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge
                  label={enrollment?.is_trained ? 'Trained' : enrollment?.is_enrolled ? 'Enrolled' : 'Pending'}
                  tone={enrollment?.is_trained ? 'trained' : enrollment?.is_enrolled ? 'enrolled' : 'pending'}
                />
                <span className="text-xs text-muted">
                  {enrollment?.total_images ?? 0}/{REQUIRED} images
                  {typeof enrollment?.embeddings_count === 'number' && enrollment.is_trained
                    ? ` · ${enrollment.embeddings_count} embeddings`
                    : ''}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-border">
                <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}
        </section>

        {!selectedId ? (
          <EmptyState
            title={`Select a ${labels.person.toLowerCase()}`}
            description={`Choose a ${labels.person.toLowerCase()} from the list to start webcam face enrollment.`}
          />
        ) : (
          <section className="space-y-4">
            <div className="overflow-hidden rounded-xl border border-border bg-black">
              <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />
              <canvas ref={canvasRef} hidden />
            </div>

            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            )}

            {!active && !error && (
              <button
                type="button"
                onClick={start}
                className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
              >
                Start Camera
              </button>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleCapture}
                disabled={!active || capturing}
                className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {capturing ? 'Capturing...' : 'Capture Face'}
              </button>
              <button
                type="button"
                onClick={handleTrain}
                disabled={(enrollment?.total_images ?? 0) < REQUIRED || training}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {training ? 'Training...' : 'Train Embeddings'}
              </button>
              <button
                type="button"
                onClick={loadEnrollment}
                className="rounded-lg border border-border px-4 py-2 text-sm"
              >
                Refresh Status
              </button>
            </div>

            <div className="rounded-xl border border-border bg-panel p-4">
              <h3 className="mb-3 text-sm font-medium">Capture Log</h3>
              {logs.length === 0 ? (
                <p className="text-sm text-muted">No captures yet. Position face in frame and capture.</p>
              ) : (
                <ul className="space-y-2 text-sm text-muted">
                  {logs.map((log, i) => (
                    <li key={`${log}-${i}`}>• {log}</li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

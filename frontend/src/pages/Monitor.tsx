import { useCallback, useEffect, useRef, useState } from 'react'
import { mediaUrl } from '../api/client'
import { recognitionApi } from '../api/services'
import { AuthImage } from '../components/AuthImage'
import { Badge } from '../components/Badge'
import { CameraFormModal } from '../components/CameraFormModal'
import { EmptyState } from '../components/Modal'
import { useToast } from '../components/Toast'
import { useCamera } from '../hooks/useCamera'
import { usePolling } from '../hooks/usePolling'
import type { Camera, CameraDwell, CCTVEvent, CCTVOverview, DetectionSnapshot, IdentifyResult } from '../types'

type Mode = 'cctv' | 'webcam'

export default function MonitorPage() {
  const { toast } = useToast()
  const [mode, setMode] = useState<Mode>('cctv')
  const [overview, setOverview] = useState<CCTVOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [monitoring, setMonitoring] = useState(false)
  const [markAttendance, setMarkAttendance] = useState(true)
  const [intervalSec, setIntervalSec] = useState(3)
  const [lastResult, setLastResult] = useState<IdentifyResult | null>(null)
  const [history, setHistory] = useState<Array<IdentifyResult & { time: string }>>([])
  const scanningRef = useRef(false)
  const { videoRef, canvasRef, active, error, start, stop, captureBase64 } = useCamera()

  const loadCctv = useCallback(async () => {
    try {
      const data = await recognitionApi.cctvOverview()
      setOverview(data)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load CCTV status', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  usePolling(loadCctv, 2000, mode === 'cctv')

  useEffect(() => {
    if (mode === 'webcam') {
      start()
      return () => stop()
    }
    stop()
  }, [mode, start, stop])

  const startAll = async () => {
    setBusy(true)
    try {
      await recognitionApi.cctvStartAll()
      toast('All CCTV cameras started', 'success')
      await loadCctv()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to start cameras', 'error')
    } finally {
      setBusy(false)
    }
  }

  const stopAll = async () => {
    setBusy(true)
    try {
      await recognitionApi.cctvStopAll()
      toast('All CCTV cameras stopped', 'info')
      await loadCctv()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to stop cameras', 'error')
    } finally {
      setBusy(false)
    }
  }

  const toggleCamera = async (camera: Camera) => {
    setBusy(true)
    try {
      if (camera.runtime?.running) {
        await recognitionApi.cameraStop(camera.id)
        toast(`${camera.name} stopped`, 'info')
      } else {
        await recognitionApi.cameraStart(camera.id)
        toast(`${camera.name} started`, 'success')
      }
      await loadCctv()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Camera action failed', 'error')
    } finally {
      setBusy(false)
    }
  }

  const scan = useCallback(async () => {
    if (scanningRef.current) return
    const image = captureBase64(0.85)
    if (!image) return

    scanningRef.current = true
    try {
      const result = await recognitionApi.identify(image, markAttendance, 'webcam')
      setLastResult(result)
      setHistory((prev) => [{ ...result, time: new Date().toLocaleTimeString() }, ...prev].slice(0, 15))

      if (result.matched && result.attendance?.action === 'check_in') {
        toast(`${result.employee_id} checked in`, 'success')
      } else if (result.matched && result.attendance?.action === 'check_out') {
        toast(`${result.employee_id} checked out`, 'success')
      } else if (result.matched && result.attendance?.action === 'pending') {
        toast(result.attendance.message, 'info')
      } else if (result.attendance?.action === 'review') {
        toast(result.attendance.message, 'info')
      } else if (result.liveness && !result.liveness.passed) {
        toast(result.message, 'error')
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Scan failed', 'error')
    } finally {
      scanningRef.current = false
    }
  }, [captureBase64, markAttendance, toast])

  useEffect(() => {
    if (!monitoring || mode !== 'webcam') return
    scan()
    const id = window.setInterval(scan, intervalSec * 1000)
    return () => window.clearInterval(id)
  }, [monitoring, intervalSec, scan, mode])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Live Monitor</h2>
          <p className="text-sm text-muted">
            CCTV RTSP recognition and webcam fallback for attendance.
          </p>
        </div>
        <div className="flex rounded-lg border border-border bg-panel p-1">
          <button
            type="button"
            onClick={() => setMode('cctv')}
            className={`rounded-md px-4 py-2 text-sm ${mode === 'cctv' ? 'bg-accent text-white' : 'text-muted'}`}
          >
            CCTV Cameras
          </button>
          <button
            type="button"
            onClick={() => setMode('webcam')}
            className={`rounded-md px-4 py-2 text-sm ${mode === 'webcam' ? 'bg-accent text-white' : 'text-muted'}`}
          >
            Webcam
          </button>
        </div>
      </div>

      {mode === 'cctv' ? (
        <CctvPanel
          overview={overview}
          loading={loading}
          busy={busy}
          onStartAll={startAll}
          onStopAll={stopAll}
          onToggle={toggleCamera}
          onSaved={loadCctv}
        />
      ) : (
        <WebcamPanel
          videoRef={videoRef}
          canvasRef={canvasRef}
          active={active}
          error={error}
          monitoring={monitoring}
          setMonitoring={setMonitoring}
          markAttendance={markAttendance}
          setMarkAttendance={setMarkAttendance}
          intervalSec={intervalSec}
          setIntervalSec={setIntervalSec}
          lastResult={lastResult}
          history={history}
          onScan={scan}
        />
      )}
    </div>
  )
}

function CctvPanel({
  overview,
  loading,
  busy,
  onStartAll,
  onStopAll,
  onToggle,
  onSaved,
}: {
  overview: CCTVOverview | null
  loading: boolean
  busy: boolean
  onStartAll: () => void
  onStopAll: () => void
  onToggle: (camera: Camera) => void
  onSaved: () => void | Promise<void>
}) {
  const [addOpen, setAddOpen] = useState(false)
  const cameras = overview?.cameras ?? []
  const events = overview?.events ?? []
  const snapshots = overview?.snapshots ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
        >
          Add camera
        </button>
        <button
          type="button"
          disabled={busy || cameras.length === 0}
          onClick={onStartAll}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Start All Cameras
        </button>
        <button
          type="button"
          disabled={busy || cameras.length === 0}
          onClick={onStopAll}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Stop All
        </button>
        <span className="text-sm text-muted">
          Running: {overview?.running_count ?? 0} / {cameras.length}
        </span>
      </div>

      {loading && !overview ? (
        <p className="text-muted">Loading cameras...</p>
      ) : cameras.length === 0 ? (
        <EmptyState
          title="No cameras yet"
          description="Add an RTSP camera to start live CCTV recognition. Webcam monitoring is still available from the toggle above."
          action={
            <button
              type="button"
              onClick={() => setAddOpen(true)}
              className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
            >
              Add camera
            </button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cameras.map((camera) => (
            <CameraCard key={camera.id} camera={camera} busy={busy} onToggle={() => onToggle(camera)} />
          ))}
        </div>
      )}

      <DwellPanel dwell={overview?.dwell} />

      <section className="rounded-xl border border-border bg-panel">
        <div className="border-b border-border px-5 py-4">
          <h3 className="font-medium">Detection Snapshots</h3>
          <p className="text-xs text-muted">
            Saved when an employee is recognized, with camera number on the image.
          </p>
        </div>
        {snapshots.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-muted">
            No detection images yet. Recognized employees will appear here.
          </p>
        ) : (
          <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {snapshots.map((snap) => (
              <SnapshotCard key={snap.id} snapshot={snap} />
            ))}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-panel">
        <div className="border-b border-border px-5 py-4">
          <h3 className="font-medium">Recognition Events</h3>
        </div>
        <div className="max-h-96 overflow-y-auto divide-y divide-border/70">
          {events.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-muted">
              No events yet. Start cameras to begin recognition.
            </p>
          ) : (
            events.map((event, i) => (
              <EventRow key={`${event.time}-${event.camera_id}-${i}`} event={event} />
            ))
          )}
        </div>
      </section>

      <CameraFormModal open={addOpen} onClose={() => setAddOpen(false)} onSaved={onSaved} />
    </div>
  )
}

function SnapshotCard({ snapshot }: { snapshot: DetectionSnapshot }) {
  const src = mediaUrl(snapshot.image_url)
  const time = new Date(snapshot.detected_at).toLocaleString()

  return (
    <article className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="aspect-video bg-black">
        {src ? (
          <img
            src={src}
            alt={`${snapshot.employee_id} on ${snapshot.camera_name}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted">No image</div>
        )}
      </div>
      <div className="space-y-1 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium">{snapshot.employee_id}</p>
          <Badge label={`Cam #${snapshot.camera_id ?? '?'}`} tone="enrolled" />
        </div>
        <p className="text-xs text-muted">{snapshot.camera_name}</p>
        <p className="text-xs text-muted">
          {(snapshot.confidence * 100).toFixed(0)}%
          {snapshot.attendance_action ? ` · ${snapshot.attendance_action}` : ''}
        </p>
        <p className="text-xs text-muted">{time}</p>
      </div>
    </article>
  )
}

function CameraCard({
  camera,
  busy,
  onToggle,
}: {
  camera: Camera
  busy: boolean
  onToggle: () => void
}) {
  const runtime = camera.runtime
  const running = runtime?.running
  const connected = runtime?.connected
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!running) return
    const id = window.setInterval(() => setTick((t) => t + 1), 1500)
    return () => window.clearInterval(id)
  }, [running])

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-panel">
      <div className="relative aspect-video bg-black">
        {running && runtime?.has_snapshot ? (
          <AuthImage
            url={`${recognitionApi.cameraSnapshotUrl(camera.id)}&r=${tick}`}
            alt={camera.name}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            {running ? 'Connecting…' : 'Camera stopped'}
          </div>
        )}
        <div className="absolute left-3 top-3 flex gap-2">
          <Badge
            label={camera.health || (connected ? 'Live' : running ? 'Connecting' : 'Offline')}
            tone={
              (camera.health || (connected ? 'online' : running ? 'degraded' : 'stopped')) === 'online'
                ? 'active'
                : camera.health === 'degraded' || (running && !connected)
                  ? 'late'
                  : camera.health === 'offline'
                    ? 'absent'
                    : 'inactive'
            }
          />
          <Badge label={`#${camera.id}`} tone="enrolled" />
        </div>
      </div>
      <div className="space-y-3 p-4">
        <div>
          <p className="font-medium">{camera.name}</p>
          <p className="text-xs text-muted">
            {camera.location || 'No location'} · {camera.zone === 'entry' ? 'Entry' : camera.zone === 'exit' ? 'Exit' : camera.zone === 'interior' ? 'Interior' : 'Mixed'}
          </p>
        </div>
        {runtime?.last_error && <p className="text-xs text-red-300">{runtime.last_error}</p>}
        <div className="flex items-center justify-between gap-2 text-xs text-muted">
          <span>
            Frames: {runtime?.frames_processed ?? 0}
            {typeof runtime?.fps === 'number' ? ` · ${runtime.fps.toFixed(1)} fps` : ''}
            {typeof runtime?.gallery_size === 'number' ? ` · Gallery: ${runtime.gallery_size}` : ''}
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={onToggle}
            className={`rounded-lg px-3 py-1.5 text-xs text-white disabled:opacity-50 ${
              running ? 'bg-red-600' : 'bg-accent'
            }`}
          >
            {running ? 'Stop' : 'Start'}
          </button>
        </div>
      </div>
    </div>
  )
}

function EventRow({ event }: { event: CCTVEvent }) {
  const thumb = event.snapshot?.image_url ? mediaUrl(event.snapshot.image_url) : null

  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3 text-sm">
      <div className="flex min-w-0 items-center gap-3">
        {thumb && <img src={thumb} alt="" className="h-12 w-20 rounded object-cover" />}
        <div className="min-w-0">
          <p className="font-medium">
            {event.matched ? event.employee_id : 'Unknown'}{' '}
            <span className="text-xs font-normal text-muted">
              · Camera #{event.camera_id} · {event.camera_name}
            </span>
          </p>
          <p className="text-xs text-muted">
            {event.time}
            {event.attendance ? ` · ${event.attendance.message}` : ` · ${event.message}`}
            {typeof event.dwell_seconds === 'number' ? ` · ${formatDwell(event.dwell_seconds)} in view` : ''}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {event.attendance && (
          <Badge
            label={event.attendance.action}
            tone={event.attendance.action === 'pending' ? 'pending' : 'enrolled'}
          />
        )}
        <span className={event.matched ? 'text-emerald-400' : 'text-amber-400'}>
          {(event.confidence * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  )
}

function WebcamPanel({
  videoRef,
  canvasRef,
  active,
  error,
  monitoring,
  setMonitoring,
  markAttendance,
  setMarkAttendance,
  intervalSec,
  setIntervalSec,
  lastResult,
  history,
  onScan,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>
  canvasRef: React.RefObject<HTMLCanvasElement | null>
  active: boolean
  error: string | null
  monitoring: boolean
  setMonitoring: (v: boolean) => void
  markAttendance: boolean
  setMarkAttendance: (v: boolean) => void
  intervalSec: number
  setIntervalSec: (v: number) => void
  lastResult: IdentifyResult | null
  history: Array<IdentifyResult & { time: string }>
  onScan: () => void
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
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

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setMonitoring(true)}
            disabled={monitoring || !active}
            className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Start Monitoring
          </button>
          <button
            type="button"
            onClick={() => setMonitoring(false)}
            disabled={!monitoring}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Stop
          </button>
          <button
            type="button"
            onClick={onScan}
            disabled={!active}
            className="rounded-lg border border-border px-4 py-2 text-sm"
          >
            Scan Now
          </button>
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={markAttendance}
              onChange={(e) => setMarkAttendance(e.target.checked)}
            />
            Mark attendance
          </label>
          <label className="flex items-center gap-2 text-sm text-muted">
            Interval
            <select
              value={intervalSec}
              onChange={(e) => setIntervalSec(Number(e.target.value))}
              className="rounded-lg border border-border bg-panel px-2 py-1"
            >
              {[2, 3, 5, 10].map((n) => (
                <option key={n} value={n}>
                  {n}s
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="space-y-4">
        <div className="rounded-xl border border-border bg-panel p-5">
          <p className="text-sm text-muted">Latest Result</p>
          {!lastResult ? (
            <p className="mt-3 text-muted">Waiting for scan...</p>
          ) : (
            <div className="mt-3 space-y-3">
              <p className={`text-2xl font-semibold ${lastResult.matched ? 'text-emerald-400' : 'text-amber-400'}`}>
                {lastResult.matched ? lastResult.employee_id : lastResult.message}
              </p>
              <p className="text-sm text-muted">Confidence: {(lastResult.confidence * 100).toFixed(1)}%</p>
              {lastResult.attendance && (
                <div className="rounded-lg bg-surface p-3 text-sm">
                  <p>{lastResult.attendance.message}</p>
                  <div className="mt-2 flex gap-2">
                    {lastResult.attendance.status ? (
                      <Badge
                        label={lastResult.attendance.status}
                        tone={lastResult.attendance.status as 'present' | 'late'}
                      />
                    ) : null}
                    <Badge
                      label={lastResult.attendance.action}
                      tone={lastResult.attendance.action === 'pending' ? 'pending' : 'enrolled'}
                    />
                  </div>
                </div>
              )}
              {lastResult.liveness && !lastResult.liveness.passed ? (
                <p className="text-sm text-red-300">{lastResult.liveness.message}</p>
              ) : null}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-panel">
          <div className="border-b border-border px-5 py-4">
            <h3 className="font-medium">Scan History</h3>
          </div>
          <div className="max-h-80 overflow-y-auto divide-y divide-border/70">
            {history.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-muted">No scans yet</p>
            ) : (
              history.map((item, i) => (
                <div key={`${item.time}-${i}`} className="flex items-center justify-between px-5 py-3 text-sm">
                  <div>
                    <p className="font-medium">{item.matched ? item.employee_id : 'Unknown'}</p>
                    <p className="text-xs text-muted">{item.time}</p>
                  </div>
                  <span className={item.matched ? 'text-emerald-400' : 'text-amber-400'}>
                    {(item.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

function formatDwell(seconds: number) {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`
  return `${m}:${String(sec).padStart(2, '0')}`
}

function DwellPanel({
  dwell,
}: {
  dwell?: { active: CameraDwell[]; today: Array<{ employee_id: string; employee_name: string; seconds: number }> }
}) {
  const active = dwell?.active ?? []
  const today = dwell?.today ?? []
  return (
    <section className="rounded-xl border border-border bg-panel">
      <div className="border-b border-border px-5 py-4">
        <h3 className="font-medium">Time in camera</h3>
        <p className="text-xs text-muted">
          ByteTrack keeps counting while the recognized person stays in view. A new session starts if they leave and come back.
        </p>
      </div>
      <div className="grid gap-6 p-5 lg:grid-cols-2">
        <div>
          <p className="mb-3 text-sm text-muted">On camera now</p>
          {active.length === 0 ? (
            <p className="text-sm text-muted">Nobody recognized in a live camera right now.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {active.map((row) => (
                <li key={row.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                  <span>
                    <span className="font-medium">{row.employee_name}</span>
                    <span className="text-muted"> · {row.camera_name}</span>
                  </span>
                  <span className="font-mono text-emerald-400">{formatDwell(row.seconds)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <p className="mb-3 text-sm text-muted">Today (all cameras)</p>
          {today.length === 0 ? (
            <p className="text-sm text-muted">No recognized camera time yet today.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {today.map((row) => (
                <li key={row.employee_id} className="flex items-center justify-between gap-3">
                  <span>{row.employee_name}</span>
                  <span className="font-mono text-muted">{formatDwell(row.seconds)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}

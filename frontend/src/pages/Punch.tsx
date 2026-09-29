import { useCallback, useEffect, useState } from 'react'
import { portalApi } from '../api/services'
import { Badge } from '../components/Badge'
import { Loading } from '../components/Modal'
import { useToast } from '../components/Toast'
import { useCamera } from '../hooks/useCamera'
import type { PortalPunchContext, PortalPunchResult } from '../types'

export default function PunchPage() {
  const { toast } = useToast()
  const { videoRef, canvasRef, active, error, start, stop, captureBase64 } = useCamera({ facingMode: 'user' })
  const [ctx, setCtx] = useState<PortalPunchContext | null>(null)
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null)
  const [gpsError, setGpsError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<PortalPunchResult | null>(null)

  const load = useCallback(async () => {
    try {
      setCtx(await portalApi.punchContext())
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not load punch', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
    start()
    if (!navigator.geolocation) {
      setGpsError('This browser cannot share location')
      return () => stop()
    }
    const watch = navigator.geolocation.watchPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setGpsError(null)
      },
      () => setGpsError('Allow location access so we can check you are at the branch'),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 5000 },
    )
    return () => {
      navigator.geolocation.clearWatch(watch)
      stop()
    }
  }, [load, start, stop])

  const punch = async () => {
    if (!coords) {
      toast('Waiting for GPS…', 'error')
      return
    }
    const image = captureBase64(0.85, 640)
    if (!image) {
      toast('Could not capture a frame. Check the camera.', 'error')
      return
    }
    setSaving(true)
    try {
      const next = await portalApi.punch({ image, latitude: coords.lat, longitude: coords.lng })
      setResult(next)
      toast(next.attendance.message, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Punch failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading label="Opening camera punch..." />

  const fence = ctx?.geofence
  const distance =
    coords && fence?.enabled && fence.latitude != null && fence.longitude != null
      ? approxMeters(coords.lat, coords.lng, fence.latitude, fence.longitude)
      : null
  const inside = distance == null || fence?.radius_m == null ? null : distance <= fence.radius_m

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Camera punch</h2>
        <p className="text-sm text-muted">
          Use your phone camera. Face recognition marks check-in or check-out
          {fence?.enabled ? ` inside ${fence.radius_m} m of ${fence.branch_name}.` : '.'}
        </p>
      </div>

      {!ctx?.trained ? (
        <p className="rounded-xl border border-amber-500/30 bg-amber-950/20 px-4 py-3 text-sm text-amber-200">
          Your face is not enrolled yet. Ask HR to capture enrollment photos before you can punch.
        </p>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-border bg-black">
        <video ref={videoRef} autoPlay playsInline muted className="aspect-[3/4] w-full object-cover sm:aspect-video" />
        <canvas ref={canvasRef} className="hidden" />
      </div>
      {error ? <p className="text-sm text-red-300">{error}</p> : null}
      {gpsError ? <p className="text-sm text-amber-200">{gpsError}</p> : null}

      <div className="flex flex-wrap items-center gap-2 text-sm">
        {active ? <Badge label="Camera on" tone="present" /> : <Badge label="Camera off" tone="inactive" />}
        {coords ? (
          <Badge
            label={
              inside === false
                ? `Outside fence · ${Math.round(distance || 0)} m`
                : fence?.enabled
                  ? `On site · ${Math.round(distance || 0)} m`
                  : 'GPS ready'
            }
            tone={inside === false ? 'absent' : 'present'}
          />
        ) : (
          <Badge label="Locating…" tone="pending" />
        )}
      </div>

      <button
        type="button"
        disabled={saving || !active || !coords || !ctx?.trained}
        onClick={punch}
        className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
      >
        {saving ? 'Recognizing…' : 'Punch with selfie'}
      </button>

      {result ? (
        <div className="rounded-xl border border-border bg-panel p-4 text-sm">
          <p className="font-medium">{result.attendance.message}</p>
          <p className="mt-1 text-muted">
            {result.attendance.status} · {(result.confidence * 100).toFixed(0)}% match · {result.attendance.source}
          </p>
        </div>
      ) : null}
    </div>
  )
}

function approxMeters(lat1: number, lon1: number, lat2: number, lon2: number) {
  const r = 6371000
  const toRad = (d: number) => (d * Math.PI) / 180
  const dlat = toRad(lat2 - lat1)
  const dlon = toRad(lon2 - lon1)
  const a =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dlon / 2) ** 2
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(a)))
}

import { useCallback, useEffect, useRef, useState } from 'react'

export function useCamera(options?: { facingMode?: 'user' | 'environment' }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [active, setActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const facingMode = options?.facingMode ?? 'user'

  const start = useCallback(async () => {
    try {
      setError(null)
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode, width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
      setActive(true)
    } catch {
      setError('Camera access denied or unavailable')
      setActive(false)
    }
  }, [facingMode])

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setActive(false)
  }, [])

  const captureBase64 = useCallback((quality = 0.85, maxWidth = 640): string | null => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !video.videoWidth) return null

    const scale = Math.min(1, maxWidth / video.videoWidth)
    canvas.width = Math.round(video.videoWidth * scale)
    canvas.height = Math.round(video.videoHeight * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', quality)
  }, [])

  useEffect(() => () => stop(), [stop])

  return { videoRef, canvasRef, active, error, start, stop, captureBase64 }
}

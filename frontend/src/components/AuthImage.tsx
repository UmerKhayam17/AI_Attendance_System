import { useEffect, useState } from 'react'
import { apiGetBlob } from '../api/client'

export function AuthImage({
  url,
  alt,
  className,
}: {
  url: string
  alt: string
  className?: string
}) {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    ;(async () => {
      try {
        const blob = await apiGetBlob(url)
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      } catch {
        if (!cancelled) setSrc(null)
      }
    })()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])

  if (!src) return null
  return <img src={src} alt={alt} className={className} />
}

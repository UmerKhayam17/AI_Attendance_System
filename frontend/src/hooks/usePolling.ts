import { useEffect, useRef } from 'react'

export function usePolling(callback: () => void | Promise<void>, intervalMs: number, enabled = true) {
  const savedCallback = useRef(callback)

  useEffect(() => {
    savedCallback.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled) return

    savedCallback.current()
    const id = window.setInterval(() => {
      savedCallback.current()
    }, intervalMs)

    return () => window.clearInterval(id)
  }, [intervalMs, enabled])
}

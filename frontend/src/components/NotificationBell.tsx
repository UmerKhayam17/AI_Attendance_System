import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { approvalApi } from '../api/services'
import type { InAppNotification } from '../types'

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState<InAppNotification[]>([])

  const load = useCallback(async () => {
    try {
      setRows(await approvalApi.notifications())
    } catch {
      setRows([])
    }
  }, [])

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 60000)
    return () => window.clearInterval(timer)
  }, [load])

  const unread = rows.filter((row) => !row.read_at).length

  return (
    <div className="relative">
      <button
        type="button"
        className="relative rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-surface"
        onClick={() => setOpen((v) => !v)}
      >
        Alerts
        {unread ? (
          <span className="absolute -right-1 -top-1 rounded-full bg-accent px-1.5 text-[10px] text-white">{unread}</span>
        ) : null}
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-80 overflow-hidden rounded-xl border border-border bg-panel shadow-xl">
          <div className="flex items-center justify-between border-b border-border px-3 py-2 text-xs text-muted">
            <span>Notifications</span>
            {unread ? (
              <button
                type="button"
                className="hover:text-white"
                onClick={async () => {
                  await approvalApi.markRead()
                  await load()
                }}
              >
                Mark all read
              </button>
            ) : null}
          </div>
          <ul className="max-h-80 overflow-y-auto text-sm">
            {rows.length === 0 ? (
              <li className="px-3 py-6 text-center text-muted">No notifications</li>
            ) : (
              rows.map((row) => (
                <li key={row.id} className={`border-b border-border/60 px-3 py-2 ${row.read_at ? 'opacity-70' : ''}`}>
                  <Link
                    to={row.link || '/'}
                    className="block hover:text-accent"
                    onClick={async () => {
                      if (!row.read_at) await approvalApi.markRead(row.id)
                      setOpen(false)
                    }}
                  >
                    <p className="font-medium">{row.title}</p>
                    <p className="text-xs text-muted">{row.body}</p>
                  </Link>
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

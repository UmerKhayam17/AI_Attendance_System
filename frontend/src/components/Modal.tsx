import { useEffect, type ReactNode } from 'react'

interface ModalProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}

export function Modal({ open, title, onClose, children, wide }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/60"
        aria-label="Close modal"
        onClick={onClose}
      />
      <div
        className={`relative z-10 max-h-[90vh] overflow-y-auto rounded-xl border border-border bg-panel shadow-2xl ${
          wide ? 'w-full max-w-3xl' : 'w-full max-w-lg'
        }`}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-muted hover:bg-surface hover:text-white"
          >
            ✕
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

interface EmptyStateProps {
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-panel/40 px-6 py-16 text-center">
      <h3 className="text-lg font-medium">{title}</h3>
      <p className="mt-2 max-w-md text-sm text-muted">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

interface LoadingProps {
  label?: string
}

export function Loading({ label = 'Loading...' }: LoadingProps) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-muted">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-muted border-t-accent" />
      <span>{label}</span>
    </div>
  )
}

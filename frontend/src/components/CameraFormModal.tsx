import { type FormEvent, useEffect, useState } from 'react'
import { recognitionApi, orgApi } from '../api/services'
import { Modal } from './Modal'
import { useToast } from './Toast'
import type { Branch, Camera, CameraFormData, CameraZone } from '../types'

export const CAMERA_ZONE_OPTIONS: Array<{ value: CameraZone; label: string; hint: string }> = [
  { value: 'mixed', label: 'Mixed', hint: 'First sight checks in, later sight checks out' },
  { value: 'entry', label: 'Entry', hint: 'Check-in only (gate / lobby in)' },
  { value: 'exit', label: 'Exit', hint: 'Check-out only (gate out)' },
  { value: 'interior', label: 'Interior', hint: 'Can check in if missed at the door; never checks out' },
]

const emptyForm: CameraFormData = {
  name: '',
  location: '',
  branch: null,
  rtsp_url: '',
  zone: 'mixed',
  is_active: true,
  sort_order: 0,
}

export function zoneLabel(zone: CameraZone | undefined) {
  return CAMERA_ZONE_OPTIONS.find((z) => z.value === zone)?.label ?? 'Mixed'
}

export function CameraFormModal({
  open,
  onClose,
  editing,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  editing?: Camera | null
  onSaved: () => void | Promise<void>
}) {
  const { toast } = useToast()
  const [form, setForm] = useState<CameraFormData>(emptyForm)
  const [branches, setBranches] = useState<Branch[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    orgApi.branches().then(setBranches).catch(() => setBranches([]))
    if (editing) {
      setForm({
        name: editing.name,
        location: editing.location,
        branch: editing.branch ?? null,
        rtsp_url: editing.rtsp_url || '',
        zone: editing.zone || 'mixed',
        is_active: editing.is_active,
        sort_order: editing.sort_order,
      })
    } else {
      setForm(emptyForm)
    }
  }, [open, editing])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        const payload = { ...form }
        if (!payload.rtsp_url) delete (payload as Partial<CameraFormData>).rtsp_url
        await recognitionApi.updateCamera(editing.id, payload)
        toast('Camera updated', 'success')
      } else {
        await recognitionApi.createCamera(form)
        toast('Camera added', 'success')
      }
      onClose()
      await onSaved()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={editing ? 'Edit camera' : 'Add camera'}>
      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Name</span>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Location</span>
          <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="field" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Branch</span>
          <select
            value={form.branch ?? ''}
            onChange={(e) => setForm({ ...form, branch: e.target.value ? Number(e.target.value) : null })}
            className="field"
          >
            <option value="">Default branch</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">Zone</span>
          <select
            value={form.zone}
            onChange={(e) => setForm({ ...form, zone: e.target.value as CameraZone })}
            className="field"
          >
            {CAMERA_ZONE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label} — {opt.hint}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="text-muted">RTSP URL</span>
          <input
            required={!editing}
            type="text"
            value={form.rtsp_url}
            onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
            className="field"
            placeholder={editing ? 'Leave blank to keep current' : 'rtsp://user:pass@host:554/...'}
          />
        </label>
        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-60">
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

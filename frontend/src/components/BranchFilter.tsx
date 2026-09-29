import { orgApi } from '../api/services'
import { useAuth } from '../auth/AuthContext'
import { useEffect, useState } from 'react'
import type { Branch } from '../types'

export function BranchFilter({
  value,
  onChange,
  allowAll = true,
  className = 'field',
}: {
  value: number | 'all'
  onChange: (value: number | 'all') => void
  allowAll?: boolean
  className?: string
}) {
  const { labels } = useAuth()
  const [branches, setBranches] = useState<Branch[]>([])

  useEffect(() => {
    orgApi.branches().then(setBranches).catch(() => setBranches([]))
  }, [])

  return (
    <select
      value={value === 'all' ? 'all' : String(value)}
      onChange={(e) => onChange(e.target.value === 'all' ? 'all' : Number(e.target.value))}
      className={className}
    >
      {allowAll ? <option value="all">All {labels.branches.toLowerCase()}</option> : null}
      {branches.map((branch) => (
        <option key={branch.id} value={branch.id}>
          {branch.name}
          {branch.is_default ? ' (default)' : ''}
        </option>
      ))}
    </select>
  )
}

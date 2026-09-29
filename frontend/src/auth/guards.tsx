import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loading } from '../components/Modal'
import { useAuth } from './AuthContext'
import type { OrgRole } from '../types'

export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <Loading label="Loading session..." />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

export function RequireRole({ roles }: { roles: OrgRole[] }) {
  const { role, loading, user } = useAuth()
  if (loading) return <Loading />
  if (user?.is_superadmin) return <Navigate to="/platform" replace />
  if (!role || role === 'superadmin' || !roles.includes(role)) return <Navigate to="/" replace />
  return <Outlet />
}

export function RequireTenant() {
  const { user, organization, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  if (user.is_superadmin) return <Navigate to="/platform" replace />
  if (!organization) return <Navigate to="/login" replace />
  return <Outlet />
}

export function RequireSuperAdmin() {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_superadmin) return <Navigate to="/" replace />
  return <Outlet />
}

export function GuestOnly() {
  const { user, loading } = useAuth()
  if (loading) return <Loading label="Loading..." />
  if (user?.is_superadmin) return <Navigate to="/platform" replace />
  if (user) return <Navigate to="/" replace />
  return <Outlet />
}

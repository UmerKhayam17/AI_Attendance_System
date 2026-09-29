import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi } from '../api/services'
import { clearTokens, getAccessToken, setTokens } from '../api/client'
import { orgLabels } from './roles'
import type { AuthResponse, AuthUser, Organization, OrgRole } from '../types'

interface AuthContextValue {
  user: AuthUser | null
  organization: Organization | null
  role: OrgRole | 'superadmin' | null
  loading: boolean
  login: (email: string, password: string) => Promise<AuthUser>
  signup: (data: {
    email: string
    password: string
    first_name: string
    last_name?: string
    organization_name: string
    org_type: 'company' | 'school'
  }) => Promise<void>
  applyAuth: (data: AuthResponse) => void
  logout: () => void
  refreshMe: () => Promise<void>
  labels: ReturnType<typeof orgLabels>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function toUser(data: AuthResponse | AuthUser): AuthUser {
  return {
    id: data.id,
    email: data.email,
    first_name: data.first_name,
    last_name: data.last_name,
    role: data.role,
    is_superadmin: Boolean(data.is_superadmin),
    organization: data.organization,
    portal_people: data.portal_people || [],
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const applyAuth = useCallback((data: AuthResponse) => {
    setTokens(data.access, data.refresh)
    setUser(toUser(data))
  }, [])

  const refreshMe = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null)
      return
    }
    const me = await authApi.me()
    setUser(me)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        if (!getAccessToken()) return
        const me = await authApi.me()
        if (!cancelled) setUser(me)
      } catch {
        clearTokens()
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await authApi.login(email, password)
      applyAuth(data)
      return toUser(data)
    },
    [applyAuth],
  )

  const signup = useCallback(
    async (data: {
      email: string
      password: string
      first_name: string
      last_name?: string
      organization_name: string
      org_type: 'company' | 'school'
    }) => {
      applyAuth(await authApi.signup(data))
    },
    [applyAuth],
  )

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      organization: user?.organization ?? null,
      role: user?.role ?? null,
      loading,
      login,
      signup,
      applyAuth,
      logout,
      refreshMe,
      labels: orgLabels(user?.organization?.org_type),
    }),
    [user, loading, login, signup, applyAuth, logout, refreshMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

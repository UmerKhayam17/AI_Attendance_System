export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, message: string, data?: unknown) {
    super(message)
    this.status = status
    this.data = data
  }
}

const ACCESS_KEY = 'aa_access'
const REFRESH_KEY = 'aa_refresh'

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens(access: string, refresh?: string) {
  localStorage.setItem(ACCESS_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

function errorMessage(data: unknown, fallback: string) {
  if (!data || typeof data !== 'object') return fallback
  const obj = data as Record<string, unknown>
  if (typeof obj.error === 'string') return obj.error
  if (typeof obj.detail === 'string') return obj.detail
  if (
    obj.quality &&
    typeof obj.quality === 'object' &&
    obj.quality &&
    'message' in obj.quality &&
    typeof (obj.quality as { message: unknown }).message === 'string'
  ) {
    return String((obj.quality as { message: unknown }).message)
  }
  for (const value of Object.values(obj)) {
    if (Array.isArray(value) && value.length && typeof value[0] === 'string') return value[0]
    if (typeof value === 'string') return value
  }
  return fallback
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  const data = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(data, response.statusText || 'Request failed'), data)
  }

  return data as T
}

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken()
  if (!refresh) return null
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const response = await fetch('/api/auth/refresh/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        })
        if (!response.ok) {
          clearTokens()
          return null
        }
        const data = (await response.json()) as { access: string; refresh?: string }
        setTokens(data.access, data.refresh)
        return data.access
      } catch {
        clearTokens()
        return null
      } finally {
        refreshPromise = null
      }
    })()
  }
  return refreshPromise
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

async function request<T>(url: string, method: Method, body?: unknown, isRetry = false): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 401 && !isRetry && !url.startsWith('/api/auth/')) {
    const next = await refreshAccessToken()
    if (next) return request<T>(url, method, body, true)
    clearTokens()
    if (!window.location.pathname.startsWith('/login')) {
      window.location.assign('/login')
    }
  }

  if (method === 'DELETE' && response.ok && response.status === 204) {
    return undefined as T
  }

  return parseResponse<T>(response)
}

export async function apiGet<T>(url: string): Promise<T> {
  return request<T>(url, 'GET')
}

export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  return request<T>(url, 'POST', body)
}

export async function apiPostForm<T>(url: string, body: FormData): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const send = async (auth?: string) => {
    const hdrs = { ...headers }
    if (auth) hdrs.Authorization = `Bearer ${auth}`
    return fetch(url, { method: 'POST', headers: hdrs, body })
  }
  let response = await send()
  if (response.status === 401) {
    const next = await refreshAccessToken()
    if (next) response = await send(next)
  }
  return parseResponse<T>(response)
}

export async function apiPut<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, 'PUT', body)
}

export async function apiPatch<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, 'PATCH', body)
}

export async function apiDelete(url: string): Promise<void> {
  await request<void>(url, 'DELETE')
}

export async function apiPublicGet<T>(url: string): Promise<T> {
  const response = await fetch(url)
  return parseResponse<T>(response)
}

export async function apiPublicPost<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return parseResponse<T>(response)
}

export async function apiGetBlob(url: string): Promise<Blob> {
  const token = getAccessToken()
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (response.status === 401) {
    const next = await refreshAccessToken()
    if (next) {
      const retry = await fetch(url, { headers: { Authorization: `Bearer ${next}` } })
      if (!retry.ok) throw new ApiError(retry.status, 'Failed to load image')
      return retry.blob()
    }
    clearTokens()
  }
  if (!response.ok) throw new ApiError(response.status, 'Failed to load file')
  return response.blob()
}

export async function apiDownload(url: string, filename: string): Promise<void> {
  const blob = await apiGetBlob(url)
  const href = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(href)
}

export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null
  if (path.startsWith('http')) return path
  return path.startsWith('/') ? path : `/media/${path}`
}

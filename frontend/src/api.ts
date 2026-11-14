export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

export function csrfToken(): string {
  return document.cookie.split('; ').find(cookie => cookie.startsWith('csrftoken='))?.split('=').slice(1).join('=') ?? ''
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body) headers.set('Content-Type', 'application/json')
  if (init.method && init.method !== 'GET') headers.set('X-CSRFToken', csrfToken())
  const response = await fetch(path, { ...init, headers, credentials: 'same-origin' })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(body.error ?? `Request failed (${response.status}).`, response.status)
  return body as T
}

export const apiGet = <T>(path: string) => apiRequest<T>(path)
export const apiPost = <T>(path: string, value: unknown = {}) => apiRequest<T>(path, { method: 'POST', body: JSON.stringify(value) })

export const BACKEND_URL = import.meta.env.DEV ? '' : 'http://127.0.0.1:8111'
const API_BASE = `${BACKEND_URL}/api`

/** Prefix a backend-relative URL (like /audio/temp/xyz.wav) with the backend origin */
export function audioUrl(path: string): string {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return `${BACKEND_URL}${path}`
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

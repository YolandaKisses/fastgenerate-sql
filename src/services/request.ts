export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

const buildUrl = (path: string) => {
  if (/^https?:\/\//.test(path)) return path
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export async function request<T = any>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const { body, ...restOptions } = options
  const init: RequestInit = {
    ...restOptions,
    headers,
  }

  if (body !== undefined) {
    headers.set('Content-Type', headers.get('Content-Type') || 'application/json')
    init.body = typeof body === 'string' ? body : JSON.stringify(body)
  }

  const res = await fetch(buildUrl(path), init)
  const text = await res.text()
  const data = text ? JSON.parse(text) : null

  if (!res.ok) {
    const message = data?.detail || data?.message || `请求失败 (${res.status})`
    throw new Error(message)
  }

  return data as T
}

export const get = <T = any>(path: string) => request<T>(path)
export const post = <T = any>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body })
export const patch = <T = any>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body })
export const del = <T = any>(path: string) => request<T>(path, { method: 'DELETE' })

export const createEventSource = (path: string) => new EventSource(buildUrl(path))

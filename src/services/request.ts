import { clearAuth, getAuthToken } from './auth'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

export const buildUrl = (path: string) => {
  if (/^https?:\/\//.test(path)) return path
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export async function request<T = any>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const { body, ...restOptions } = options
  const token = getAuthToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
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
    if (res.status === 401) {
      clearAuth()
      if (window.location.hash !== '#/login') {
        window.location.hash = '#/login'
      }
    }
    const message = data?.detail || data?.message || `请求失败 (${res.status})`
    throw new Error(message)
  }

  return data as T
}

export const get = <T = any>(path: string) => request<T>(path)
export const post = <T = any>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body })
export const patch = <T = any>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body })
export const del = <T = any>(path: string) => request<T>(path, { method: 'DELETE' })

export type SseHandlers = Record<string, (data: any) => void>

const parseSseBlock = (block: string) => {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  return { event, data: dataLines.join('\n') }
}

export async function streamSse(
  path: string,
  handlers: SseHandlers,
  options: { signal?: AbortSignal } = {},
) {
  const headers = new Headers()
  const token = getAuthToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await fetch(buildUrl(path), {
    headers,
    signal: options.signal,
  })

  if (!res.ok) {
    if (res.status === 401) {
      clearAuth()
      if (window.location.hash !== '#/login') {
        window.location.hash = '#/login'
      }
    }
    const text = await res.text()
    const data = text ? JSON.parse(text) : null
    throw new Error(data?.detail || data?.message || `请求失败 (${res.status})`)
  }

  if (!res.body) return

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        if (!block.trim() || block.trimStart().startsWith(':')) continue
        const { event, data } = parseSseBlock(block)
        if (!data) continue
        handlers[event]?.(JSON.parse(data))
      }
    }

    if (buffer.trim()) {
      const { event, data } = parseSseBlock(buffer)
      if (data) {
        handlers[event]?.(JSON.parse(data))
      }
    }
  } catch (error: any) {
    if (error?.name === 'AbortError') return
    throw error
  } finally {
    reader.releaseLock()
  }
}

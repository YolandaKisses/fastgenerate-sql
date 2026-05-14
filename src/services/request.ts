import { clearAuth, getAuthToken } from './auth'

import { buildUrl } from './config'
type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

async function handleResponseError(res: Response, text?: string) {
  if (res.status === 401) {
    clearAuth()
    if (window.location.hash !== '#/login') {
      window.location.hash = '#/login'
    }
  }

  const rawText = text ?? await res.text()
  let data: any = null
  try {
    data = rawText ? JSON.parse(rawText) : null
  } catch {
    data = null
  }
  let message = data?.message || `请求失败 (${res.status})`

  if (data?.detail) {
    if (typeof data.detail === 'string') {
      message = data.detail
    } else if (Array.isArray(data.detail)) {
      message = data.detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`).join('; ')
    } else if (typeof data.detail === 'object') {
      message = JSON.stringify(data.detail)
    }
  }
  throw new Error(message)
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
    if (body instanceof FormData) {
      init.body = body
    } else {
      headers.set('Content-Type', headers.get('Content-Type') || 'application/json')
      init.body = typeof body === 'string' ? body : JSON.stringify(body)
    }
  }

  const res = await fetch(buildUrl(path), init)
  const text = await res.text()
  let data: any = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }

  if (!res.ok) {
    await handleResponseError(res, text)
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
    await handleResponseError(res)
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

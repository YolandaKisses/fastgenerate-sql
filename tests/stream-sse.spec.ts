import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setAuthSession } from '../src/services/auth'
import { streamSse } from '../src/services/request'

describe('streamSse', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('uses fetch with bearer token and dispatches named SSE events', async () => {
    setAuthSession('token-1', {
      user_id: 'u1',
      name: '系统管理员',
      account: 'admin',
      role: 'admin',
    })
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('event: status\ndata: {"phase":"running"}\n\n'))
        controller.enqueue(encoder.encode('event: result\ndata: {"ok":true}\n\n'))
        controller.close()
      },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
      text: () => Promise.resolve(''),
    })
    vi.stubGlobal('fetch', fetchMock)
    const status = vi.fn()
    const result = vi.fn()

    await streamSse('/schema/knowledge/tasks/1/events', { status, result })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer token-1')
    expect(status).toHaveBeenCalledWith({ phase: 'running' })
    expect(result).toHaveBeenCalledWith({ ok: true })
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearAuth, getAuthToken, getCurrentUser, setAuthSession } from '../src/services/auth'
import { request } from '../src/services/request'

describe('auth client helpers', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('stores and clears token with current user', () => {
    setAuthSession('token-1', {
      user_id: 'u1',
      name: '系统管理员',
      account: 'admin',
      role: 'admin',
    })

    expect(getAuthToken()).toBe('token-1')
    expect(getCurrentUser()?.account).toBe('admin')

    clearAuth()

    expect(getAuthToken()).toBeNull()
    expect(getCurrentUser()).toBeNull()
  })

  it('adds bearer token to normal requests', async () => {
    setAuthSession('token-1', {
      user_id: 'u1',
      name: '系统管理员',
      account: 'admin',
      role: 'admin',
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('{"ok":true}'),
    })
    vi.stubGlobal('fetch', fetchMock)

    await request('/datasources/')

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer token-1')
  })
})

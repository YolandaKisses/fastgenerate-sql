import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearAuth,
  getAuthToken,
  getCurrentUser,
  getUserScopedSessionStorageKey,
  setAuthSession,
} from '../src/services/auth'
import { request } from '../src/services/request'

describe('auth client helpers', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
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

  it('builds session storage keys scoped by current user', () => {
    setAuthSession('token-1', {
      user_id: 'u1',
      name: '系统管理员',
      account: 'admin',
      role: 'admin',
    })

    expect(getUserScopedSessionStorageKey('workbench_state')).toBe('workbench_state:u1')
  })

  it('clears workbench session state for the current user on logout', () => {
    setAuthSession('token-1', {
      user_id: 'u1',
      name: '系统管理员',
      account: 'admin',
      role: 'admin',
    })
    sessionStorage.setItem('workbench_state', '{"legacy":true}')
    sessionStorage.setItem('workbench_state:u1', '{"user":"u1"}')

    clearAuth()

    expect(sessionStorage.getItem('workbench_state')).toBeNull()
    expect(sessionStorage.getItem('workbench_state:u1')).toBeNull()
  })

  it('clears previous user workbench state when switching accounts', () => {
    setAuthSession('token-1', {
      user_id: 'u1',
      name: '系统管理员',
      account: 'admin',
      role: 'admin',
    })
    sessionStorage.setItem('workbench_state:u1', '{"user":"u1"}')

    setAuthSession('token-2', {
      user_id: 'u2',
      name: '分析师',
      account: 'analyst',
      role: 'analyst',
    })

    expect(sessionStorage.getItem('workbench_state:u1')).toBeNull()
    expect(getUserScopedSessionStorageKey('workbench_state')).toBe('workbench_state:u2')
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

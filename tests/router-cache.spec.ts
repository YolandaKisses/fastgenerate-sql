import { describe, expect, it } from 'vitest'
import { routes } from '../src/router'

describe('主菜单页面缓存配置', () => {
  it('应为主菜单页面开启 keepAlive，并保持登录页不缓存', () => {
    const keepAlivePaths = routes
      .filter((route) => route.meta?.keepAlive)
      .map((route) => route.path)

    expect(keepAlivePaths).toEqual([
      '/wiki',
      '/data-sources',
      '/schema',
      '/demand',
      '/settings',
    ])

    const loginRoute = routes.find((route) => route.path === '/login')
    expect(loginRoute?.meta?.keepAlive).not.toBe(true)
  })
})

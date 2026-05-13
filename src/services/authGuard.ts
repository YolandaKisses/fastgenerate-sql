import type { NavigationGuard } from 'vue-router'
import { isAuthenticated } from './auth'

export const authGuard: NavigationGuard = (to) => {
  const authed = isAuthenticated()
  
  if (to.path === '/login' && authed) {
    return '/data-sources'
  }
  
  if (to.meta.requiresAuth && !authed) {
    return {
      path: '/login',
      query: { redirect: to.fullPath }
    }
  }
  
  return true
}

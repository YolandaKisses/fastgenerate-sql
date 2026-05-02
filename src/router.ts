import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { isAuthenticated } from './services/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workspace'
  },
  {
    path: '/login',
    component: () => import('./pages/Login/index.vue'),
    meta: { public: true }
  },
  {
    path: '/workspace',
    component: () => import('./pages/Workbench/index.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/data-sources',
    component: () => import('./pages/DataSources/index.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/schema',
    component: () => import('./pages/SchemaManager/index.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/audit-logs',
    component: () => import('./pages/AuditLogs/index.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/settings',
    component: () => import('./pages/Settings/index.vue'),
    meta: { requiresAuth: true }
  }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to) => {
  const authed = isAuthenticated()
  if (to.path === '/login' && authed) {
    return '/workspace'
  }
  if (to.meta.requiresAuth && !authed) {
    return {
      path: '/login',
      query: { redirect: to.fullPath }
    }
  }
  return true
})

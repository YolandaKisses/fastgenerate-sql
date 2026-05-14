import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { authGuard } from './services/authGuard'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/data-sources'
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('./pages/Login/index.vue'),
    meta: { public: true }
  },
  {
    path: '/wiki',
    name: 'wiki',
    component: () => import('./pages/Wiki/index.vue'),
    meta: { requiresAuth: true, keepAlive: true }
  },
  {
    path: '/data-sources',
    name: 'data-sources',
    component: () => import('./pages/DataSources/index.vue'),
    meta: { requiresAuth: true, keepAlive: true }
  },
  {
    path: '/schema',
    name: 'schema',
    component: () => import('./pages/SchemaManager/index.vue'),
    meta: { requiresAuth: true, keepAlive: true }
  },
  {
    path: '/demand',
    name: 'demand',
    component: () => import('./pages/DemandManager/index.vue'),
    meta: { requiresAuth: true, keepAlive: true }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./pages/Settings/index.vue'),
    meta: { requiresAuth: true, keepAlive: true }
  }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach(authGuard)

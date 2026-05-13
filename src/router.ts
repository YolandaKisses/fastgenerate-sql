import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { authGuard } from './services/authGuard'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/data-sources'
  },
  {
    path: '/login',
    component: () => import('./pages/Login/index.vue'),
    meta: { public: true }
  },
  {
    path: '/wiki',
    component: () => import('./pages/Wiki/index.vue'),
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
    path: '/demand',
    component: () => import('./pages/DemandManager/index.vue'),
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

router.beforeEach(authGuard)

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workspace'
  },
  {
    path: '/workspace',
    component: () => import('./pages/Workbench/index.vue')
  },
  {
    path: '/data-sources',
    component: () => import('./pages/DataSources/index.vue')
  },
  {
    path: '/schema',
    component: () => import('./pages/SchemaManager/index.vue')
  },
  {
    path: '/audit-logs',
    component: () => import('./pages/AuditLogs/index.vue')
  }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

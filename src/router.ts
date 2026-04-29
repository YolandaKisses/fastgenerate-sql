import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import AuditLogsPage from './pages/AuditLogs/index.vue'
import DataSourcesPage from './pages/DataSources/index.vue'
import SchemaManagerPage from './pages/SchemaManager/index.vue'
import SettingsPage from './pages/Settings/index.vue'
import WorkbenchPage from './pages/Workbench/index.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workspace'
  },
  {
    path: '/workspace',
    component: WorkbenchPage
  },
  {
    path: '/data-sources',
    component: DataSourcesPage
  },
  {
    path: '/schema',
    component: SchemaManagerPage
  },
  {
    path: '/audit-logs',
    component: AuditLogsPage
  },
  {
    path: '/settings',
    component: SettingsPage
  }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

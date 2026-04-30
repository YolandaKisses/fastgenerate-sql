<script setup lang="ts">
import { computed } from 'vue'
import { NLayoutSider, NMenu, NAvatar } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const activeKey = computed(() => route.path)

const menuOptions = [
  {
    label: '工作台',
    key: '/workspace',
  },
  {
    label: '数据源配置',
    key: '/data-sources',
  },
  {
    label: 'Schema 管理',
    key: '/schema',
  },
  {
    label: '审计日志',
    key: '/audit-logs',
  }
]

const handleUpdateValue = (key: string) => {
  router.push(key)
}
</script>

<template>
  <n-layout-sider bordered :width="240" class="app-sider">
    <div class="brand">
      <h1 class="brand-title">SQL AI</h1>
      <span class="version">v1.2.0</span>
    </div>
    <n-menu
      :value="activeKey"
      :options="menuOptions"
      @update:value="handleUpdateValue"
      class="nav-menu"
    />
    <div class="sidebar-footer">
      <n-avatar round size="medium" style="background-color: #eef0fa; color: #2080f0; font-weight: bold;">
        管
      </n-avatar>
      <div class="user-meta">
        <strong>管理员用户</strong>
        <span>admin@sqlai.io</span>
      </div>
    </div>
  </n-layout-sider>
</template>

<style scoped>
.app-sider {
  display: flex;
  flex-direction: column;
  background-color: #fbfcfd;
}

.brand {
  padding: 24px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brand-title {
  font-size: 18px;
  font-weight: 600;
  color: #181c22;
  margin: 0;
  line-height: 1.2;
}

.version {
  color: #717785;
  font-size: 12px;
}

.nav-menu {
  flex: 1;
}

.sidebar-footer {
  margin-top: auto;
  padding: 16px 20px;
  border-top: 1px solid #efeff5;
  display: flex;
  gap: 12px;
  align-items: center;
}

.user-meta {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.user-meta strong {
  font-size: 13px;
  color: #181c22;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-meta span {
  font-size: 11px;
  color: #717785;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>

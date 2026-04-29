<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NSpace, NText, NLayout, NLayoutContent, NLayoutSider, useMessage } from 'naive-ui'
import AuditLogTable from './components/AuditLogTable.vue'
import AuditLogDetail from './components/AuditLogDetail.vue'

const message = useMessage()
const logs = ref<any[]>([])
const selectedId = ref<number | null>(null)

const selectedLog = computed(() => {
  return logs.value.find(l => l.id === selectedId.value) || null
})

const fetchLogs = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/audit/logs')
    if (res.ok) {
      logs.value = await res.json()
      if (logs.value.length > 0 && !selectedId.value) {
        selectedId.value = logs.value[0].id
      }
    }
  } catch (error) {
    message.error('无法加载审计日志')
  }
}

const handleDelete = async (id: number) => {
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/audit/logs/${id}`, { method: 'DELETE' })
    const data = await res.json()
    if (data.success) {
      message.success('已删除')
      if (selectedId.value === id) {
        selectedId.value = null
      }
      await fetchLogs()
    }
  } catch (error) {
    message.error('删除失败')
  }
}

onMounted(() => {
  fetchLogs()
})

const handleSelect = (id: number) => {
  selectedId.value = id
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header" style="margin-bottom: 24px;">
      <div>
        <h1 class="page-title">审计日志</h1>
        <p class="page-subtitle">本地查看历史问答与执行记录，用于排查与复盘。</p>
      </div>
    </div>

    <n-layout has-sider class="logs-layout" style="background: transparent;">
      <n-layout-content style="background: transparent; margin-right: 24px;">
        <div style="margin-bottom: 12px;">
          <n-text style="font-size: 16px; font-weight: 600; color: #181c22;">日志列表 ({{ logs.length }})</n-text>
        </div>
        <AuditLogTable :logs="logs" :selected-id="selectedId" @select="handleSelect" @delete="handleDelete" />
      </n-layout-content>

      <n-layout-sider width="400" style="background: transparent;">
        <AuditLogDetail :log="selectedLog" />
      </n-layout-sider>
    </n-layout>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 28px;
  margin: 0 0 8px 0;
  color: #181c22;
}

.page-subtitle {
  font-size: 14px;
  line-height: 22px;
  color: #717785;
  margin: 0 0 4px 0;
}

.logs-layout {
  flex: 1;
}
</style>

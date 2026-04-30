<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NSpace, NText, NLayout, NLayoutContent, NLayoutSider, useMessage } from 'naive-ui'
import AuditLogTable from './components/AuditLogTable.vue'
import AuditLogDetail from './components/AuditLogDetail.vue'

const message = useMessage()
const logs = ref<any[]>([])
const selectedId = ref<number | null>(null)
const keyword = ref('')
const selectedStatus = ref<string | null>(null)
const selectedDatasource = ref<string | null>(null)

const statusOptions = [
  { label: '全部状态', value: null },
  { label: '未执行', value: 'pending' },
  { label: '执行成功', value: 'success' },
  { label: '无数据', value: 'empty' },
  { label: '执行失败', value: 'error' }
]

const datasourceOptions = computed(() => {
  const names = Array.from(new Set(logs.value.map(log => log.datasource_name).filter(Boolean)))
  return [
    { label: '全部数据源', value: null },
    ...names.map(name => ({ label: name, value: name }))
  ]
})

const selectedLog = computed(() => {
  return filteredLogs.value.find(l => l.id === selectedId.value) || null
})

const filteredLogs = computed(() => {
  return logs.value.filter((log) => {
    const matchesKeyword = !keyword.value || `${log.question} ${log.sql || ''} ${log.error_summary || ''}`.toLowerCase().includes(keyword.value.toLowerCase())
    const status = !log.executed ? 'pending' : log.execution_status
    const matchesStatus = selectedStatus.value === null || status === selectedStatus.value
    const matchesDatasource = selectedDatasource.value === null || log.datasource_name === selectedDatasource.value
    return matchesKeyword && matchesStatus && matchesDatasource
  })
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
        <p class="page-note">仅本地查看，不支持导出。</p>
      </div>
    </div>

    <n-layout has-sider class="logs-layout" style="background: transparent;">
      <n-layout-content style="background: transparent; margin-right: 24px;">
        <div class="filters">
          <input
            v-model="keyword"
            aria-label="关键词搜索"
            placeholder="按问题、SQL 或错误信息搜索"
            class="filter-input"
          />
          <select v-model="selectedStatus" aria-label="执行状态筛选" class="filter-select">
            <option :value="null">全部状态</option>
            <option value="pending">未执行</option>
            <option value="success">执行成功</option>
            <option value="empty">无数据</option>
            <option value="error">执行失败</option>
          </select>
          <select v-model="selectedDatasource" aria-label="数据源筛选" class="filter-select">
            <option :value="null">全部数据源</option>
            <option v-for="option in datasourceOptions.slice(1)" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </div>
        <div style="margin-bottom: 12px;">
          <n-text style="font-size: 16px; font-weight: 600; color: #181c22;">日志列表 ({{ filteredLogs.length }})</n-text>
        </div>
        <AuditLogTable :logs="filteredLogs" :selected-id="selectedId" @select="handleSelect" @delete="handleDelete" />
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

.page-note {
  font-size: 13px;
  color: #8c92a0;
  margin: 0;
}

.logs-layout {
  flex: 1;
}

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.filter-input {
  flex: 1;
  height: 40px;
  border: 1px solid #d9dce8;
  border-radius: 8px;
  padding: 0 12px;
  background: #fff;
  color: #181c22;
}

.filter-select {
  min-width: 160px;
  height: 40px;
  border: 1px solid #d9dce8;
  border-radius: 8px;
  padding: 0 12px;
  background: #fff;
}
</style>

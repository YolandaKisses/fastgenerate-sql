<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NText, NInput, NSelect, useMessage } from 'naive-ui'
import AuditLogTable from './components/AuditLogTable.vue'
import AuditLogDetail from './components/AuditLogDetail.vue'

const message = useMessage()
const logs = ref<any[]>([])
const selectedId = ref<number | null>(null)
const keyword = ref('')
const ALL_STATUS = '__all_status__'
const ALL_DATASOURCE = '__all_datasource__'
const selectedStatus = ref<string>(ALL_STATUS)
const selectedDatasource = ref<string>(ALL_DATASOURCE)

const statusOptions = [
  { label: '全部状态', value: ALL_STATUS },
  { label: '未执行', value: 'pending' },
  { label: '执行成功', value: 'success' },
  { label: '无数据', value: 'empty' },
  { label: '执行失败', value: 'error' }
]

const datasourceOptions = computed(() => {
  const names = Array.from(new Set(logs.value.map(log => log.datasource_name).filter(Boolean)))
  return [
    { label: '全部数据源', value: ALL_DATASOURCE },
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
    const matchesStatus = selectedStatus.value === ALL_STATUS || status === selectedStatus.value
    const matchesDatasource = selectedDatasource.value === ALL_DATASOURCE || log.datasource_name === selectedDatasource.value
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
    <div class="page-header">
      <div class="header-content">
        <div>
          <h1 class="page-title">审计日志</h1>
          <p class="page-subtitle">查看历史问答与执行记录，用于排查与复盘。</p>
          <p class="page-note">仅本地查看，不支持导出。</p>
        </div>
      </div>
    </div>

    <div class="audit-container">
      <div class="main-panel">
        <div class="filters">
          <n-input
            v-model:value="keyword"
            placeholder="搜索问题、SQL 或错误信息..."
            clearable
            class="filter-search"
          />
          <n-select 
            v-model:value="selectedStatus" 
            :options="statusOptions" 
            placeholder="执行状态"
            class="filter-select-status"
          />
          <n-select 
            v-model:value="selectedDatasource" 
            :options="datasourceOptions" 
            placeholder="全部数据源"
            class="filter-select-ds"
          />
        </div>
        
        <div class="list-title">
          <n-text strong style="font-size: 15px; color: #181c22;">日志列表 ({{ filteredLogs.length }})</n-text>
        </div>

        <div class="table-wrapper">
          <AuditLogTable :logs="filteredLogs" :selected-id="selectedId" @select="handleSelect" @delete="handleDelete" />
        </div>
      </div>

      <div class="sider-panel">
        <AuditLogDetail :log="selectedLog" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
  overflow: hidden;
}

.header-content {
  margin-bottom: 24px;
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
  font-size: 12px;
  color: #8c92a0;
  margin: 0;
}

.audit-container {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 24px;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-search {
  flex: 1;
}

.filter-select-status {
  width: 160px;
}

.filter-select-ds {
  width: 220px;
}

.list-title {
  margin-bottom: 12px;
}

.table-wrapper {
  flex: 1;
  overflow-y: auto;
  border-radius: 12px;
  border: 1px solid #efeff5;
  background: #fff;
}

.sider-panel {
  width: 400px;
  display: flex;
  flex-direction: column;
}
</style>

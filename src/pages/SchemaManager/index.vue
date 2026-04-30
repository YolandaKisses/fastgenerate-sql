<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NSelect, useMessage } from 'naive-ui'
import TableList from './components/TableList.vue'
import SchemaEditor from './components/SchemaEditor.vue'

const message = useMessage()
const currentSource = ref<number | null>(null)
const sourceOptions = ref<{label: string, value: number}[]>([])
const tables = ref<any[]>([])
const selectedTable = ref<any | null>(null)
const knowledgeTask = ref<any | null>(null)
const actualTableCount = ref(0)
const knowledgeSyncing = ref(false)
let knowledgePollTimer: ReturnType<typeof setTimeout> | null = null

const formatKnowledgeBanner = (task: any | null) => {
  if (!task) return '尚未同步知识库'
  const completed = task.completed_tables ?? 0
  const total = task.total_tables ?? 0
  
  if (task.status === 'completed') {
    if (actualTableCount.value > total) {
      return `知识库已过期 (${total}/${actualTableCount.value} 表已同步)`
    }
    return `知识库已同步成功 ${completed} / ${total}`
  }
  if (task.status === 'failed') {
    return `知识库同步失败 ${completed} / ${total}`
  }
  return `知识库同步进行中 ${completed} / ${total}`
}

const fetchSources = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/datasources/')
    if (res.ok) {
      const data = await res.json()
      sourceOptions.value = data.map((ds: any) => ({
        label: `${ds.name} (${ds.db_type})`,
        value: ds.id
      }))

      // 校验当前选中项是否依然有效
      if (currentSource.value && !sourceOptions.value.find(opt => opt.value === currentSource.value)) {
        currentSource.value = null
      }

      if (data.length > 0 && !currentSource.value) {
        currentSource.value = data[0].id
      }
    }
  } catch (error) {
    message.error('无法加载数据源')
  }
}

const fetchTables = async (dsId: number) => {
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/tables/${dsId}`)
    if (res.ok) {
      tables.value = await res.json()
      if (tables.value.length > 0) {
        selectedTable.value = tables.value[0]
      } else {
        selectedTable.value = null
      }
    }
  } catch (error) {
    message.error('无法加载表结构')
  }
}

const fetchLatestKnowledgeTask = async (dsId: number) => {
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/knowledge/status/${dsId}`)
    if (res.ok) {
      const data = await res.json()
      knowledgeTask.value = data.task
      actualTableCount.value = data.actual_table_count
      
      if (data.task && (data.task.status === 'running' || data.task.status === 'pending')) {
        knowledgeSyncing.value = true
        pollKnowledgeTask(data.task.id)
      }
    }
  } catch (error) {
    console.error('无法加载知识库任务状态', error)
  }
}

watch(currentSource, (newVal) => {
  knowledgeTask.value = null
  knowledgeSyncing.value = false
  if (knowledgePollTimer) {
    clearTimeout(knowledgePollTimer)
    knowledgePollTimer = null
  }
  if (newVal) {
    fetchTables(newVal)
    fetchLatestKnowledgeTask(newVal)
  }
})

onMounted(() => {
  fetchSources()
})

const handleSelectTable = (table: any) => {
  selectedTable.value = table
}

const handleSync = async () => {
  if (!currentSource.value) return
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/sync/${currentSource.value}`, { method: 'POST' })
    const data = await res.json()
    if (data.success) {
      message.success(data.message)
      fetchTables(currentSource.value)
      fetchLatestKnowledgeTask(currentSource.value)
    } else {
      message.error(data.message)
    }
  } catch (error) {
    message.error('同步请求失败')
  }
}

const pollKnowledgeTask = async (taskId: number) => {
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/knowledge/tasks/${taskId}`)
    if (!res.ok) {
      throw new Error('无法获取任务状态')
    }
    const data = await res.json()
    knowledgeTask.value = data
    if (data.status === 'running' || data.status === 'pending') {
      knowledgeSyncing.value = true
      knowledgePollTimer = setTimeout(() => {
        pollKnowledgeTask(taskId)
      }, 1000)
      return
    }

    knowledgeSyncing.value = false
    if (data.status === 'completed') {
      message.success('知识库同步完成')
    } else if (data.status === 'failed') {
      message.error(data.error_message || '知识库同步失败')
    }
  } catch (error) {
    knowledgeSyncing.value = false
    message.error('知识库任务轮询失败')
  }
}

const handleKnowledgeSync = async () => {
  if (!currentSource.value) return
  try {
    knowledgeSyncing.value = true
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/knowledge/sync/${currentSource.value}`, { method: 'POST' })
    const data = await res.json()
    if (!res.ok || data.success === false) {
      knowledgeSyncing.value = false
      message.error(data.message || '知识库同步启动失败')
      return
    }
    knowledgeTask.value = data
    pollKnowledgeTask(data.id)
  } catch (error) {
    knowledgeSyncing.value = false
    message.error('知识库同步请求失败')
  }
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h1 class="page-title">Schema 与备注管理</h1>
          <p class="page-subtitle">管理数据库元数据，支持表级和字段级的本地补充备注，提升 AI 问答准确性。</p>
        </div>
        <div class="header-right">
          <div v-if="knowledgeTask" class="knowledge-banner" :class="[
            `is-${knowledgeTask.status}`,
            { 'is-expired': knowledgeTask.status === 'completed' && actualTableCount > knowledgeTask.total_tables }
          ]">
            <span class="status-dot"></span>
            {{ formatKnowledgeBanner(knowledgeTask) }}
          </div>
          <div v-else class="knowledge-banner is-none">
            <span class="status-dot"></span>
            尚未同步知识库
          </div>
          <n-select 
            v-model:value="currentSource" 
            :options="sourceOptions" 
            placeholder="选择数据源" 
            style="width: 260px;"
          />
        </div>
      </div>
    </div>

    <div class="schema-container">
      <div class="sider-panel">
        <TableList :tables="tables" :selected-table="selectedTable" @select="handleSelectTable" />
      </div>
      <div class="main-panel">
        <SchemaEditor
          :table="selectedTable"
          :knowledge-task="knowledgeTask"
          :knowledge-syncing="knowledgeSyncing"
          @sync="handleSync"
          @sync-knowledge="handleKnowledgeSync"
        />
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
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
  margin: 0;
}

.knowledge-banner {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  gap: 8px;
}

.knowledge-banner.is-expired {
  color: #8a6700;
  background: #fff7db;
  border: 1px solid #f3df9b;
}

.knowledge-banner.is-none {
  color: #717785;
  background: #f4f5f7;
  border: 1px solid #e1e3e6;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.knowledge-banner.is-pending,
.knowledge-banner.is-running {
  color: #8a6700;
  background: #fff7db;
  border: 1px solid #f3df9b;
}

.knowledge-banner.is-completed {
  color: #17623a;
  background: #e9f8ef;
  border: 1px solid #b8e2c6;
}

.knowledge-banner.is-failed {
  color: #a53a3a;
  background: #fdeeee;
  border: 1px solid #f3c3c3;
}

.schema-container {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 24px;
}

.sider-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>

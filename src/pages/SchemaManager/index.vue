<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
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

// 当前活跃的知识库同步 EventSource
let activeKnowledgeSSE: EventSource | null = null
let knowledgeStatusPoll: ReturnType<typeof setInterval> | null = null

// 当前处理中的表名（用于实时展示）
// 移除了独立的 currentSyncTable ref，改用 knowledgeTask.current_table

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
  if (task.status === 'partial_success') {
    return `知识库部分同步成功 ${completed} / ${total}`
  }
  if (task.status === 'failed') {
    return `知识库同步失败 ${completed} / ${total}`
  }

  // running 状态下显示当前正在处理的表名
  if (task.current_table) {
    return `同步进行中 ${completed} / ${total} — 正在处理: ${task.current_table}`
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
        if (!activeKnowledgeSSE) startKnowledgeStatusPolling(dsId)
      } else {
        knowledgeSyncing.value = false
        stopKnowledgeStatusPolling()
      }
    }
  } catch (error) {
    console.error('无法加载知识库任务状态', error)
  }
}

const startKnowledgeStatusPolling = (dsId: number) => {
  if (knowledgeStatusPoll) return
  knowledgeStatusPoll = setInterval(() => {
    if (!currentSource.value || currentSource.value !== dsId || activeKnowledgeSSE) {
      stopKnowledgeStatusPolling()
      return
    }
    fetchLatestKnowledgeTask(dsId)
  }, 3000)
}

const stopKnowledgeStatusPolling = () => {
  if (knowledgeStatusPoll) {
    clearInterval(knowledgeStatusPoll)
    knowledgeStatusPoll = null
  }
}

// 清理活跃的 SSE 连接
const cleanupKnowledgeSSE = () => {
  if (activeKnowledgeSSE) {
    activeKnowledgeSSE.close()
    activeKnowledgeSSE = null
  }
}

watch(currentSource, (newVal) => {
  knowledgeTask.value = null
  knowledgeSyncing.value = false
  stopKnowledgeStatusPolling()
  cleanupKnowledgeSSE()
  if (newVal) {
    fetchTables(newVal)
    fetchLatestKnowledgeTask(newVal)
  }
})

onMounted(() => {
  fetchSources()
})

onUnmounted(() => {
  stopKnowledgeStatusPolling()
  cleanupKnowledgeSSE()
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

// ---------------------------------------------------------------------------
// SSE 流式知识库同步（替代轮询）
// ---------------------------------------------------------------------------
const handleKnowledgeSync = () => {
  if (!currentSource.value) return

  // 清理之前的 SSE
  cleanupKnowledgeSSE()
  stopKnowledgeStatusPolling()

  knowledgeSyncing.value = true

  // 初始化 knowledgeTask 为"正在启动"状态
  knowledgeTask.value = {
    status: 'running',
    completed_tables: 0,
    total_tables: 0,
  }

  const url = `http://127.0.0.1:8000/api/v1/schema/knowledge/sync_stream/${currentSource.value}`
  const source = new EventSource(url)
  activeKnowledgeSSE = source

  source.addEventListener('status', (e: MessageEvent) => {
    const data = JSON.parse(e.data)

    // 更新任务状态
    knowledgeTask.value = {
      ...knowledgeTask.value,
      status: data.status ? data.status 
            : data.phase === 'completed' ? 'completed'
            : data.phase === 'failed' ? 'failed'
            : 'running',
      completed_tables: data.completed_tables ?? knowledgeTask.value?.completed_tables ?? 0,
      total_tables: data.total_tables ?? knowledgeTask.value?.total_tables ?? 0,
      current_table: data.current_table ?? knowledgeTask.value?.current_table,
      id: data.task_id ?? knowledgeTask.value?.id,
    }

    if (data.phase === 'completed') {
      knowledgeSyncing.value = false
      message.success(data.message || '知识库同步完成')
      source.close()
      activeKnowledgeSSE = null
      // 刷新最新状态
      if (currentSource.value) fetchLatestKnowledgeTask(currentSource.value)
    } else if (data.phase === 'failed') {
      knowledgeSyncing.value = false
      message.error(data.message || '知识库同步失败')
      source.close()
      activeKnowledgeSSE = null
      if (currentSource.value) fetchLatestKnowledgeTask(currentSource.value)
    }
  })

  source.addEventListener('table_start', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    if (knowledgeTask.value) {
      knowledgeTask.value = {
        ...knowledgeTask.value,
        current_table: data.table_name
      }
    }
  })

  source.addEventListener('table_done', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    if (knowledgeTask.value) {
      knowledgeTask.value = {
        ...knowledgeTask.value,
        completed_tables: data.completed_tables,
        current_table: ''
      }
    }
  })

  source.addEventListener('error', (e: MessageEvent) => {
    try {
      const data = JSON.parse((e as any).data || '{}')
      if (data.message) {
        message.error(data.message)
      }
    } catch {
      if (source.readyState !== EventSource.CLOSED) {
        message.error('知识库同步 SSE 连接中断')
      }
    }
    knowledgeSyncing.value = false
    if (knowledgeTask.value) knowledgeTask.value.current_table = ''
    source.close()
    activeKnowledgeSSE = null
    if (currentSource.value) fetchLatestKnowledgeTask(currentSource.value)
  })
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

.knowledge-banner.is-partial_success {
  color: #a16207;
  background: #fefce8;
  border: 1px solid #fef08a;
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

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { NSelect, useMessage } from 'naive-ui'
import AiAssistant from './components/AiAssistant.vue'
import SqlEditor from './components/SqlEditor.vue'
import QueryResult from './components/QueryResult.vue'
import HermesProcess from './components/HermesProcess.vue'
import type { HermesStep } from './components/HermesProcess.vue'

const STORAGE_KEY = 'workbench_state'

const message = useMessage()
const loading = ref(false)
const currentDatasource = ref<number | null>(null)
const datasourceOptions = ref<{label: string, value: number}[]>([])

const generatedSql = ref('')
const displayedSql = ref('')
const isRendering = ref(false)
const sqlExplanation = ref('')
const clarification = ref('')
const queryResult = ref<any | null>(null)
const currentAuditLogId = ref<number | null>(null)
const validationState = ref<'idle' | 'validating' | 'valid' | 'invalid'>('idle')
const validationReasons = ref<string[]>([])

// Hermes 工作过程步骤
const hermesSteps = ref<HermesStep[]>([])
const hermesProcessRef = ref<InstanceType<typeof HermesProcess> | null>(null)

// 对话上下文历史 (用于多轮澄清)
const messageHistory = ref<{role: 'user' | 'assistant', content: string}[]>([])

// 清除上下文
const handleResetContext = () => {
  messageHistory.value = []
  generatedSql.value = ''
  displayedSql.value = ''
  sqlExplanation.value = ''
  clarification.value = ''
  hermesSteps.value = []
  currentAuditLogId.value = null
  message.info('上下文已清除')
}

// 当前活跃的 EventSource 引用
let activeEventSource: EventSource | null = null

// 渐进渲染的 requestAnimationFrame ID
let renderRafId: number | null = null

// 从 sessionStorage 恢复上次的工作状态
const restoreState = () => {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    if (saved) {
      const state = JSON.parse(saved)
      currentDatasource.value = state.datasourceId ?? null
      generatedSql.value = state.sql ?? ''
      sqlExplanation.value = state.explanation ?? ''
      clarification.value = state.clarification ?? ''
      queryResult.value = state.result ?? null
      messageHistory.value = state.history ?? []
      currentAuditLogId.value = state.auditLogId ?? null
    }
  } catch {}
}

// 保存工作状态到 sessionStorage
const saveState = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      datasourceId: currentDatasource.value,
      sql: generatedSql.value,
      explanation: sqlExplanation.value,
      clarification: clarification.value,
      result: queryResult.value,
      history: messageHistory.value,
      auditLogId: currentAuditLogId.value
    }))
  } catch {}
}

watch([currentDatasource, generatedSql, sqlExplanation, clarification, queryResult, messageHistory, currentAuditLogId], saveState, { deep: true })

watch(generatedSql, async (newSql) => {
  if (!newSql) {
    validationState.value = 'idle'
    validationReasons.value = []
    return
  }

  validationState.value = 'validating'
  validationReasons.value = []
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/workbench/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: newSql })
    })
    const data = await res.json()
    validationState.value = data.status === 'valid' ? 'valid' : 'invalid'
    validationReasons.value = data.reasons || []
  } catch {
    validationState.value = 'invalid'
    validationReasons.value = ['SQL 校验请求失败']
  }
})

onMounted(async () => {
  restoreState()
  
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/datasources/')
    if (res.ok) {
      const data = await res.json()
      datasourceOptions.value = data
        .filter((ds: any) => ds.status === 'READY' || ds.status === 'ready' || ds.status === 'connection_ok')
        .map((ds: any) => ({ label: `${ds.name} (${ds.db_type})`, value: ds.id }))
      
      // 校验恢复的状态是否依然有效
      if (currentDatasource.value && !datasourceOptions.value.find(opt => opt.value === currentDatasource.value)) {
        currentDatasource.value = null
      }

      // 仅在没有有效选中项时，默认选第一个
      if (datasourceOptions.value.length > 0 && !currentDatasource.value) {
        currentDatasource.value = datasourceOptions.value[0].value
      }
    }
  } catch (error) {
    message.error('无法加载数据源列表')
  }
})

onUnmounted(() => {
  // 清理活跃的 EventSource
  if (activeEventSource) {
    activeEventSource.close()
    activeEventSource = null
  }
  // 清理渐进渲染
  if (renderRafId !== null) {
    cancelAnimationFrame(renderRafId)
    renderRafId = null
  }
})

// ---------------------------------------------------------------------------
// SQL 渐进渲染
// ---------------------------------------------------------------------------
const startProgressiveRender = (fullSql: string) => {
  displayedSql.value = ''
  isRendering.value = true
  let index = 0

  // 根据 SQL 长度动态调整速度：短 SQL 快渲，长 SQL 慢渲
  const totalLen = fullSql.length
  const baseChunk = totalLen < 100 ? 4 : totalLen < 300 ? 3 : 2

  const render = () => {
    const chunkSize = Math.min(baseChunk, totalLen - index)
    displayedSql.value += fullSql.slice(index, index + chunkSize)
    index += chunkSize

    if (index < totalLen) {
      renderRafId = requestAnimationFrame(render)
    } else {
      isRendering.value = false
      generatedSql.value = fullSql
      renderRafId = null
    }
  }

  renderRafId = requestAnimationFrame(render)
}

// ---------------------------------------------------------------------------
// SSE 流式问答
// ---------------------------------------------------------------------------
const handleQuerySubmit = (question: string) => {
  if (!currentDatasource.value) {
    message.warning('请先选择一个数据源')
    return
  }
  
  // 重置状态
  loading.value = true
  clarification.value = ''
  generatedSql.value = ''
  displayedSql.value = ''
  isRendering.value = false
  sqlExplanation.value = ''
  queryResult.value = null
  hermesSteps.value = []
  currentAuditLogId.value = null

  // 将当前问题存入历史记录 (只保留最近 10 条以防 Prompt 太长)
  messageHistory.value.push({ role: 'user', content: question })
  if (messageHistory.value.length > 10) {
    messageHistory.value.shift()
  }

  // 取消之前的 EventSource / 渲染
  if (activeEventSource) { activeEventSource.close(); activeEventSource = null }
  if (renderRafId !== null) { cancelAnimationFrame(renderRafId); renderRafId = null }

  // 启动计时器
  hermesProcessRef.value?.startTimer()

  // 构建 SSE URL
  const url = new URL('http://127.0.0.1:8000/api/v1/workbench/ask_stream')
  url.searchParams.set('datasource_id', String(currentDatasource.value))
  url.searchParams.set('question', question)
  
  // 传入历史对话上下文
  if (messageHistory.value.length > 1) {
    // 传除最后一条（即当前问题）以外的历史
    const context = messageHistory.value.slice(0, -1)
    url.searchParams.set('history', JSON.stringify(context))
  }

  const source = new EventSource(url.toString())
  activeEventSource = source

  source.addEventListener('status', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    hermesSteps.value.push({
      phase: data.phase,
      message: data.message,
      timestamp: Date.now(),
    })

    // 当完成或失败时停止计时器
    if (data.phase === 'completed' || data.phase === 'failed') {
      hermesProcessRef.value?.stopTimer()
    }
  })

  source.addEventListener('note_hit', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    hermesSteps.value.push({
      phase: 'note_hit',
      message: `命中笔记: ${data.note}`,
      detail: data.comment || undefined,
      timestamp: Date.now(),
    })
  })

  source.addEventListener('result', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    console.log('SSE result:', data)

    if (data.audit_log_id) {
      currentAuditLogId.value = data.audit_log_id
    }

    if (data.type === 'sql_candidate') {
      // 启动渐进渲染
      sqlExplanation.value = data.explanation || ''
      startProgressiveRender(data.sql)
      message.success('SQL 生成成功，请确认后执行')
      
      // 存入历史
      messageHistory.value.push({ role: 'assistant', content: data.explanation || '已生成 SQL 候选语句。' })
    } else if (data.type === 'clarification') {
      clarification.value = data.message
      message.info('AI 需要您进一步澄清问题')
      
      // 存入历史
      messageHistory.value.push({ role: 'assistant', content: data.message })
    }
    if (data.warning) {
      message.warning(data.warning)
    }

    source.close()
    activeEventSource = null
    loading.value = false
  })

  source.addEventListener('error', (e: MessageEvent) => {
    // SSE 自带的 error event（连接断开等）
    // 也可能是后端发送的 error event
    try {
      const data = JSON.parse((e as any).data || '{}')
      if (data.message) {
        message.error(data.message)
        hermesSteps.value.push({
          phase: 'failed',
          message: data.message,
          timestamp: Date.now(),
        })
      }
    } catch {
      // 连接级错误
      if (source.readyState === EventSource.CLOSED) {
        // 正常关闭，忽略
      } else {
        message.error('SSE 连接中断，请检查后端服务')
      }
    }

    hermesProcessRef.value?.stopTimer()
    source.close()
    activeEventSource = null
    loading.value = false
  })
}

const handleExecuteSql = async () => {
  if (!currentDatasource.value || !generatedSql.value || loading.value) return
  loading.value = true
  queryResult.value = null

  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/workbench/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        datasource_id: currentDatasource.value, 
        sql: generatedSql.value,
        audit_log_id: currentAuditLogId.value
      })
    })
    const data = await res.json()
    console.log('Execute result:', data)
    queryResult.value = data

    if (data.status === 'success') {
      message.success(`查询完成，返回 ${data.row_count} 条记录 (${data.duration_ms}ms)`)
    } else if (data.status === 'empty') {
      message.info('查询成功，但没有返回数据')
    } else {
      message.error(data.message || '执行失败')
    }
    if (data.warning) {
      message.warning(data.warning)
    }
    
    // 滚动到结果区域
    setTimeout(() => {
      const el = document.querySelector('.result-container')
      if (el) el.scrollIntoView({ behavior: 'smooth' })
    }, 100)
  } catch (error) {
    message.error('执行请求失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div class="header-content">
        <div>
          <h1 class="page-title">工作台</h1>
          <p class="page-subtitle">已支持连接测试通过的数据源直接问答。</p>
        </div>
        <div class="header-actions">
          <div class="context-info" v-if="messageHistory.length > 0">
            <span class="context-tag">对话中 ({{ Math.ceil(messageHistory.length / 2) }} 轮)</span>
            <n-button quaternary size="tiny" type="warning" @click="handleResetContext">
              清除上下文
            </n-button>
          </div>
          <div class="datasource-picker">
            <span class="picker-label">当前数据源</span>
            <n-select 
              v-model:value="currentDatasource" 
              :options="datasourceOptions" 
              placeholder="请选择数据源" 
              style="width: 300px;"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="page-content">
      <AiAssistant :disabled="loading || !currentDatasource" @submit="handleQuerySubmit" />

      <!-- Hermes 工作过程面板 -->
      <HermesProcess
        ref="hermesProcessRef"
        :steps="hermesSteps"
        :loading="loading"
      />

      <!-- 澄清提示 -->
      <div v-if="clarification" class="clarification-box">
        <span class="clarification-icon">💬</span>
        <div>
          <div style="font-weight: 600; margin-bottom: 4px; color: #181c22;">AI 需要澄清</div>
          <div style="color: #414753;">{{ clarification }}</div>
        </div>
      </div>

      <div class="workbench-sections">
        <section class="panel">
          <h2 class="panel-title">SQL 候选</h2>
          <SqlEditor
            v-if="generatedSql || isRendering"
            :sql="generatedSql"
            :displayed-sql="displayedSql"
            :is-rendering="isRendering"
            :explanation="sqlExplanation"
            :validation-state="validationState"
            :validation-reasons="validationReasons"
            @execute="handleExecuteSql"
          />
          <div v-else class="panel-placeholder">生成 SQL 后会展示候选语句与解释说明。</div>
        </section>

        <section class="panel">
          <h2 class="panel-title">执行结果</h2>
          <QueryResult v-if="queryResult" :result="queryResult" />
          <div v-else class="panel-placeholder">执行完成后，这里会展示结果表格或错误信息。</div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 20px;
}

.context-info {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff8f0;
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid #ffd8a8;
}

.context-tag {
  font-size: 11px;
  font-weight: 600;
  color: #e67e22;
  text-transform: uppercase;
}

.datasource-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.picker-label {
  font-size: 11px;
  font-weight: 600;
  color: #8c92a0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.page-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 1200px;
}

.workbench-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel {
  border: 1px solid #efeff5;
  border-radius: 12px;
  background: #fff;
  padding: 24px;
}

.panel-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
  color: #181c22;
}

.panel-placeholder {
  margin: 0;
  color: #717785;
  font-size: 14px;
}

.clarification-box {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 1px solid #fcd34d;
  border-radius: 10px;
  font-size: 14px;
}

.clarification-icon {
  font-size: 20px;
  flex-shrink: 0;
}
</style>

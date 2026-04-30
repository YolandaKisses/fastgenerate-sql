<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NSelect, useMessage } from 'naive-ui'
import AiAssistant from './components/AiAssistant.vue'
import SqlEditor from './components/SqlEditor.vue'
import QueryResult from './components/QueryResult.vue'

const STORAGE_KEY = 'workbench_state'

const message = useMessage()
const loading = ref(false)
const currentDatasource = ref<number | null>(null)
const datasourceOptions = ref<{label: string, value: number}[]>([])

const generatedSql = ref('')
const sqlExplanation = ref('')
const clarification = ref('')
const queryResult = ref<any>(null)
const validationState = ref<'idle' | 'validating' | 'valid' | 'invalid'>('idle')
const validationReasons = ref<string[]>([])

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
      result: queryResult.value
    }))
  } catch {}
}

watch([currentDatasource, generatedSql, sqlExplanation, clarification, queryResult], saveState, { deep: true })

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

const handleQuerySubmit = async (question: string) => {
  if (!currentDatasource.value) {
    message.warning('请先选择一个数据源')
    return
  }
  
  loading.value = true
  clarification.value = ''
  generatedSql.value = ''
  sqlExplanation.value = ''
  queryResult.value = null

  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/workbench/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ datasource_id: currentDatasource.value, question })
    })
    
    if (!res.ok) {
      const errText = await res.text()
      message.error(`请求失败 (${res.status}): ${errText.slice(0, 100)}`)
      return
    }
    
    const data = await res.json()
    console.log('Ask result:', data)

    if (!data || !data.type) {
      message.error('后端返回了无效的响应格式')
      return
    }

    if (data.type === 'sql_candidate') {
      generatedSql.value = data.sql
      sqlExplanation.value = data.explanation || ''
      message.success('SQL 生成成功，请确认后执行')
      if (data.warning) {
        message.warning(data.warning)
      }
    } else if (data.type === 'clarification') {
      clarification.value = data.message
      message.info('AI 需要您进一步澄清问题')
      if (data.warning) {
        message.warning(data.warning)
      }
    } else if (data.type === 'error') {
      message.error(data.message || '未知错误')
    }
  } catch (error: any) {
    console.error('Ask error:', error)
    message.error(`请求失败: ${error.message || '请检查后端服务'}`)
  } finally {
    loading.value = false
  }
}

const handleExecuteSql = async () => {
  if (!currentDatasource.value || !generatedSql.value || loading.value) return
  loading.value = true
  queryResult.value = null

  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/workbench/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ datasource_id: currentDatasource.value, sql: generatedSql.value })
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

      <div class="workbench-sections">
        <section class="panel">
          <h2 class="panel-title">SQL 候选</h2>
          <SqlEditor
            v-if="generatedSql"
            :sql="generatedSql"
            :explanation="sqlExplanation"
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
  background-color: #fbfcfd;
  border: 1px solid #efeff5;
  border-radius: 8px;
  font-size: 14px;
}

.clarification-icon {
  font-size: 20px;
  flex-shrink: 0;
}
</style>

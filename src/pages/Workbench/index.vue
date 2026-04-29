<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NSelect, NSpace, useMessage } from 'naive-ui'
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

onMounted(async () => {
  restoreState()
  
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/datasources/')
    if (res.ok) {
      const data = await res.json()
      datasourceOptions.value = data
        .filter((ds: any) => ds.status === 'READY' || ds.status === 'ready' || ds.status === 'connection_ok')
        .map((ds: any) => ({ label: `${ds.name} (${ds.db_type})`, value: ds.id }))
      // 仅在没有恢复的选中项时，默认选第一个
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
    } else if (data.type === 'clarification') {
      clarification.value = data.message
      message.info('AI 需要您进一步澄清问题')
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
  <div class="workbench-page">
    <div class="main-content">
      <n-space justify="space-between" align="center" style="margin-bottom: 16px;">
        <div style="font-size: 20px; font-weight: 600; color: #181c22;">工作台</div>
        <n-select
          v-model:value="currentDatasource"
          :options="datasourceOptions"
          placeholder="选择数据源"
          style="width: 260px;"
        />
      </n-space>
      
      <AiAssistant :disabled="loading || !currentDatasource" @submit="handleQuerySubmit" />
      
      <!-- 澄清区域 -->
      <div v-if="clarification" class="clarification-box">
        <div class="clarification-icon">💬</div>
        <div>
          <div style="font-weight: 600; margin-bottom: 4px;">AI 需要进一步信息</div>
          <div style="color: #414753;">{{ clarification }}</div>
        </div>
      </div>

      <!-- SQL 编辑与确认 -->
      <SqlEditor 
        v-if="generatedSql" 
        :sql="generatedSql" 
        :explanation="sqlExplanation"
        @execute="handleExecuteSql" 
      />

      <!-- 查询结果 -->
      <QueryResult v-if="queryResult" :result="queryResult" />
    </div>
  </div>
</template>

<style scoped>
.workbench-page {
  position: relative;
  height: 100%;
}

.main-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.clarification-box {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  background-color: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 14px;
}

.clarification-icon {
  font-size: 20px;
  flex-shrink: 0;
}
</style>

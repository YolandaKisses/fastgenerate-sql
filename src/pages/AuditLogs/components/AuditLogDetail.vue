<script setup lang="ts">
import { NCard, NDescriptions, NDescriptionsItem, NTag, NText, NScrollbar } from 'naive-ui'

const props = defineProps<{
  log: any | null
}>()

const getStatusLabel = (log: any) => {
  if (!log.executed) return '未执行'
  if (log.execution_status === 'success') return '执行成功'
  if (log.execution_status === 'empty') return '无数据'
  return '执行失败'
}

const getStatusType = (log: any) => {
  if (!log.executed) return 'warning'
  if (log.execution_status === 'success') return 'success'
  if (log.execution_status === 'empty') return 'info'
  return 'error'
}

const formatTime = (iso: string) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

const parseUsedNotes = (value: string | null | undefined) => {
  if (!value) return []
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}
</script>

<template>
  <n-card class="detail-card" :bordered="true" title="日志详情">
    <template v-if="log">
      <n-descriptions label-placement="top" :column="1" size="small">
        <n-descriptions-item label="提问时间">
          <n-text depth="2" style="font-family: 'JetBrains Mono', monospace; font-size: 13px;">{{ formatTime(log.created_at) }}</n-text>
        </n-descriptions-item>
        
        <n-descriptions-item label="数据源">
          <n-text>{{ log.datasource_name }}</n-text>
        </n-descriptions-item>

        <n-descriptions-item label="用户问题">
          <n-text strong>{{ log.question }}</n-text>
        </n-descriptions-item>

        <n-descriptions-item v-if="parseUsedNotes(log.used_notes).length > 0" label="命中笔记">
          <div class="note-list">
            <div v-for="note in parseUsedNotes(log.used_notes)" :key="note" class="note-item">{{ note }}</div>
          </div>
        </n-descriptions-item>
        
        <n-descriptions-item v-if="log.clarified" label="澄清内容">
          <n-text type="warning">{{ log.clarification_content }}</n-text>
        </n-descriptions-item>
        
        <n-descriptions-item label="生成 SQL">
          <div v-if="log.sql" class="sql-box">
            <n-scrollbar x-scrollable>
              <pre>{{ log.sql }}</pre>
            </n-scrollbar>
          </div>
          <n-text v-else depth="3">未生成 SQL</n-text>
        </n-descriptions-item>
        
        <n-descriptions-item label="执行状态">
          <n-tag :type="getStatusType(log)" size="small" :bordered="false" style="font-weight: bold;">
            {{ getStatusLabel(log) }}
          </n-tag>
        </n-descriptions-item>
        
        <n-descriptions-item v-if="log.duration_ms" label="执行耗时">
          <n-text style="font-family: 'JetBrains Mono', monospace;">{{ log.duration_ms }}ms</n-text>
        </n-descriptions-item>
        
        <n-descriptions-item v-if="log.row_count != null" label="返回行数">
          <n-text>{{ log.row_count }} 行</n-text>
        </n-descriptions-item>
        
        <n-descriptions-item v-if="log.error_summary" label="错误信息">
          <n-text type="error" style="word-break: break-all;">{{ log.error_summary }}</n-text>
        </n-descriptions-item>
      </n-descriptions>
    </template>
    <div v-else class="empty-state">
      <n-text depth="3">请选择一条日志查看详情</n-text>
    </div>
  </n-card>
</template>

<style scoped>
.detail-card {
  border-radius: 8px;
  border-color: #efeff5;
  box-shadow: none;
  height: 100%;
}

.sql-box {
  background-color: #111827;
  border-radius: 6px;
  padding: 12px;
  margin-top: 4px;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.sql-box pre {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #f8fafc;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
}

.note-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.note-item {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #5b5f6d;
  background: #f7f8fb;
  border: 1px solid #eceef5;
  border-radius: 6px;
  padding: 6px 8px;
}
</style>

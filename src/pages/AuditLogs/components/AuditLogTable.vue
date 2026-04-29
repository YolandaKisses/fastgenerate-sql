<script setup lang="ts">
import { NTag } from 'naive-ui'

const props = defineProps<{
  logs: Array<any>
  selectedId?: number | null
}>()

const emit = defineEmits(['select', 'delete'])

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

const handleDelete = (e: Event, id: number) => {
  e.stopPropagation()
  emit('delete', id)
}
</script>

<template>
  <div class="table-wrapper">
    <table class="data-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>数据源</th>
          <th>问题</th>
          <th>状态</th>
          <th>耗时</th>
          <th style="width: 50px;">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="logs.length === 0">
          <td colspan="6" style="text-align: center; color: #717785; padding: 32px;">暂无日志记录</td>
        </tr>
        <tr 
          v-for="log in logs" 
          :key="log.id" 
          :class="{'selected-row': selectedId === log.id}"
          @click="emit('select', log.id)"
        >
          <td style="width: 160px; font-family: 'JetBrains Mono', monospace; font-size: 12px; white-space: nowrap;">{{ formatTime(log.created_at) }}</td>
          <td style="width: 120px; font-size: 12px;">{{ log.datasource_name }}</td>
          <td class="question-cell">{{ log.question }}</td>
          <td style="width: 90px;">
            <n-tag :type="getStatusType(log)" size="small" :bordered="false" style="font-weight: bold;">
              {{ getStatusLabel(log) }}
            </n-tag>
          </td>
          <td style="width: 70px; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
            {{ log.duration_ms ? log.duration_ms + 'ms' : '-' }}
          </td>
          <td style="width: 50px;">
            <button class="delete-btn" title="删除" @click="handleDelete($event, log.id)">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrapper {
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #efeff5;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 14px;
}

.data-table th {
  background-color: #f7f7fa;
  padding: 12px 16px;
  font-weight: 600;
  color: #414753;
  border-bottom: 1px solid #efeff5;
  white-space: nowrap;
}

.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #efeff5;
  color: #181c22;
  cursor: pointer;
}

.data-table tbody tr:hover {
  background-color: #f1f3fd;
}

.selected-row {
  background-color: #eef0fa;
}

.question-cell {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.delete-btn {
  background: transparent;
  border: none;
  color: #c1c6d6;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.delete-btn:hover {
  color: #e53e3e;
  background-color: #fef2f2;
}
</style>

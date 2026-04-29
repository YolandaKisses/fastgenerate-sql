<script setup lang="ts">
import { NSpace, NText, NTag } from 'naive-ui'

const props = defineProps<{
  result: {
    status: string
    columns?: string[]
    column_comments?: Record<string, string>
    rows?: any[]
    row_count?: number
    duration_ms?: number
    message?: string
  }
}>()

const getColumnLabel = (col: string) => {
  if (props.result.column_comments && props.result.column_comments[col]) {
    return props.result.column_comments[col]
  }
  return col
}
</script>

<template>
  <div class="result-container">
    <!-- 错误状态 -->
    <div v-if="result.status === 'error'" class="error-box">
      <n-text type="error" style="font-weight: 600;">执行失败</n-text>
      <n-text depth="2" style="font-size: 13px; margin-top: 4px;">{{ result.message }}</n-text>
    </div>

    <!-- 空数据 -->
    <div v-else-if="result.status === 'empty'" class="empty-box">
      <n-text depth="3">查询成功，但没有返回任何数据。</n-text>
    </div>

    <!-- 正常结果 -->
    <template v-else>
      <div class="result-header">
        <n-space align="center" :size="16">
          <h2 class="result-title">查询结果</h2>
          <span class="result-meta">
            返回 {{ result.row_count }} 条记录 (用时 {{ result.duration_ms }}ms)
          </span>
        </n-space>
      </div>

      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="col in result.columns" :key="col" :title="col">{{ getColumnLabel(col) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in result.rows" :key="idx" :class="{'alt-row': idx % 2 === 1}">
              <td v-for="col in result.columns" :key="col" class="font-code">
                {{ row[col] ?? 'NULL' }}
              </td>
            </tr>
          </tbody>
        </table>

        <div class="pagination-bar">
          <span class="page-info">显示第 1-{{ result.row_count }} 条，共 {{ result.row_count }} 条数据 (上限 500)</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.result-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #181c22;
}

.result-meta {
  font-size: 12px;
  color: #717785;
}

.error-box {
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.empty-box {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background-color: #f7f7fa;
  border: 1px solid #efeff5;
  border-radius: 8px;
}

.table-wrapper {
  background: #ffffff;
  border: 1px solid #efeff5;
  border-radius: 8px;
  overflow: hidden;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13px;
}

.data-table th {
  background-color: #f7f7fa;
  padding: 12px;
  font-weight: 600;
  color: #414753;
  border-bottom: 1px solid #efeff5;
  white-space: nowrap;
}

.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #efeff5;
  color: #181c22;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.font-code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

.alt-row {
  background-color: #fbfcfd;
}

.data-table tbody tr:hover {
  background-color: #f1f3fd;
}

.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #f7f7fa;
  font-size: 12px;
  color: #717785;
}
</style>

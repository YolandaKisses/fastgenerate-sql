<script setup lang="ts">
import { NSpace, NText, NButton } from 'naive-ui'

const props = defineProps<{
  sql: string
  explanation?: string
}>()

const emit = defineEmits(['execute'])
</script>

<template>
  <div class="sql-editor-container">
    <div class="editor-header">
      <n-space align="center" :size="8">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
        <span class="filename">AI 生成的 SQL</span>
        <span class="status-dot"></span>
      </n-space>
      
      <n-space align="center" :size="16">
        <button class="run-all-btn" @click="emit('execute')">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.5 10.5 21 3"></path><path d="M16 3h5v5"></path><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"></path></svg>
          确认并执行
        </button>
      </n-space>
    </div>
    
    <div v-if="explanation" class="explanation-bar">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
      <span>{{ explanation }}</span>
    </div>

    <div class="editor-body">
      <div class="line-numbers">
        <span v-for="(_, idx) in sql.split('\n')" :key="idx">{{ idx + 1 }}</span>
      </div>
      <div class="code-content">
        <pre>{{ sql }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sql-editor-container {
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
  border: 1px solid #efeff5;
  border-radius: 8px;
  overflow: hidden;
}

.editor-header {
  height: 40px;
  background-color: #f7f7fa;
  border-bottom: 1px solid #efeff5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

.text-muted {
  color: #717785;
}

.filename {
  font-size: 12px;
  font-weight: 500;
  color: #414753;
  font-family: 'Inter', sans-serif;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #22c55e;
}

.explanation-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background-color: #eef6ff;
  border-bottom: 1px solid #d0e3f7;
  font-size: 13px;
  color: #1e5ca6;
}

.run-all-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background-color: #2080f0;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
  font-family: 'Inter', sans-serif;
}

.run-all-btn:hover {
  background-color: #0073e0;
}

.editor-body {
  flex: 1;
  display: flex;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 20px;
  padding: 16px;
  background-color: #ffffff;
  min-height: 120px;
}

.line-numbers {
  width: 40px;
  display: flex;
  flex-direction: column;
  text-align: right;
  padding-right: 16px;
  color: #c1c6d6;
  border-right: 1px solid #efeff5;
  margin-right: 16px;
  user-select: none;
}

.code-content {
  flex: 1;
  overflow: auto;
}

pre {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

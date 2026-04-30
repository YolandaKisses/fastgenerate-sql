<script setup lang="ts">
import { NSpace, NText, NButton, NIcon } from 'naive-ui'
import { FileTrayOutline, PlayOutline, InformationCircleOutline } from '@vicons/ionicons5'

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
        <n-icon :component="FileTrayOutline" color="#717785" />
        <span class="filename">AI 生成的 SQL</span>
        <span class="status-dot"></span>
      </n-space>
      
      <n-space align="center" :size="16">
        <n-button type="primary" size="tiny" @click="emit('execute')">
          <template #icon>
            <n-icon :component="PlayOutline" />
          </template>
          确认并执行
        </n-button>
      </n-space>
    </div>
    
    <div v-if="explanation" class="explanation-bar">
      <n-icon :component="InformationCircleOutline" />
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

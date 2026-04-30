<script setup lang="ts">
import { computed } from 'vue'
import { NSpace, NText, NButton, NIcon } from 'naive-ui'
import { FileTrayOutline, PlayOutline, InformationCircleOutline, HourglassOutline, CheckmarkCircleOutline, CloseCircleOutline } from '@vicons/ionicons5'

const props = defineProps<{
  sql: string
  displayedSql?: string
  isRendering?: boolean
  explanation?: string
  validationState?: 'idle' | 'validating' | 'valid' | 'invalid'
  validationReasons?: string[]
  executed?: boolean
  executionStatus?: string | null
}>()

const emit = defineEmits(['execute'])

// 展示用的 SQL：渐进渲染期间用 displayedSql，完成后用完整 sql
const visibleSql = computed(() => {
  if (props.isRendering && props.displayedSql !== undefined) {
    return props.displayedSql
  }
  return props.sql
})

const isExecuteDisabled = computed(() => {
  return props.executed || props.isRendering || props.validationState === 'validating' || props.validationState === 'invalid'
})

const executeButtonText = computed(() => {
  if (!props.executed) return '确认并执行'
  if (props.executionStatus === 'error') return '执行失败'
  if (props.executionStatus === 'empty') return '已执行，无结果'
  return '已执行'
})
</script>

<template>
  <div class="sql-editor-container">
    <div class="editor-header">
      <n-space align="center" :size="8">
        <n-icon :component="FileTrayOutline" color="#717785" />
        <span class="filename">AI 生成的 SQL</span>
        <span class="status-dot" :class="{ 'dot-rendering': isRendering }"></span>
      </n-space>
      
      <n-space align="center" :size="16">
        <n-button type="primary" size="tiny" :disabled="isExecuteDisabled" @click="emit('execute')">
          <template #icon>
            <n-icon :component="executed ? CheckmarkCircleOutline : PlayOutline" />
          </template>
          {{ executeButtonText }}
        </n-button>
      </n-space>
    </div>
    
    <div v-if="explanation" class="explanation-bar">
      <n-icon :component="InformationCircleOutline" />
      <span>{{ explanation }}</span>
    </div>

    <!-- SQL 校验状态栏 -->
    <div v-if="validationState && validationState !== 'idle'" class="validation-bar" :class="'is-' + validationState">
      <div class="validation-header">
        <n-icon v-if="validationState === 'validating'" :component="HourglassOutline" class="spin-icon" />
        <n-icon v-else-if="validationState === 'valid'" :component="CheckmarkCircleOutline" />
        <n-icon v-else :component="CloseCircleOutline" />
        <span class="validation-title">
          {{ validationState === 'validating' ? '正在进行安全与规范校验...' :
             validationState === 'valid' ? '校验通过，允许执行' : '校验失败，存在安全风险或语法问题' }}
        </span>
      </div>
      <ul v-if="validationState === 'invalid' && validationReasons && validationReasons.length > 0" class="validation-reasons">
        <li v-for="(reason, idx) in validationReasons" :key="idx">{{ reason }}</li>
      </ul>
    </div>

    <div class="editor-body">
      <div class="line-numbers">
        <span v-for="(_, idx) in visibleSql.split('\n')" :key="idx">{{ idx + 1 }}</span>
      </div>
      <div class="code-content">
        <pre>{{ visibleSql }}<span v-if="isRendering" class="cursor-blink">▌</span></pre>
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
  transition: background-color 0.3s;
}

.dot-rendering {
  background-color: #f59e0b;
  animation: pulse-dot 1s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
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

.cursor-blink {
  color: #6b5fbf;
  animation: blink 0.8s step-end infinite;
  font-weight: 300;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.validation-bar {
  padding: 10px 16px;
  font-size: 13px;
  border-bottom: 1px solid #efeff5;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.validation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.validation-title {
  flex: 1;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.validation-bar.is-validating {
  background-color: #fef9c3; /* tailwind yellow-100 */
  color: #854d0e; /* tailwind yellow-800 */
  border-bottom-color: #fef08a; /* tailwind yellow-200 */
}

.validation-bar.is-valid {
  background-color: #dcfce7; /* tailwind green-100 */
  color: #166534; /* tailwind green-800 */
  border-bottom-color: #bbf7d0; /* tailwind green-200 */
}

.validation-bar.is-invalid {
  background-color: #fee2e2; /* tailwind red-100 */
  color: #991b1b; /* tailwind red-800 */
  border-bottom-color: #fecaca; /* tailwind red-200 */
}

.validation-reasons {
  margin: 0;
  padding-left: 24px;
  list-style-type: disc;
  color: #b91c1c; /* tailwind red-700 */
}
</style>

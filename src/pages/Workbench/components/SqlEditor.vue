<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { NSpace, NButton, NIcon, NInput } from 'naive-ui'
import { 
  FileTrayOutline, PlayOutline, InformationCircleOutline, 
  HourglassOutline, CheckmarkCircleOutline, CloseCircleOutline,
  CreateOutline, SaveOutline
} from '@vicons/ionicons5'

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

const emit = defineEmits(['execute', 'update:sql', 'revalidate'])

const isEditing = ref(false)
const internalSql = ref(props.sql)

// 当外部 sql 变化（比如流式输出时），更新内部值
watch(() => props.sql, (newVal) => {
  if (!isEditing.value) {
    internalSql.value = newVal
  }
})

const visibleSql = computed(() => {
  if (props.isRendering && props.displayedSql !== undefined) {
    return props.displayedSql
  }
  return isEditing.value ? internalSql.value : props.sql
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

const handleStartEdit = () => {
  internalSql.value = props.sql
  isEditing.value = true
}

const handleSaveEdit = () => {
  isEditing.value = false
  if (internalSql.value !== props.sql) {
    emit('update:sql', internalSql.value)
    emit('revalidate', internalSql.value)
  }
}

const handleCancelEdit = () => {
  internalSql.value = props.sql
  isEditing.value = false
}
</script>

<template>
  <div class="sql-editor-container" :class="{ 'is-editing-mode': isEditing }">
    <div class="editor-header">
      <n-space align="center" :size="8">
        <n-icon :component="FileTrayOutline" color="#717785" />
        <span class="filename">{{ isEditing ? '编辑 SQL 语句' : 'AI 生成的 SQL' }}</span>
        <span v-if="!isEditing" class="status-dot" :class="{ 'dot-rendering': isRendering }"></span>
      </n-space>
      
      <n-space align="center" :size="12">
        <!-- 编辑/保存按钮 -->
        <template v-if="!executed && !isRendering">
          <n-button v-if="!isEditing" quaternary size="tiny" @click="handleStartEdit">
            <template #icon><n-icon :component="CreateOutline" /></template>
            修改
          </n-button>
          <template v-else>
            <n-button quaternary size="tiny" @click="handleCancelEdit">取消</n-button>
            <n-button type="primary" secondary size="tiny" @click="handleSaveEdit">
              <template #icon><n-icon :component="SaveOutline" /></template>
              保存修改
            </n-button>
          </template>
        </template>

        <n-button type="primary" size="tiny" :disabled="isExecuteDisabled || isEditing" @click="emit('execute')">
          <template #icon>
            <n-icon :component="executed ? CheckmarkCircleOutline : PlayOutline" />
          </template>
          {{ executeButtonText }}
        </n-button>
      </n-space>
    </div>
    
    <div v-if="explanation && !isEditing" class="explanation-bar">
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
             validationState === 'valid' ? '校验通过，允许执行' : '校验失败' }}
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
        <template v-if="isEditing">
          <textarea 
            v-model="internalSql" 
            class="sql-textarea" 
            spellcheck="false"
            placeholder="请输入 SQL 语句..."
          ></textarea>
        </template>
        <pre v-else>{{ visibleSql }}<span v-if="isRendering" class="cursor-blink">▌</span></pre>
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
  transition: all 0.3s ease;
}

.is-editing-mode {
  border-color: #6b5fbf;
  box-shadow: 0 0 0 2px rgba(107, 95, 191, 0.1);
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
  position: relative;
}

.sql-textarea {
  width: 100%;
  height: 100%;
  min-height: 100px;
  border: none;
  padding: 0;
  margin: 0;
  background: transparent;
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
  color: #1f2225;
  resize: none;
  outline: none;
}

pre {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  color: #1f2225;
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
  background-color: #fef9c3;
  color: #854d0e;
  border-bottom-color: #fef08a;
}

.validation-bar.is-valid {
  background-color: #dcfce7;
  color: #166534;
  border-bottom-color: #bbf7d0;
}

.validation-bar.is-invalid {
  background-color: #fee2e2;
  color: #991b1b;
  border-bottom-color: #fecaca;
}

.validation-reasons {
  margin: 0;
  padding-left: 24px;
  list-style-type: disc;
  color: #b91c1c;
}
</style>

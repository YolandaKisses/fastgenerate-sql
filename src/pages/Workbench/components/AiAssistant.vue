<script setup lang="ts">
import { ref } from 'vue'
import { NSpace, NText } from 'naive-ui'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits(['submit'])
const query = ref('')

const handleGenerate = () => {
  if (query.value.trim()) {
    emit('submit', query.value)
    query.value = ''
  }
}
</script>

<template>
  <div class="ai-assistant">
    <div style="margin-bottom: 16px;">
      <n-text style="font-size: 20px; font-weight: 600; color: #181c22;">AI 查询助手</n-text>
      <div class="assistant-hint">常见澄清场景将优先提示，不会直接猜测。</div>
    </div>

    <label class="sr-only" for="natural-language-question">自然语言问题</label>
    <div class="input-wrapper">
      <div class="input-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
      </div>
      <input 
        id="natural-language-question"
        aria-label="自然语言问题"
        v-model="query" 
        class="custom-input" 
        placeholder="描述您想查询的数据，例如：'按城市统计用户数量'" 
        :disabled="disabled"
        @keydown.enter="handleGenerate"
      />
      <button class="generate-btn" :disabled="disabled || !query.trim()" @click="handleGenerate">
        生成 SQL
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 4px;"><polyline points="9 10 4 15 9 20"></polyline><path d="M20 4v7a4 4 0 0 1-4 4H4"></path></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.ai-assistant {
  display: flex;
  flex-direction: column;
}

.assistant-hint {
  font-size: 13px;
  color: #717785;
  margin-top: 8px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 16px;
  color: #2080f0;
  pointer-events: none;
}

.custom-input {
  width: 100%;
  padding: 16px 140px 16px 48px;
  border: 1px solid #efeff5;
  border-radius: 8px;
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  color: #181c22;
  outline: none;
  background-color: #ffffff;
  transition: all 0.2s;
}

.custom-input:focus {
  border-color: #2080f0;
  box-shadow: 0 0 0 4px rgba(32, 128, 240, 0.1);
}

.custom-input:disabled {
  background-color: #f7f7fa;
  cursor: not-allowed;
}

.generate-btn {
  position: absolute;
  right: 8px;
  top: 8px;
  bottom: 8px;
  padding: 0 24px;
  background-color: #2080f0;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  font-family: 'Inter', sans-serif;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: background-color 0.2s;
}

.generate-btn:hover:not(:disabled) {
  background-color: #0073e0;
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
</style>

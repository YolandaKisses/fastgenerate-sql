<script setup lang="ts">
import { NAlert, NCard, NEmpty, NTag } from 'naive-ui'

defineProps<{
  answer: string
  sources: Array<{
    title: string
    path: string
    source_type: string
    snippet: string
  }>
}>()

const emit = defineEmits<{
  openSource: [path: string]
}>()
</script>

<template>
  <n-card title="回答与引用" class="answer-panel">
    <template #header-extra>
      <n-tag type="success" round>可追溯</n-tag>
    </template>

    <n-empty v-if="!answer" description="提交问题后，这里会展示答案与引用来源。" />

    <div v-else class="answer-content">
      <n-alert type="info" :show-icon="false">
        <div class="answer-text">{{ answer }}</div>
      </n-alert>

      <div class="source-list">
        <div v-for="source in sources" :key="`${source.path}-${source.title}`" class="source-card">
          <div class="source-meta">
            <strong>{{ source.title }}</strong>
            <n-tag size="small" type="warning">{{ source.source_type }}</n-tag>
          </div>
          <p class="source-path">{{ source.path }}</p>
          <p class="source-snippet">{{ source.snippet }}</p>
          <button class="source-link" type="button" @click="emit('openSource', source.path)">
            跳转到 Wiki 原文
          </button>
        </div>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.answer-panel {
  border-radius: 20px;
  border: 1px solid #e8edf5;
  min-height: 0;
}

.answer-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.answer-text {
  white-space: pre-wrap;
  line-height: 1.75;
  color: #1e293b;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-card {
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #fffaf2 0%, #fff 100%);
  border: 1px solid #f3e6c8;
}

.source-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.source-path {
  margin: 8px 0 4px;
  font-size: 12px;
  color: #64748b;
  word-break: break-all;
}

.source-snippet {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
}

.source-link {
  margin-top: 10px;
  border: none;
  background: none;
  color: #0f766e;
  cursor: pointer;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
}
</style>

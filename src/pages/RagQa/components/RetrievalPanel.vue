<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NEmpty, NProgress, NTag } from 'naive-ui'

const props = defineProps<{
  items: Array<{
    chunk_id: string
    score: number
    title: string
    path: string
    source_type: string
    snippet: string
  }>
  retrieval: {
    matched_count: number
    direct_hits: number
    source_types: string[]
    top_k_used: number
  } | null
  diagnostics: {
    related_entities: Array<{
      name: string
      entity_type: string
      path: string
      score: number
    }>
    related_relations: Array<{
      subject: string
      predicate: string
      object: string
      path: string
      score: number
    }>
  } | null
}>()

const emit = defineEmits<{
  openSource: [path: string]
}>()

const maxScore = computed(() => {
  const highest = props.items[0]?.score ?? 0
  return highest > 0 ? highest : 1
})
</script>

<template>
  <n-card title="召回证据" class="retrieval-panel">
    <template #header-extra>
      <n-tag v-if="retrieval" type="info" round>{{ retrieval.matched_count }} 命中</n-tag>
    </template>

    <n-empty v-if="!retrieval" description="这里会展示命中的文档和片段。" />

    <div v-else class="retrieval-content">
      <div class="retrieval-summary">
        <div class="summary-item">
          <span class="summary-label">直接命中</span>
          <strong>{{ retrieval.direct_hits }}</strong>
        </div>
        <div class="summary-item">
          <span class="summary-label">来源类型</span>
          <strong>{{ retrieval.source_types.join(' / ') || '未限制' }}</strong>
        </div>
        <div class="summary-item">
          <span class="summary-label">Top-K</span>
          <strong>{{ retrieval.top_k_used }}</strong>
        </div>
      </div>

      <div class="retrieval-list">
        <div v-for="item in items" :key="item.chunk_id" class="retrieval-item">
          <div class="item-head">
            <div>
              <strong>{{ item.title }}</strong>
              <p class="item-path">{{ item.path }}</p>
            </div>
            <n-tag size="small">{{ item.source_type }}</n-tag>
          </div>

          <n-progress
            type="line"
            :percentage="Math.max(1, Math.round((item.score / maxScore) * 100))"
            :show-indicator="false"
            processing
            color="#0f766e"
          />

          <p class="item-snippet">{{ item.snippet }}</p>
          <button class="item-link" type="button" @click="emit('openSource', item.path)">
            在 Wiki 中查看
          </button>
        </div>
      </div>

      <div v-if="diagnostics?.related_entities?.length" class="diagnostic-section">
        <h4>相关实体</h4>
        <div class="diagnostic-list">
          <div v-for="entity in diagnostics.related_entities" :key="`${entity.name}-${entity.path}`" class="diagnostic-card">
            <strong>{{ entity.name }}</strong>
            <p>{{ entity.entity_type }} · {{ entity.path }}</p>
          </div>
        </div>
      </div>

      <div v-if="diagnostics?.related_relations?.length" class="diagnostic-section">
        <h4>相关关系</h4>
        <div class="diagnostic-list">
          <div
            v-for="relation in diagnostics.related_relations"
            :key="`${relation.subject}-${relation.predicate}-${relation.object}-${relation.path}`"
            class="diagnostic-card"
          >
            <strong>{{ relation.subject }} {{ relation.predicate }} {{ relation.object }}</strong>
            <p>{{ relation.path }}</p>
          </div>
        </div>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.retrieval-panel {
  border-radius: 20px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  min-height: 0;
}

.retrieval-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.retrieval-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  padding: 14px;
  border-radius: 14px;
  background: #eff6ff;
  border: 1px solid #dbeafe;
}

.summary-label {
  display: block;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 6px;
}

.retrieval-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.retrieval-item {
  padding: 14px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.diagnostic-section h4 {
  margin: 0 0 10px;
  color: #0f172a;
}

.diagnostic-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.diagnostic-card {
  padding: 12px 14px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.diagnostic-card p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 12px;
  word-break: break-all;
}

.item-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.item-path {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
  word-break: break-all;
}

.item-snippet {
  margin: 12px 0 8px;
  color: #334155;
  line-height: 1.7;
}

.item-link {
  border: none;
  background: none;
  color: #1d4ed8;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

@media (max-width: 960px) {
  .retrieval-summary {
    grid-template-columns: 1fr;
  }
}
</style>

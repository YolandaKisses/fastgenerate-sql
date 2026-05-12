<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import AskPanel from './components/AskPanel.vue'
import AnswerPanel from './components/AnswerPanel.vue'
import RetrievalPanel from './components/RetrievalPanel.vue'
import { post } from '../../services/request'

type RagSearchItem = {
  chunk_id: string
  score: number
  title: string
  path: string
  source_type: string
  datasource: string
  object_type?: string
  object_name?: string
  snippet: string
}

type RagRetrieval = {
  matched_count: number
  direct_hits: number
  source_types: string[]
  top_k_used: number
}

type RagDiagnostics = {
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
}

const router = useRouter()
const message = useMessage()

const loading = ref(false)
const answer = ref('')
const sources = ref<RagSearchItem[]>([])
const retrievalItems = ref<RagSearchItem[]>([])
const retrieval = ref<RagRetrieval | null>(null)
const diagnostics = ref<RagDiagnostics | null>(null)

const handleAsk = async (payload: {
  query: string
  datasource?: string
  demand_name?: string
  object_type?: string
  source_types?: string[]
  top_k: number
}) => {
  loading.value = true
  try {
    const response = await post<{
      answer: string
      sources: RagSearchItem[]
      retrieval: RagRetrieval
      diagnostics: RagDiagnostics
    }>('/rag/ask', payload)
    const searchResponse = await post<{
      items: RagSearchItem[]
      retrieval: RagRetrieval
      diagnostics: RagDiagnostics
    }>('/rag/search', payload)

    answer.value = response.answer
    sources.value = response.sources
    retrievalItems.value = searchResponse.items
    retrieval.value = response.retrieval
    diagnostics.value = response.diagnostics
  } catch (error: any) {
    message.error(error.message || '问答请求失败')
  } finally {
    loading.value = false
  }
}

const openWikiSource = (path: string) => {
  router.push({ path: '/wiki', query: { path } })
}
</script>

<template>
  <div class="rag-page">
    <section class="hero">
      <div>
        <p class="eyebrow">Knowledge QA</p>
        <h2>把本地 Wiki、需求文档和表结构串成真正可追溯的问答链路</h2>
        <p class="hero-copy">
          问题会先经过本地知识检索，再交给 Hermes 基于证据生成答案。每条回答都保留来源和命中片段，方便快速回溯原文。
        </p>
      </div>
    </section>

    <section class="rag-grid">
      <div class="left-column">
        <AskPanel :loading="loading" @submit="handleAsk" />
        <AnswerPanel :answer="answer" :sources="sources" @open-source="openWikiSource" />
      </div>
      <div class="right-column">
        <RetrievalPanel :items="retrievalItems" :retrieval="retrieval" :diagnostics="diagnostics" @open-source="openWikiSource" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.rag-page {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.hero {
  padding: 28px 32px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.18), transparent 32%),
    radial-gradient(circle at top right, rgba(30, 64, 175, 0.16), transparent 28%),
    linear-gradient(135deg, #fffdf5 0%, #f8fbff 45%, #f6fffb 100%);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #0f766e;
}

.hero h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
  color: #0f172a;
  max-width: 840px;
}

.hero-copy {
  margin: 14px 0 0;
  max-width: 760px;
  line-height: 1.8;
  color: #475569;
}

.rag-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.9fr);
  gap: 20px;
}

.left-column,
.right-column {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 1120px) {
  .rag-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hero {
    padding: 22px;
    border-radius: 22px;
  }

  .hero h2 {
    font-size: 24px;
  }
}
</style>

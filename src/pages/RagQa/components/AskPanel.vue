<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NCard, NCheckbox, NCheckboxGroup, NForm, NFormItem, NInput, NSelect, NSpace, NTag } from 'naive-ui'

const props = defineProps<{
  loading?: boolean
}>()

const emit = defineEmits<{
  submit: [
    {
      query: string
      datasource?: string
      demand_name?: string
      object_type?: string
      source_types?: string[]
      top_k: number
    },
  ]
}>()

const query = ref('')
const datasource = ref('')
const demandName = ref('')
const objectType = ref<string | null>(null)
const sourceTypes = ref<string[]>(['demand', 'schema', 'lineage'])
const topK = ref(8)

const sourceTypeOptions = [
  { label: '需求文档', value: 'demand' },
  { label: '表结构/视图/过程', value: 'schema' },
  { label: '血缘说明', value: 'lineage' },
  { label: '通用 Wiki', value: 'wiki' },
]

const topKOptions = [5, 8, 10, 12].map((value) => ({ label: `Top ${value}`, value }))
const objectTypeOptions = [
  { label: '全部对象', value: null },
  { label: '表', value: 'table' },
  { label: '视图', value: 'view' },
  { label: '过程', value: 'routine' },
  { label: '血缘', value: 'lineage' },
]

const canSubmit = computed(() => query.value.trim().length > 0)

const handleSubmit = () => {
  if (!canSubmit.value) {
    return
  }
  emit('submit', {
    query: query.value.trim(),
    datasource: datasource.value || undefined,
    demand_name: demandName.value.trim() || undefined,
    object_type: objectType.value || undefined,
    source_types: sourceTypes.value.length ? sourceTypes.value : undefined,
    top_k: topK.value,
  })
}
</script>

<template>
  <n-card title="知识问答" class="ask-panel">
    <template #header-extra>
      <n-tag type="info" round>RAG + Hermes</n-tag>
    </template>

    <n-form label-placement="top">
      <n-form-item label="问题">
        <n-input
          v-model:value="query"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 8 }"
          placeholder="例如：east 报送明细表和账户资料表的关联键是什么？"
          @keydown.enter.exact.prevent="handleSubmit"
        />
      </n-form-item>

      <n-form-item label="数据源（可选）">
        <n-input v-model:value="datasource" placeholder="例如：dd_etl" />
      </n-form-item>

      <n-form-item label="需求分类（可选）">
        <n-input v-model:value="demandName" placeholder="例如：east报送" />
      </n-form-item>

      <n-form-item label="对象类型（可选）">
        <n-select v-model:value="objectType" :options="objectTypeOptions" />
      </n-form-item>

      <n-form-item label="来源类型">
        <n-checkbox-group v-model:value="sourceTypes">
          <n-space>
            <n-checkbox v-for="option in sourceTypeOptions" :key="option.value" :value="option.value" :label="option.label" />
          </n-space>
        </n-checkbox-group>
      </n-form-item>

      <n-form-item label="召回数量">
        <n-select v-model:value="topK" :options="topKOptions" />
      </n-form-item>

      <n-button type="primary" size="large" :loading="props.loading" :disabled="!canSubmit" @click="handleSubmit">
        发起问答
      </n-button>
    </n-form>
  </n-card>
</template>

<style scoped>
.ask-panel {
  border-radius: 20px;
  border: 1px solid #e8edf5;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
}

.checkbox-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #334155;
}
</style>

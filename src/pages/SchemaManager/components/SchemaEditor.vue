<script setup lang="ts">
import { ref, watch } from 'vue'
import { NCard, NSpace, NText, NButton, NInput, useMessage } from 'naive-ui'

const props = defineProps<{
  table: any | null
}>()

const emit = defineEmits(['sync'])
const message = useMessage()

const fields = ref<any[]>([])

const fetchFields = async (tableId: number) => {
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/fields/${tableId}`)
    if (res.ok) {
      fields.value = await res.json()
    }
  } catch (error) {
    message.error('无法加载字段信息')
  }
}

watch(() => props.table, (newTable) => {
  if (newTable && newTable.id) {
    fetchFields(newTable.id)
  } else {
    fields.value = []
  }
}, { immediate: true })

let saveTimeout: any = null
const handleRemarkChange = (fieldId: number, remark: string) => {
  if (saveTimeout) clearTimeout(saveTimeout)
  saveTimeout = setTimeout(async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/fields/${fieldId}/remark`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remark })
      })
      if (!res.ok) {
        message.error('保存备注失败')
      }
    } catch {
      message.error('保存备注网络异常')
    }
  }, 500) // 500ms debounce
}
</script>

<template>
  <n-card v-if="table" class="editor-card" :bordered="true">
    <template #header>
      <n-space align="center" :size="12">
        <n-text style="font-size: 18px; font-weight: 600; font-family: 'JetBrains Mono', monospace;">{{ table.name }}</n-text>
        <n-text depth="3">{{ table.original_comment }}</n-text>
      </n-space>
    </template>
    
    <template #header-extra>
      <n-space>
        <n-button type="primary" @click="emit('sync')">重新同步该数据源</n-button>
      </n-space>
    </template>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>字段名</th>
            <th>类型</th>
            <th>原始备注</th>
            <th style="width: 40%;">本地补充备注 (自动保存)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="field in fields" :key="field.id">
            <td class="font-code field-name">{{ field.name }}</td>
            <td class="font-code field-type">{{ field.type }}</td>
            <td class="original-comment">{{ field.original_comment }}</td>
            <td class="supplementary-comment">
              <n-input 
                v-model:value="field.supplementary_comment" 
                placeholder="添加补充说明，例如枚举值含义..." 
                size="small" 
                @update:value="(val) => handleRemarkChange(field.id, val)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </n-card>
  
  <n-card v-else class="editor-card empty-state" :bordered="true">
    <n-text depth="3">请在左侧选择要管理的表，或点击同步数据源获取 Schema。</n-text>
    <n-button type="primary" style="margin-top: 16px;" @click="emit('sync')">立即同步</n-button>
  </n-card>
</template>

<style scoped>
.editor-card {
  border-radius: 8px;
  border-color: #efeff5;
  box-shadow: none;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

.table-wrapper {
  border: 1px solid #efeff5;
  border-radius: 8px;
  overflow: auto;
  flex: 1;
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
  position: sticky;
  top: 0;
  z-index: 10;
}

.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #efeff5;
  color: #181c22;
  vertical-align: middle;
}

.font-code {
  font-family: 'JetBrains Mono', monospace;
}

.field-name {
  font-weight: 500;
}

.field-type {
  color: #8250df;
  font-size: 12px;
}

.original-comment {
  color: #414753;
}

.data-table tbody tr:hover {
  background-color: #fbfcfd;
}
</style>

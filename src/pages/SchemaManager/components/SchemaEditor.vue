<script setup lang="ts">
import { ref, watch } from 'vue'
import { NButton, NInput, useMessage } from 'naive-ui'

const props = defineProps<{
  table: any | null
  knowledgeTask?: any | null
  knowledgeSyncing?: boolean
}>()

const emit = defineEmits(['sync', 'sync-knowledge'])
const message = useMessage()

const fields = ref<any[]>([])
const tableRemark = ref('')

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
    tableRemark.value = newTable.supplementary_comment || ''
    fetchFields(newTable.id)
  } else {
    tableRemark.value = ''
    fields.value = []
  }
}, { immediate: true })

let saveTimeout: any = null
const handleTableRemarkChange = (tableId: number, remark: string) => {
  if (saveTimeout) clearTimeout(saveTimeout)
  saveTimeout = setTimeout(async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/tables/${tableId}/remark`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remark })
      })
      if (!res.ok) {
        message.error('保存表级备注失败')
      }
    } catch {
      message.error('保存表级备注网络异常')
    }
  }, 500)
}

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
  }, 500)
}

</script>

<template>
  <div v-if="table" class="editor-container">
    <div class="editor-header">
      <div class="header-main">
        <span class="table-name">{{ table.name }}</span>
        <span class="table-comment">{{ table.original_comment }}</span>
      </div>
      <div class="header-actions">
        <n-button secondary size="small" @click="emit('sync')">重新同步该数据源</n-button>
        <n-button type="primary" size="small" :loading="knowledgeSyncing" @click="emit('sync-knowledge')">同步到知识库</n-button>
      </div>
    </div>

    <div class="editor-content">
      <div class="panel section">
        <label class="section-label">表级补充备注</label>
        <n-input
          v-model:value="tableRemark"
          type="textarea"
          placeholder="补充业务背景、关键口径或表的用途说明..."
          :autosize="{ minRows: 3, maxRows: 6 }"
          @update:value="handleTableRemarkChange(table.id, tableRemark)"
        />
      </div>

      <div class="panel table-section">
        <div class="section-label" style="padding: 12px 16px;">字段级补充备注</div>
        <div class="table-scroll-area">
          <table class="native-table">
            <thead>
              <tr>
                <th style="width: 15%;">字段名</th>
                <th style="width: 25%;">类型</th>
                <th style="width: 25%;">原始备注</th>
                <th style="width: 35%;">本地补充备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="field in fields" :key="field.id">
                <td class="code-font" :title="field.name">{{ field.name }}</td>
                <td class="code-font type-text" :title="field.type">{{ field.type }}</td>
                <td class="comment-text" :title="field.original_comment">{{ field.original_comment }}</td>
                <td>
                  <n-input 
                    v-model:value="field.supplementary_comment" 
                    placeholder="添加说明..."
                    size="small"
                    @update:value="(val) => handleRemarkChange(field.id, val)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="empty-container">
    <div class="empty-content">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#d9dce8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
      <p>请在左侧选择要管理的表</p>
      <n-button type="primary" size="large" style="margin-top: 16px;" @click="emit('sync')">同步数据源</n-button>
    </div>
  </div>
</template>

<style scoped>
.editor-container, .empty-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border: 1px solid #efeff5;
  border-radius: 12px;
  overflow: hidden;
}

.empty-container {
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
  color: #717785;
}

.editor-header {
  padding: 16px 20px;
  border-bottom: 1px solid #efeff5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fbfcfd;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.header-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-name {
  font-size: 18px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  color: #181c22;
}

.table-comment {
  font-size: 14px;
  color: #717785;
}

.editor-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px;
  gap: 20px;
  min-height: 0;
}


.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #414753;
  margin-bottom: 8px;
  display: block;
}

.panel {
  display: flex;
  flex-direction: column;
}

.table-section {
  flex: 1;
  min-height: 0;
  border: 1px solid #efeff5;
  border-radius: 8px;
  overflow: hidden;
}

.table-scroll-area {
  flex: 1;
  overflow: auto;
}

.native-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.native-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  table-layout: fixed; /* Fix layout jumping */
}

.native-table th {
  background: #f7f7fa;
  text-align: left;
  padding: 12px;
  font-weight: 600;
  color: #414753;
  border-bottom: 1px solid #efeff5;
  position: sticky;
  top: 0;
  z-index: 10; /* Ensure header stays above content */
}

.native-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #efeff5;
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.code-font {
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
}

.type-text {
  color: #8250df;
  font-size: 12px;
}

.comment-text {
  color: #717785;
}
</style>

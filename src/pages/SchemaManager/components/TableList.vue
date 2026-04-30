<script setup lang="ts">
import { computed, ref } from 'vue'
import { NCard, NInput, NList, NListItem, NText, NScrollbar } from 'naive-ui'

const props = defineProps<{
  tables: Array<any>
  selectedTable: any | null
}>()

const emit = defineEmits(['select'])
const keyword = ref('')

const filteredTables = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  if (!search) {
    return props.tables
  }

  return props.tables.filter((table) => {
    const haystack = [table.name, table.original_comment, table.supplementary_comment]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(search)
  })
})
</script>

<template>
  <n-card class="list-card" content-style="padding: 0; display: flex; flex-direction: column; height: 100%;">
    <div style="padding: 16px; border-bottom: 1px solid #efeff5;">
      <n-input v-model:value="keyword" placeholder="搜索表名..." size="small">
        <template #prefix>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #c1c6d6;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        </template>
      </n-input>
    </div>
    
    <n-scrollbar class="table-scroll">
      <n-list hoverable clickable class="table-list">
        <n-list-item 
          v-for="table in filteredTables" 
          :key="table.id" 
          :class="{'selected-item': selectedTable?.id === table.id}"
          @click="emit('select', table)"
        >
          <div class="table-item-content">
            <n-text strong style="font-size: 13px; font-family: 'JetBrains Mono', monospace;">{{ table.name }}</n-text>
            <n-text depth="3" style="font-size: 12px; margin-top: 4px;" class="truncate">{{ table.original_comment || '无表级注释' }}</n-text>
          </div>
        </n-list-item>
        <div v-if="filteredTables.length === 0" class="empty-state">没有匹配的表</div>
      </n-list>
    </n-scrollbar>
  </n-card>
</template>

<style scoped>
.list-card {
  border-radius: 8px;
  border: 1px solid #efeff5;
  box-shadow: none;
  background: #ffffff;
  height: 100%;
}

.table-scroll {
  flex: 1;
}

.table-list {
  background: transparent;
}

.table-item-content {
  display: flex;
  flex-direction: column;
}

.truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.selected-item {
  background-color: #eef0fa;
}

.empty-state {
  padding: 24px 16px;
  color: #717785;
  font-size: 13px;
  text-align: center;
}
</style>

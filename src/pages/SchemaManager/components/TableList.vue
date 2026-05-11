<script setup lang="ts">
import { computed, ref } from 'vue'
import { NCard, NText, NScrollbar, NInput, NIcon } from 'naive-ui'
import { SearchOutline } from '@vicons/ionicons5'

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
  <div class="list-card">
    <div class="search-box">
      <n-input v-model:value="keyword" placeholder="搜索对象名..." size="small" clearable>
        <template #prefix>
          <n-icon :component="SearchOutline" />
        </template>
      </n-input>
    </div>
    
    <n-scrollbar class="table-scroll">
      <div class="table-list">
        <div 
          v-for="table in filteredTables" 
          :key="table.id" 
          class="table-item"
          :class="{'selected-item': selectedTable?.id === table.id}"
          @click="emit('select', table)"
        >
          <div class="table-item-content">
            <n-text strong style="font-size: 13px; font-family: 'JetBrains Mono', monospace;">{{ table.name }}</n-text>
            <n-text depth="3" style="font-size: 12px; margin-top: 4px;" class="truncate">{{ table.original_comment || '无表级注释' }}</n-text>
          </div>
        </div>
        <div v-if="filteredTables.length === 0" class="empty-state">没有匹配的表</div>
      </div>
    </n-scrollbar>
  </div>
</template>

<style scoped>
.list-card {
  border-radius: 12px;
  border: 1px solid #efeff5;
  background: #ffffff;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-box {
  padding: 12px;
  border-bottom: 1px solid #efeff5;
}

.table-scroll {
  flex: 1;
  min-height: 0;
}

.table-list {
  display: flex;
  flex-direction: column;
  padding-right: 10px;
  box-sizing: border-box;
}

.table-item {
  margin: 4px 0;
  padding: 14px !important;
  cursor: pointer;
  border-radius: 8px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.table-item:hover {
  background-color: #f8f9fe;
  border-color: #e0e4f8;
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
  background-color: #eef0fa !important;
  border-color: #2080f033 !important;
  box-shadow: 0 2px 8px rgba(32, 128, 240, 0.08);
}

.empty-state {
  padding: 24px 16px;
  color: #717785;
  font-size: 13px;
  text-align: center;
}
</style>

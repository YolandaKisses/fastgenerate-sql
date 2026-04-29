<script setup lang="ts">
import { NList, NListItem, NTag, NSpace, NText } from 'naive-ui'

const props = defineProps<{
  sources: Array<{ id: number, name: string, db_type: string, status: string, host: string }>,
  selectedSource?: any | null
}>()

const emit = defineEmits(['select'])

const getStatusType = (status: string) => {
  switch (status) {
    case 'connection_ok':
    case 'ready': return 'success'
    case 'draft': return 'default'
    case 'stale': return 'warning'
    case 'connection_failed':
    case 'sync_failed': return 'error'
    default: return 'default'
  }
}
</script>

<template>
  <n-list hoverable clickable class="source-list">
    <n-list-item 
      v-for="source in sources" 
      :key="source.id" 
      :class="{'selected-item': selectedSource?.id === source.id}"
      @click="emit('select', source)"
    >
      <n-space justify="space-between" align="center">
        <n-space align="center" :size="12">
          <div class="icon-box">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
          </div>
          <div>
            <n-text strong style="font-size: 14px">{{ source.name }}</n-text>
            <br>
            <n-text depth="3" style="font-size: 11px">{{ source.db_type }} • {{ source.host }}</n-text>
          </div>
        </n-space>
        <n-tag :type="getStatusType(source.status)" size="small" round style="font-weight: bold; font-size: 10px;">
          {{ source.status }}
        </n-tag>
      </n-space>
    </n-list-item>
  </n-list>
</template>

<style scoped>
.source-list {
  background: transparent;
}
.icon-box {
  width: 32px;
  height: 32px;
  background-color: #f1f3fd;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2080f0;
}
.text-primary {
  stroke: #2080f0;
}
.selected-item {
  background-color: #eef0fa;
}
</style>

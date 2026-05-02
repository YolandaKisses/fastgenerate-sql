<script setup lang="ts">
import { NList, NListItem, NTag, NSpace, NText, NEmpty } from 'naive-ui'
import { ServerOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'

const props = defineProps<{
  sources: Array<{ id: number, name: string, db_type: string, status: string, host: string, sync_status?: string }>,
  selectedSource?: any | null
}>()

const emit = defineEmits(['select'])

const getStatusType = (status: string) => {
  switch (status) {
    case 'connection_ok':
      return 'success'
    case 'draft': return 'default'
    case 'stale': return 'warning'
    case 'connection_failed':
    case 'sync_failed': return 'error'
    default: return 'default'
  }
}

const getSyncStatusType = (status?: string) => {
  switch (status) {
    case 'sync_success':
      return 'success'
    case 'sync_partial_success':
      return 'warning'
    case 'sync_failed':
      return 'error'
    case 'syncing':
      return 'info'
    default:
      return 'default'
  }
}
</script>

<template>
  <div v-if="sources.length === 0" class="empty-list-container">
    <n-empty :description="selectedSource ? '正在配置新连接' : '暂无数据源连接'" size="large">
      <template #icon>
        <n-icon>
          <ServerOutline />
        </n-icon>
      </template>
      <template #extra v-if="!selectedSource">
        <n-text depth="3" class="empty-tip">
          点击右上角“新建连接”开始配置
        </n-text>
      </template>
    </n-empty>
  </div>
  <n-list v-else hoverable clickable class="source-list">
    <n-list-item 
      v-for="source in sources" 
      :key="source.id" 
      :class="{'selected-item': selectedSource?.id === source.id}"
      @click="emit('select', source)"
    >
      <n-space align="start" :size="12">
        <div class="icon-box" :class="`type-${source.db_type.toLowerCase()}`">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
        </div>
        <div class="meta-content">
          <n-text strong class="source-name">{{ source.name }}</n-text>
          <div class="sub-meta">
            <n-text depth="3" class="source-host">{{ source.db_type }} • {{ source.host }}</n-text>
          </div>
          <div class="status-tags">
            <n-tag :type="getStatusType(source.status)" size="small" round :bordered="false" class="status-tag">
              {{ source.status }}
            </n-tag>
            <n-tag v-if="source.sync_status" :type="getSyncStatusType(source.sync_status)" size="small" round :bordered="false" class="status-tag">
              {{ source.sync_status }}
            </n-tag>
          </div>
        </div>
      </n-space>
    </n-list-item>
  </n-list>
</template>

<style scoped>
.empty-list-container {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.empty-tip {
  font-size: 13px;
}

.source-list {
  background: transparent;
}

.n-list-item {
  margin: 4px 0;
  border-radius: 8px !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  padding: 12px !important;
  border: 1px solid transparent !important;
}

.n-list-item:hover {
  background-color: #f8f9fe !important;
  border-color: #e0e4f8 !important;
}

.selected-item {
  background-color: #eef0fa !important;
  border-color: #2080f033 !important;
  box-shadow: 0 2px 8px rgba(32, 128, 240, 0.08);
}

.icon-box {
  width: 40px;
  height: 40px;
  background-color: #f1f3fd;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2080f0;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.selected-item .icon-box {
  background-color: #2080f0;
  color: white;
  transform: scale(1.05);
}

.type-mysql { color: #00758f; background-color: #f0f7f9; }
.type-postgresql { color: #336791; background-color: #f0f4f8; }
.type-oracle { color: #f80000; background-color: #fff1f0; }

.meta-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.source-name {
  font-size: 15px;
  transition: color 0.2s ease;
}

.selected-item .source-name {
  color: #2080f0;
}

.source-host {
  font-size: 12px;
}

.sub-meta {
  margin-bottom: 6px;
}

.status-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.status-tag {
  font-size: 10px;
  font-weight: 600;
  height: 18px;
  line-height: 18px;
  padding: 0 8px;
}
</style>

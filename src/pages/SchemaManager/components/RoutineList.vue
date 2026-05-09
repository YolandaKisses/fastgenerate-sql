<script setup lang="ts">
import { NCard, NList, NListItem, NTag, NSpace, NText, NEmpty, NScrollbar } from 'naive-ui'
import { NIcon } from 'naive-ui'
import { CodeSlashOutline } from '@vicons/ionicons5'

defineProps<{
  routines: Array<{
    id: number
    owner: string
    name: string
    routine_type: string
    definition_text: string
  }>
  selectedRoutine?: any | null
}>()

const emit = defineEmits(['select'])
</script>

<template>
  <n-card class="list-card" content-style="padding: 0; display: flex; flex-direction: column; height: 100%; border-radius: 12px;">
    <div v-if="routines.length === 0" class="empty-list-container">
      <n-empty description="暂无已同步的存储过程或函数" size="large">
        <template #icon>
          <n-icon>
            <CodeSlashOutline />
          </n-icon>
        </template>
      </n-empty>
    </div>
    <n-scrollbar v-else class="routine-scroll">
      <n-list hoverable clickable class="routine-list">
        <n-list-item
          v-for="routine in routines"
          :key="routine.id"
          :class="{ 'selected-item': selectedRoutine?.id === routine.id }"
          @click="emit('select', routine)"
        >
          <div class="routine-item">
            <div class="routine-header">
              <n-text strong class="routine-name">{{ routine.name }}</n-text>
              <n-tag size="small" round :bordered="false" type="info">
                {{ routine.routine_type }}
              </n-tag>
            </div>
            <n-space align="center" :size="8" class="routine-meta">
              <n-text depth="3" class="routine-owner">{{ routine.owner }}</n-text>
            </n-space>
          </div>
        </n-list-item>
      </n-list>
    </n-scrollbar>
  </n-card>
</template>

<style scoped>
.list-card {
  border-radius: 12px;
  border: 1px solid #efeff5;
  box-shadow: none;
  background: #ffffff;
  height: 100%;
}

.empty-list-container {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.routine-list {
  background: transparent;
  padding-right: 10px;
  box-sizing: border-box;
}

.routine-scroll {
  flex: 1;
  min-height: 0;
}

.n-list-item {
  margin: 4px 0;
  border-radius: 8px !important;
  transition: all 0.2s ease;
  padding: 14px !important;
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

.routine-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.routine-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.routine-name {
  font-size: 14px;
  line-height: 1.4;
}

.routine-owner {
  font-size: 12px;
}
</style>

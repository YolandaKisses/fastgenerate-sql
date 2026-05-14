<script setup lang="ts">
import { computed, ref } from 'vue'
import { NList, NListItem, NTag, NSpace, NText, NEmpty, NScrollbar, NInput } from 'naive-ui'
import { NIcon } from 'naive-ui'
import { CodeSlashOutline, SearchOutline } from '@vicons/ionicons5'

const props = defineProps<{
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
const keyword = ref('')

const filteredRoutines = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  if (!search) {
    return props.routines
  }

  return props.routines.filter((routine: (typeof props.routines)[number]) => {
    const haystack = [routine.name, routine.owner, routine.routine_type]
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
    <div v-if="filteredRoutines.length === 0" class="empty-list-container">
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
          v-for="routine in filteredRoutines"
          :key="routine.id"
          :class="{ 'selected-item': selectedRoutine?.id === routine.id }"
          @click="emit('select', routine)"
        >
          <div class="routine-item">
            <div class="routine-header">
              <div class="routine-name">{{ routine.name }}</div>
              <n-tag size="small" round :bordered="false" type="info">
                {{ routine.routine_type }}
              </n-tag>
            </div>
            <div class="routine-meta">
              <n-text depth="3" class="routine-owner">{{ routine.owner }}</n-text>
            </div>
          </div>
        </n-list-item>
      </n-list>
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

.empty-list-container {
  flex: 1;
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
  margin: 6px 0;
  border-radius: 8px !important;
  transition: all 0.2s ease;
  padding: 14px 16px !important;
  border: 1px solid transparent !important;
  position: relative;
  background-color: transparent !important;
}

.n-list-item:hover {
  background-color: #f8f9fe !important;
  border-color: #e0e4f8 !important;
}

.selected-item {
  background-color: #ffffff !important;
  border: 1px solid #2080f0 !important;
  box-shadow: 0 4px 12px rgba(32, 128, 240, 0.1);
  transform: translateY(-1px);
  z-index: 1;
}

/* 精细的左侧指示器 */
.selected-item::before {
  content: "";
  position: absolute;
  left: 2px;
  top: 12px;
  bottom: 12px;
  width: 3px;
  background-color: #2080f0;
  border-radius: 2px;
}

.selected-item .routine-item {
  padding-left: 6px;
}

.routine-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  transition: padding 0.2s ease;
}

.routine-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.routine-name {
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  color: #262626;
  line-height: 1.5;
  word-break: break-all;
  white-space: normal;
}

.routine-owner {
  font-size: 12px;
  color: #8c8c8c;
}
</style>

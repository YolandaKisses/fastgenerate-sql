<script setup lang="ts">
import { computed, ref } from 'vue'
import { NList, NListItem, NTag, NSpace, NText, NEmpty, NScrollbar, NInput } from 'naive-ui'
import { NIcon } from 'naive-ui'
import { BookOutline, SearchOutline } from '@vicons/ionicons5'

const props = defineProps<{
  views: Array<{
    id: number
    owner: string
    name: string
    definition_text: string
    original_comment?: string | null
  }>
  selectedView?: any | null
}>()

const emit = defineEmits(['select'])
const keyword = ref('')

const filteredViews = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  if (!search) {
    return props.views
  }

  return props.views.filter((view: (typeof props.views)[number]) => {
    const haystack = [view.name, view.owner, view.original_comment]
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
    <div v-if="filteredViews.length === 0" class="empty-list-container">
      <n-empty description="暂无已同步的视图" size="large">
        <template #icon>
          <n-icon>
            <BookOutline />
          </n-icon>
        </template>
      </n-empty>
    </div>
    <n-scrollbar v-else class="view-scroll">
      <n-list hoverable clickable class="view-list">
        <n-list-item
          v-for="view in filteredViews"
          :key="view.id"
          :class="{ 'selected-item': selectedView?.id === view.id }"
          @click="emit('select', view)"
        >
          <div class="view-item">
            <div class="view-header">
              <n-text strong class="view-name">{{ view.name }}</n-text>
              <n-tag size="small" round :bordered="false" type="success">
                VIEW
              </n-tag>
            </div>
            <n-space align="center" :size="8" class="view-meta">
              <n-text depth="3" class="view-owner">{{ view.owner }}</n-text>
            </n-space>
            <n-text depth="3" class="view-comment">
              {{ view.original_comment || "无视图备注" }}
            </n-text>
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

.view-list {
  background: transparent;
  padding-right: 10px;
  box-sizing: border-box;
}

.view-scroll {
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

.view-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.view-name {
  font-size: 14px;
  line-height: 1.4;
}

.view-owner,
.view-comment {
  font-size: 12px;
}

.view-comment {
  display: block;
  line-height: 1.4;
}
</style>

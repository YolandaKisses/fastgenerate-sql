<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NScrollbar, NText, NIcon } from "naive-ui";
import { AddOutline, SearchOutline, TrashOutline } from "@vicons/ionicons5";
import type { DemandDraftTable } from "../types";

const props = defineProps<{
  tables: DemandDraftTable[];
  selectedTableId: string | null;
}>();

const emit = defineEmits<{
  (e: "select", id: string): void;
  (e: "add"): void;
  (e: "remove", id: string): void;
}>();

const keyword = ref("");

const filteredTables = computed(() => {
  const search = keyword.value.trim().toLowerCase();
  if (!search) {
    return props.tables;
  }
  return props.tables.filter((table) => {
    return [table.name, table.savedPath]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(search);
  });
});
</script>

<template>
  <div class="list-card">
    <div class="list-header">
      <n-input
        v-model:value="keyword"
        placeholder="搜索需求表..."
        size="small"
        clearable
      >
        <template #prefix>
          <n-icon :component="SearchOutline" />
        </template>
      </n-input>
      <n-button type="primary" size="small" @click="emit('add')">
        <template #icon>
          <n-icon :component="AddOutline" />
        </template>
        新建表
      </n-button>
    </div>

    <n-scrollbar class="list-scroll">
      <div class="table-list">
        <div
          v-for="table in filteredTables"
          :key="table.id"
          class="table-item"
          :class="{ 'selected-item': selectedTableId === table.id }"
          @click="emit('select', table.id)"
        >
          <div class="table-item-content">
            <n-text strong class="table-name">{{
              table.name || "未命名表"
            }}</n-text>
            <n-text depth="3" class="table-meta">
              {{ table.fields.length }} 个字段
            </n-text>
            <n-text
              v-if="table.savedPath"
              depth="3"
              class="table-meta truncate"
            >
              {{ table.savedPath }}
            </n-text>
          </div>
          <button
            class="remove-button"
            type="button"
            title="删除当前草稿"
            @click.stop="emit('remove', table.id)"
          >
            <n-icon :component="TrashOutline" />
          </button>
        </div>
        <div v-if="filteredTables.length === 0" class="empty-state">
          暂无需求表草稿
        </div>
      </div>
    </n-scrollbar>
  </div>
</template>

<style scoped>
.list-card {
  border-radius: 12px;
  border: 1px solid #efeff5;
  background: #ffffff;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  padding: 12px;
  border-bottom: 1px solid #efeff5;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-scroll {
  flex: 1;
  min-height: 0;
}

.table-list {
  display: flex;
  flex-direction: column;
  padding: 10px;
  gap: 8px;
}

.table-item {
  padding: 14px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  transition: all 0.2s ease;
}

.table-item:hover {
  background: #f8f9fe;
  border-color: #e0e4f8;
}

.selected-item {
  background: #eef4ff;
  border-color: #bfd4ff;
}

.table-item-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.table-name {
  font-size: 13px;
  font-family: "JetBrains Mono", monospace;
}

.table-meta {
  font-size: 12px;
}

.truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.remove-button {
  width: 28px;
  height: 28px;
  border: 1px solid #efeff5;
  border-radius: 8px;
  background: #ffffff;
  color: #717785;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.remove-button:hover {
  color: #d03050;
  border-color: #f3c4cf;
  background: #fff7f8;
}

.empty-state {
  padding: 24px 16px;
  color: #717785;
  font-size: 13px;
  text-align: center;
}
</style>

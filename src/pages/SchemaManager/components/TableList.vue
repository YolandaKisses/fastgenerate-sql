<script setup lang="ts">
import { computed, ref } from "vue";
import { NList, NListItem, NTag, NScrollbar, NInput, NIcon } from "naive-ui";
import { SearchOutline } from "@vicons/ionicons5";

const props = defineProps<{
  tables: Array<any>;
  selectedTable: any | null;
}>();

const emit = defineEmits(["select"]);
const keyword = ref("");

const filteredTables = computed(() => {
  const search = keyword.value.trim().toLowerCase();
  if (!search) {
    return props.tables;
  }

  return props.tables.filter((table) => {
    const haystack = [
      table.name,
      table.original_comment,
      table.supplementary_comment,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(search);
  });
});
</script>

<template>
  <div class="list-card">
    <div class="search-box">
      <n-input
        v-model:value="keyword"
        placeholder="搜索对象名..."
        size="small"
        clearable
      >
        <template #prefix>
          <n-icon :component="SearchOutline" />
        </template>
      </n-input>
    </div>

    <n-scrollbar class="table-scroll">
      <n-list hoverable clickable class="table-list">
        <n-list-item
          v-for="table in filteredTables"
          :key="table.id"
          :class="{ 'selected-item': selectedTable?.id === table.id }"
          @click="emit('select', table)"
        >
          <div class="table-item-content">
            <div class="table-header">
              <div class="table-name">{{ table.name }}</div>
              <n-tag size="small" round :bordered="false" type="warning">
                TABLE
              </n-tag>
            </div>
            <div class="table-comment">
              {{ table.original_comment || "无表级注释" }}
            </div>
          </div>
        </n-list-item>
        <div v-if="filteredTables.length === 0" class="empty-state">
          没有匹配的表
        </div>
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

.table-scroll {
  flex: 1;
  min-height: 0;
}

.table-list {
  background: transparent;
  padding-right: 12px;
  box-sizing: border-box;
}

.n-list-item {
  margin: 6px 0;
  padding: 14px 16px !important;
  cursor: pointer;
  border-radius: 8px !important;
  border: 1px solid transparent !important;
  transition: all 0.2s ease;
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

.selected-item .table-item-content {
  padding-left: 6px;
}

.table-item-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  transition: padding 0.2s ease;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.table-name {
  font-size: 13px;
  font-family: "JetBrains Mono", monospace;
  font-weight: 600;
  color: #262626;
  line-height: 1.5;
  word-break: break-all;
  white-space: normal;
}

.table-comment {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.4;
  word-break: break-all;
  white-space: normal;
}

.empty-state {
  padding: 24px 16px;
  color: #717785;
  font-size: 13px;
  text-align: center;
}
</style>

<script setup lang="ts">
import { computed } from "vue";
import { NButton, NInput, NIcon, NSelect, NTabs, NTabPane } from "naive-ui";
import { AddOutline, SaveOutline, TrashOutline, CreateOutline, FolderOutline, GridOutline } from "@vicons/ionicons5";
import type { DemandDraftTable, SchemaTableOption, DemandField } from "../types";

const props = defineProps<{
  table: DemandDraftTable | null;
  demandName: string;
  schemaTables: SchemaTableOption[];
  saving: boolean;
}>();

const emit = defineEmits<{
  (e: "update-table-name", value: string): void;
  (e: "update-table-comment", value: string): void;
  (e: "update-related-tables", value: string[]): void;
  (e: "update-related-table-detail", key: string, value: string): void;
  (e: "update-field", fieldId: string, key: keyof DemandField, value: string): void;
  (e: "add-field"): void;
  (e: "remove-field", fieldId: string): void;
  (e: "save"): void;
}>();

const canSave = computed(() => {
  if (!props.table) return false;
  return Boolean(props.demandName.trim() && props.table.name.trim() && props.table.fields.length);
});

const relatedTableOptions = computed(() => {
  return props.schemaTables
    .filter((item) => item.name.trim())
    .map((item) => ({
      label: `${item.name}${item.original_comment ? ` (${item.original_comment})` : ""}`,
      value: item.name,
    }));
});
</script>

<template>
  <div v-if="table" class="editor-card">
    <!-- 1. 紧凑型 Header：集成表名、备注、分类、操作 -->
    <div class="editor-header">
      <div class="header-left">
        <div class="title-group">
          <n-input
            :value="table.name"
            placeholder="请输入表名..."
            class="table-name-input"
            @update:value="emit('update-table-name', $event)"
          />
          <div v-if="table.savedPath" class="status-pill success">
            <span class="dot"></span> 已同步 Wiki
          </div>
        </div>
        <div class="comment-group">
          <n-input
            :value="table.comment"
            placeholder="添加业务逻辑或口径描述..."
            class="table-comment-input"
            @update:value="emit('update-table-comment', $event)"
          />
        </div>
      </div>

      <div class="header-right">
        <div class="meta-card">
          <div class="meta-item">
            <span class="meta-label">归属分类</span>
            <div class="meta-value">
              <n-icon :component="FolderOutline" />
              <span class="text">{{ demandName || "未分类" }}</span>
            </div>
          </div>
          <div class="divider"></div>
          <n-button
            type="primary"
            :loading="saving"
            :disabled="!canSave"
            class="save-btn"
            @click="emit('save')"
          >
            <template #icon>
              <n-icon :component="SaveOutline" />
            </template>
            保存同步
          </n-button>
        </div>
      </div>
    </div>

    <!-- 2. 编辑区：通过 flex: 1 自动撑满剩余高度 -->
    <div class="editor-content">
      <n-tabs
        type="line"
        class="full-height-tabs"
        pane-style="flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 0;"
      >
        <n-tab-pane name="schema" tab="表结构定义">
          <div class="fields-container">
            <div class="toolbar">
              <div class="toolbar-text">
                共 {{ table.fields.length }} 个字段 · 支持直接编辑
              </div>
              <n-button size="small" type="primary" secondary @click="emit('add-field')">
                <template #icon>
                  <n-icon :component="AddOutline" />
                </template>
                新增字段
              </n-button>
            </div>

            <div class="table-v-scroll">
              <table class="fields-table">
                <thead>
                  <tr>
                    <th style="width: 22%">字段名</th>
                    <th style="width: 15%">数据类型</th>
                    <th style="width: 25%">原始定义/备注</th>
                    <th style="width: 30%">业务规则/补充备注</th>
                    <th class="action-col">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="field in table.fields" :key="field.id">
                    <td>
                      <n-input
                        :value="field.name"
                        size="small"
                        placeholder="字段英文名"
                        @update:value="emit('update-field', field.id, 'name', $event)"
                      />
                    </td>
                    <td>
                      <n-input
                        :value="field.type"
                        size="small"
                        placeholder="varchar(64)"
                        @update:value="emit('update-field', field.id, 'type', $event)"
                      />
                    </td>
                    <td>
                      <n-input
                        :value="field.original_comment"
                        size="small"
                        placeholder="来源定义"
                        @update:value="emit('update-field', field.id, 'original_comment', $event)"
                      />
                    </td>
                    <td>
                      <n-input
                        :value="field.supplementary_comment"
                        size="small"
                        placeholder="详细业务逻辑说明"
                        @update:value="emit('update-field', field.id, 'supplementary_comment', $event)"
                      />
                    </td>
                    <td class="action-cell">
                      <button
                        class="icon-btn-danger"
                        type="button"
                        @click="emit('remove-field', field.id)"
                      >
                        <n-icon :component="TrashOutline" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="relations" tab="关联关系设置">
          <div class="relation-container">
            <div class="relation-header">
              <div class="header-text">
                <span class="main">业务关联表 (Sibling Tables)</span>
                <span class="desc">关联信息将有助于提高 AI 生成 Wiki 的准确度。</span>
              </div>
            </div>
            
            <div class="relation-content">
              <div class="config-section">
                <n-select
                  :value="table.relatedTables"
                  multiple
                  filterable
                  placeholder="搜索并关联其他业务表..."
                  :options="relatedTableOptions"
                  :max-tag-count="8"
                  @update:value="emit('update-related-tables', $event)"
                />
              </div>

              <div v-if="table.relatedTables.length > 0" class="relation-grid">
                <div v-for="key in table.relatedTables" :key="key" class="relation-card">
                  <div class="card-head">
                    <span class="table-tag">{{ key }}</span>
                    <span class="table-comment">
                      {{ schemaTables.find((i) => i.name === key)?.original_comment || "暂无备注" }}
                    </span>
                  </div>
                  <n-input
                    :value="table.relatedTableDetails[key] || ''"
                    type="textarea"
                    placeholder="请输入表间关联逻辑（如关联字段等）..."
                    size="small"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    @update:value="emit('update-related-table-detail', key, $event)"
                  />
                </div>
              </div>
              <div v-else class="relation-empty">
                尚未关联任何表，点击上方选择框开始关联。
              </div>
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>

  <div v-else class="empty-view">
    <div class="empty-placeholder">
      <div class="icon">📑</div>
      <div class="text">请在左侧选择或新建一个需求表草稿</div>
    </div>
  </div>
</template>

<style scoped>
.editor-card {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #efeff5;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

/* Header 深度美化 */
.editor-header {
  padding: 16px 24px;
  border-bottom: 1px solid #f0f2f5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  position: relative;
}

.header-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0; /* 防止内容撑破父容器 */
  max-width: calc(100% - 320px); /* 给右侧预留出足够的空间 */
}

.title-group,
.comment-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-name-input {
  max-width: 420px;
}

:deep(.table-name-input .n-input__input-el) {
  font-size: 16px;
  font-weight: 600;
  color: #1f2225;
}

.table-comment-input {
  flex: 1;
  max-width: 800px;
}

:deep(.table-comment-input .n-input__input-el) {
  font-size: 13px;
  color: #717785;
}

.status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.status-pill.success {
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.status-pill .dot {
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
}

.header-right {
  display: flex;
  align-items: center;
  flex-shrink: 0; /* 禁止压缩 */
  margin-left: 24px;
}

.meta-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #f8f9fb;
  padding: 4px 4px 4px 16px;
  border-radius: 10px;
  border: 1px solid #f0f2f5;
  min-width: 300px; /* 强制设置最小宽度，保证右侧不缩水 */
}

.meta-item {
  display: flex;
  flex-direction: column;
  flex: 1; /* 占据剩余空间 */
  min-width: 0;
}

.meta-label {
  font-size: 10px;
  color: #8c92a0;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
}

.meta-value {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #414753;
  white-space: nowrap;
}

.meta-value .text {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.divider {
  width: 1px;
  height: 24px;
  background: #e1e4e8;
}

.save-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(24, 144, 255, 0.2);
}

/* 内容区域 */
.editor-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.full-height-tabs {
  height: 100%;
}

:deep(.n-tabs-nav) {
  padding: 0 24px;
}

:deep(.n-tabs-pane-wrapper) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* 表结构面板 */
.fields-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fcfdfe;
}

.toolbar {
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
}

.toolbar-text {
  font-size: 13px;
  color: #8c92a0;
}

.table-v-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 24px 24px;
}

.fields-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
}

.fields-table th {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #fff;
  padding: 14px 12px;
  text-align: left;
  font-size: 12px;
  color: #717785;
  font-weight: 600;
  border-bottom: 2px solid #f0f2f5;
}

.fields-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f2f5;
  vertical-align: middle;
}

.fields-table tr:hover td {
  background: #f8f9fc;
}

.action-cell {
  width: 60px;
  text-align: center;
}

.icon-btn-danger {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid #efeff5;
  background: #fff;
  color: #8c92a0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.icon-btn-danger:hover {
  background: #fff5f5;
  color: #d03050;
  border-color: #f3c4cf;
}

/* 关联关系面板统一风格 */
.relation-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fcfdfe;
  border: 1px solid #efeff5;
  border-radius: 8px;
  overflow: hidden;
}

.relation-header {
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
}

.relation-header .main {
  font-size: 13px;
  font-weight: 600;
  color: #1f2225;
  margin-right: 12px;
}

.relation-header .desc {
  font-size: 12px;
  color: #8c92a0;
}

.relation-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-section {
  width: 100%;
}

.relation-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.relation-card {
  padding: 16px;
  background: #fbfcfd;
  border: 1px solid #efeff5;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: border-color 0.2s;
}

.relation-card:hover {
  border-color: #d0d7de;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-tag {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 700;
  font-size: 14px;
  color: #1f2225;
  padding: 2px 6px;
  background: #f0f2f5;
  border-radius: 4px;
}

.table-comment {
  font-size: 12px;
  color: #8c92a0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.relation-empty {
  padding: 40px;
  text-align: center;
  color: #8c92a0;
  background: #fbfcfd;
  border: 1px dashed #efeff5;
  border-radius: 12px;
}

/* 空视图 */
.empty-view {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f9fafb;
}

.empty-placeholder {
  text-align: center;
}

.empty-placeholder .icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-placeholder .text {
  color: #8c92a0;
  font-size: 15px;
}
</style>

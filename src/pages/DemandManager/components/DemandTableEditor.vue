<script setup lang="ts">
import { computed } from "vue";
import { NButton, NInput, NIcon, NSelect, NTabs, NTabPane } from "naive-ui";
import { AddOutline, SaveOutline, TrashOutline } from "@vicons/ionicons5";
import type { DemandDraftTable, SchemaTableOption } from "../types";

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
    <div class="editor-header">
      <div class="header-main">
        <div class="header-title">需求表定义</div>
        <div class="header-subtitle">
          当前需求分类：{{ demandName || "未填写" }}
        </div>
      </div>
      <n-button type="primary" :loading="saving" :disabled="!canSave" @click="emit('save')">
        <template #icon>
          <n-icon :component="SaveOutline" />
        </template>
        保存并生成 Wiki
      </n-button>
    </div>

    <div class="table-meta-panel">
      <div class="table-meta-grid">
        <div class="table-meta-item">
          <label class="section-label">表名</label>
          <n-input
            :value="table.name"
            placeholder="请输入本次需求要创建的表名"
            @update:value="emit('update-table-name', $event)"
          />
        </div>
        <div class="table-meta-item">
          <label class="section-label">表备注</label>
          <n-input
            :value="table.comment"
            placeholder="请输入表级备注说明"
            @update:value="emit('update-table-comment', $event)"
          />
        </div>
      </div>
      <div v-if="table.savedPath" class="saved-hint">已生成：{{ table.savedPath }}</div>
    </div>

    <div class="editor-content">
      <n-tabs
        type="line"
        class="full-height-tabs"
        pane-style="flex: 1; display: flex; flex-direction: column; min-height: 0; gap: 20px;"
      >
        <n-tab-pane name="schema" tab="表结构">
          <div class="fields-panel">
            <div class="panel-header">
              <div>
                <div class="section-title">表结构</div>
                <div class="section-desc">字段名、类型、原始备注、本地补充备注都支持直接编辑</div>
              </div>
              <n-button secondary @click="emit('add-field')">
                <template #icon>
                  <n-icon :component="AddOutline" />
                </template>
                新增字段
              </n-button>
            </div>

            <div class="fields-table-header">
              <table class="fields-table fields-table-static">
                <thead>
                  <tr>
                    <th>字段名</th>
                    <th>类型</th>
                    <th>原始备注</th>
                    <th>本地补充备注</th>
                    <th class="action-col">操作</th>
                  </tr>
                </thead>
              </table>
            </div>
            <div class="fields-table-wrap">
              <table class="fields-table">
                <tbody>
                  <tr v-for="field in table.fields" :key="field.id">
                    <td>
                      <n-input
                        :value="field.name"
                        placeholder="如 report_date"
                        @update:value="emit('update-field', field.id, 'name', $event)"
                      />
                    </td>
                    <td>
                      <n-input
                        :value="field.type"
                        placeholder="如 varchar(64)"
                        @update:value="emit('update-field', field.id, 'type', $event)"
                      />
                    </td>
                    <td>
                      <n-input
                        :value="field.original_comment"
                        placeholder="来源定义或原始备注"
                        @update:value="emit('update-field', field.id, 'original_comment', $event)"
                      />
                    </td>
                    <td>
                      <n-input
                        :value="field.supplementary_comment"
                        placeholder="补充业务口径、规则说明"
                        @update:value="emit('update-field', field.id, 'supplementary_comment', $event)"
                      />
                    </td>
                    <td class="action-cell">
                      <button
                        class="remove-button"
                        type="button"
                        title="删除字段"
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

        <n-tab-pane name="relations" tab="关联表设置">
          <div class="relation-panel">
            <div class="relation-header">
              <div>
                <label class="section-label">关联表 (Sibling Tables)</label>
                <div class="section-tip">关联表信息将帮助后续文档更准确地表达表间关系。</div>
              </div>
            </div>
            <n-select
              :value="table.relatedTables"
              multiple
              filterable
              placeholder="选择业务相关的关联表..."
              :options="relatedTableOptions"
              :max-tag-count="4"
              @update:value="emit('update-related-tables', $event)"
            />

            <div v-if="table.relatedTables.length > 0" class="relation-preview">
              <div class="preview-title">已选关联表详情</div>
              <div class="preview-scroll-area">
                <div class="preview-list">
                  <div
                    v-for="key in table.relatedTables"
                    :key="key"
                    class="preview-item"
                  >
                    <div class="item-info">
                      <span class="item-name">{{ key }}</span>
                      <span class="item-comment">
                        {{ schemaTables.find((item) => item.name === key)?.original_comment || "无备注" }}
                      </span>
                    </div>
                    <div class="item-input">
                      <n-input
                        :value="table.relatedTableDetails[key] || ''"
                        type="textarea"
                        placeholder="例如：t1.user_id = t2.id"
                        size="small"
                        :autosize="{ minRows: 2, maxRows: 3 }"
                        @update:value="emit('update-related-table-detail', key, $event)"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>

  <div v-else class="empty-editor">
    请先在左侧新建一个表草稿
  </div>
</template>

<style scoped>
.editor-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  background: #fff;
  border: 1px solid #efeff5;
  border-radius: 12px;
  overflow: hidden;
}

.table-meta-panel,
.fields-panel,
.relation-panel {
  border-radius: 8px;
  background: #ffffff;
}

.editor-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 24px;
  gap: 20px;
  overflow: hidden;
}

.editor-header {
  padding: 16px 20px;
  border-bottom: 1px solid #efeff5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #fbfcfd;
}

.header-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2225;
}

.header-subtitle,
.section-desc,
.saved-hint {
  font-size: 13px;
  color: #717785;
}

.table-meta-panel {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid #efeff5;
}

.table-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.table-meta-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label,
.section-title {
  font-weight: 600;
  color: #414753;
}

.fields-panel {
  flex: 1;
  min-height: 0;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border: 1px solid #efeff5;
  overflow: hidden;
}

.relation-panel {
  flex: 1;
  min-height: 0;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #fbfcfd;
  border: 1px solid #efeff5;
  overflow: hidden;
}

.full-height-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

:deep(.full-height-tabs .n-tabs-pane-wrapper) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

:deep(.full-height-tabs .n-tab-pane) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

:deep(.n-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-nav) {
  padding: 0 4px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.relation-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 0;
}

.fields-table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.fields-table-header {
  flex: 0 0 auto;
  overflow: hidden;
  border-bottom: 1px solid #efeff5;
}

.fields-table {
  width: 100%;
  min-width: 960px;
  border-collapse: collapse;
  table-layout: fixed;
}

.fields-table th,
.fields-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #f0f2f5;
  text-align: left;
  vertical-align: top;
}

.fields-table th {
  font-size: 13px;
  color: #717785;
  font-weight: 600;
  background: #fbfcff;
}

.action-col,
.action-cell {
  width: 72px;
}

.remove-button {
  width: 32px;
  height: 32px;
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

.relation-preview {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin-top: 8px;
  padding-top: 20px;
  border-top: 1px dashed #efeff5;
}

.preview-title {
  flex: 0 0 auto;
  font-size: 14px;
  font-weight: 600;
  color: #1f2225;
  margin-bottom: 12px;
}

.preview-scroll-area {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-right: 6px;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #efeff5;
  border-radius: 6px;
  background: #fff;
}

.item-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.item-name {
  font-family: "JetBrains Mono", monospace;
  font-weight: 600;
  color: #1f2225;
}

.item-comment {
  font-size: 13px;
  color: #717785;
}

.item-input {
  width: 100%;
}

.section-tip {
  font-size: 12px;
  color: #717785;
  margin-top: 4px;
}

.empty-editor {
  height: 100%;
  border-radius: 14px;
  border: 1px dashed #d6d9e0;
  background: #ffffff;
  color: #717785;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 960px) {
  .editor-header,
  .panel-header {
    flex-direction: column;
    align-items: stretch;
  }

  .table-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>

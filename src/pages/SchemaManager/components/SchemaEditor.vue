<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NInput,
  NSelect,
  NIcon,
  NTabs,
  NTabPane,
  useMessage,
} from "naive-ui";
import { SyncOutline, BookOutline, SparklesOutline } from "@vicons/ionicons5";
import { get, patch } from "../../../services/request";

const props = defineProps({
  table: { type: Object, default: null },
  allTables: { type: Array, default: () => [] },
  knowledgeTask: { type: Object, default: null },
  knowledgeSyncing: { type: Boolean, default: false },
  schemaSyncing: { type: Boolean, default: false },
});

const emit = defineEmits(["sync", "sync-knowledge", "sync-table"]);
const message = useMessage();
const isKnowledgeSyncActive = computed(() => Boolean(props.knowledgeSyncing));
const isDatasourceKnowledgeSyncActive = computed(() => {
  if (!isKnowledgeSyncActive.value) return false;
  return props.knowledgeTask?.scope !== "table";
});

const fields = ref<any[]>([]);
const tableRemark = ref("");
const relatedTables = ref<string[]>([]);
const relatedTableDetails = ref<Record<string, string>>({});
const isRelatedChanged = ref(false);

const dirtyFields = ref(new Set<number>());
const isTableRemarkChanged = ref(false);
const isRemarkSaveDisabled = computed(() => !isTableRemarkChanged.value && dirtyFields.value.size === 0);

const tableOptions = computed(() => {
  if (!props.allTables) return [];
  return props.allTables
    .filter((t: any) => t.id !== props.table?.id)
    .map((t: any) => ({
      label: `${t.name} ${t.original_comment ? `(${t.original_comment})` : ""}`,
      value: t.name,
    }));
});

const fetchFields = async (tableId: number) => {
  try {
    fields.value = await get(`/schema/fields/${tableId}`);
  } catch (error) {
    message.error("无法加载字段信息");
  }
};

watch(
  () => props.table,
  (newTable) => {
    if (newTable && newTable.id) {
      tableRemark.value = newTable.supplementary_comment || "";

      let details: Record<string, string> = {};
      let keys: string[] = [];
      if (newTable.related_tables) {
        try {
          const parsed = JSON.parse(newTable.related_tables);
          if (typeof parsed === "object" && !Array.isArray(parsed)) {
            details = parsed;
            keys = Object.keys(parsed);
          } else {
            keys = newTable.related_tables.split(",").filter(Boolean);
          }
        } catch {
          keys = newTable.related_tables.split(",").filter(Boolean);
        }
      }
      relatedTables.value = keys;
      relatedTableDetails.value = details;

      isRelatedChanged.value = false;
      fetchFields(newTable.id);
    } else {
      tableRemark.value = "";
      relatedTables.value = [];
      isRelatedChanged.value = false;
      fields.value = [];
    }
    isTableRemarkChanged.value = false;
    dirtyFields.value.clear();
  },
  { immediate: true },
);


const handleTableRemarkChange = () => {
  isTableRemarkChanged.value = true;
};

const handleRemarkChange = (fieldId: number) => {
  dirtyFields.value.add(fieldId);
};

const saveRemarks = async () => {
  if (!props.table) return;
  
  const promises = [];
  
  if (isTableRemarkChanged.value) {
    promises.push(patch(`/schema/tables/${props.table.id}/remark`, { remark: tableRemark.value }));
  }
  
  for (const fieldId of dirtyFields.value) {
    const field = fields.value.find(f => f.id === fieldId);
    if (field) {
      promises.push(patch(`/schema/fields/${fieldId}/remark`, { remark: field.supplementary_comment || "" }));
    }
  }
  
  try {
    await Promise.all(promises);
    isTableRemarkChanged.value = false;
    dirtyFields.value.clear();
    message.success("备注信息保存成功");
  } catch {
    message.error("保存备注信息失败");
  }
};

const handleRelatedTablesChange = (value: string[]) => {
  relatedTables.value = value;
  isRelatedChanged.value = true;
};

const saveRelatedTables = async () => {
  if (!props.table) return;
  try {
    const payload: Record<string, string> = {};
    relatedTables.value.forEach((key) => {
      payload[key] = relatedTableDetails.value[key] || "";
    });

    await patch(`/schema/tables/${props.table.id}/related-tables`, {
      related_tables: JSON.stringify(payload),
    });
    isRelatedChanged.value = false;
    message.success("关联关系保存成功");
  } catch {
    message.error("保存关联表失败");
  }
};

const handleDetailChange = (key: string, val: string) => {
  relatedTableDetails.value[key] = val;
  isRelatedChanged.value = true;
};
</script>

<template>
  <div v-if="table" class="editor-container">
    <div class="editor-header">
      <div class="header-main">
        <span class="table-name">{{ table.name }}</span>
        <span class="table-comment">{{ table.original_comment }}</span>
      </div>
      <div class="header-actions">
        <n-button
          secondary
          size="small"
          :loading="
            isKnowledgeSyncActive &&
            knowledgeTask?.scope === 'table' &&
            knowledgeTask?.mode === 'basic'
          "
          :disabled="isKnowledgeSyncActive || schemaSyncing"
          @click="emit('sync-table', 'basic')"
        >
          <template #icon>
            <n-icon><BookOutline /></n-icon>
          </template>
          单表知识库同步
        </n-button>
        <n-button
          tertiary
          size="small"
          :loading="
            isKnowledgeSyncActive &&
            knowledgeTask?.scope === 'table' &&
            knowledgeTask?.mode === 'ai_enhanced'
          "
          :disabled="isKnowledgeSyncActive || schemaSyncing"
          @click="emit('sync-table', 'ai_enhanced')"
        >
          <template #icon>
            <n-icon><SparklesOutline /></n-icon>
          </template>
          AI 单表深度解析
        </n-button>
      </div>
    </div>

    <div class="editor-content">
      <n-tabs
        type="line"
        animated
        class="full-height-tabs"
        pane-style="flex: 1; display: flex; flex-direction: column; min-height: 0; gap: 20px;"
      >
        <n-tab-pane name="remarks" tab="备注管理">
          <div class="panel section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
              <label class="section-label" style="margin-bottom: 0;">表级补充备注</label>
              <n-button
                :type="!isRemarkSaveDisabled ? 'primary' : 'default'"
                size="small"
                :disabled="isRemarkSaveDisabled"
                @click="saveRemarks"
              >
                保存备注设置
              </n-button>
            </div>
            <n-input
              v-model:value="tableRemark"
              type="textarea"
              placeholder="补充业务背景、关键口径或表的用途说明..."
              :autosize="{ minRows: 3, maxRows: 3 }"
              @update:value="handleTableRemarkChange"
            />
          </div>

          <div class="panel table-section">
            <div class="section-label" style="padding: 12px 16px">
              字段级补充备注
            </div>
            <div class="table-scroll-area">
              <table class="native-table">
                <thead>
                  <tr>
                    <th style="width: 15%">字段名</th>
                    <th style="width: 25%">类型</th>
                    <th style="width: 25%">原始备注</th>
                    <th style="width: 35%">本地补充备注</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="field in fields" :key="field.id">
                    <td class="code-font" :title="field.name">
                      {{ field.name }}
                    </td>
                    <td class="code-font type-text" :title="field.type">
                      {{ field.type }}
                    </td>
                    <td class="comment-text" :title="field.original_comment">
                      {{ field.original_comment }}
                    </td>
                    <td>
                      <n-input
                        v-model:value="field.supplementary_comment"
                        type="textarea"
                        placeholder="添加说明..."
                        size="small"
                        :autosize="{ minRows: 1, maxRows: 3 }"
                        @update:value="
                          () => handleRemarkChange(field.id)
                        "
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="relations" tab="关联表设置">
          <div class="panel section relation-panel">
            <div
              class="relation-header"
              style="
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
              "
            >
              <div>
                <label class="section-label">关联表 (Sibling Tables)</label>
                <div class="section-tip">
                  关联表信息将帮助 AI 在多表关联查询时更准确地理解表间关系。
                </div>
              </div>
              <n-button
                :type="isRelatedChanged ? 'primary' : 'default'"
                size="small"
                :disabled="!isRelatedChanged"
                @click="saveRelatedTables"
              >
                保存关联设置
              </n-button>
            </div>
            <n-select
              v-model:value="relatedTables"
              multiple
              filterable
              placeholder="选择业务相关的关联表..."
              :options="tableOptions"
              :max-tag-count="4"
              @update:value="handleRelatedTablesChange"
            />

            <div class="relation-preview" v-if="relatedTables.length > 0">
              <div class="preview-title">已选关联表详情</div>
              <div class="preview-list">
                <div
                  v-for="key in relatedTables"
                  :key="key"
                  class="preview-item"
                >
                  <div class="item-info">
                    <span class="item-name">{{
                      allTables.find((t) => t.name === key)?.name || key
                    }}</span>
                    <span class="item-comment">{{
                      allTables.find((t) => t.name === key)?.original_comment ||
                      "无备注"
                    }}</span>
                  </div>
                  <div class="item-input">
                    <n-input
                      :value="relatedTableDetails[key] || ''"
                      type="textarea"
                      @update:value="(val) => handleDetailChange(key, val)"
                      placeholder="例如：t1.user_id = t2.id"
                      size="small"
                      :autosize="{ minRows: 2, maxRows: 3 }"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>

  <div v-else class="empty-container">
    <div class="empty-content">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="48"
        height="48"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#d9dce8"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path
          d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
        ></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
      </svg>
      <p>请在左侧选择要管理的表</p>
      <n-button
        type="primary"
        size="large"
        style="margin-top: 16px"
        :loading="schemaSyncing"
        :disabled="schemaSyncing"
        @click="emit('sync')"
      >
        <template #icon>
          <n-icon><SyncOutline /></n-icon>
        </template>
        同步数据源
      </n-button>
    </div>
  </div>
</template>

<style scoped>
.editor-container,
.empty-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border: 1px solid #efeff5;
  border-radius: 12px;
  overflow: hidden;
}

.empty-container {
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
  color: #717785;
}

.editor-header {
  padding: 16px 20px;
  border-bottom: 1px solid #efeff5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fbfcfd;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.header-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-name {
  font-size: 18px;
  font-weight: 600;
  font-family: "JetBrains Mono", monospace;
  color: #181c22;
}

.table-comment {
  font-size: 14px;
  color: #717785;
}

.editor-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px;
  gap: 20px;
  min-height: 0;
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
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #414753;
  display: block;
  margin-bottom: 10px;
}

.panel {
  display: flex;
  flex-direction: column;
}

.table-section {
  flex: 1;
  min-height: 0;
  border: 1px solid #efeff5;
  border-radius: 8px;
  overflow: hidden;
}

.table-scroll-area {
  flex: 1;
  overflow: auto;
}

.native-table {
  width: 100%;
  min-width: 800px; /* trigger horizontal scroll on narrow screens */
  border-collapse: collapse;
  font-size: 13px;
  table-layout: fixed; /* Fix layout jumping */
}

.native-table th {
  background: #f7f7fa;
  text-align: left;
  padding: 12px;
  font-weight: 600;
  color: #414753;
  border-bottom: 1px solid #efeff5;
  position: sticky;
  top: 0;
  z-index: 10; /* Ensure header stays above content */
}

.native-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #efeff5;
  vertical-align: middle;
  word-break: break-word;
}

.code-font {
  font-family: "JetBrains Mono", monospace;
  word-break: break-all;
}

.type-text {
  color: #8250df;
  font-size: 12px;
}

.comment-text {
  color: #717785;
}

:deep(.n-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-nav) {
  padding: 0 4px;
}

.relation-panel {
  padding: 20px;
  background: #fbfcfd;
  border-radius: 8px;
  border: 1px solid #efeff5;
}

.relation-header {
  margin-bottom: 16px;
}

.section-tip {
  font-size: 12px;
  color: #717785;
  margin-top: 4px;
}

.relation-preview {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px dashed #efeff5;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: #181c22;
  margin-bottom: 12px;
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
  background: #fff;
  border: 1px solid #efeff5;
  border-radius: 6px;
}

.item-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.item-input {
  width: 100%;
}

.item-name {
  font-family: "JetBrains Mono", monospace;
  font-weight: 600;
  color: #181c22;
}

.item-comment {
  font-size: 13px;
  color: #717785;
}
</style>

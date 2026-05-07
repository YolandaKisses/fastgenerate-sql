<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton, NInput, NIcon, useMessage } from "naive-ui";
import { SyncOutline, BookOutline, SparklesOutline } from "@vicons/ionicons5";
import { get, patch } from "../../../services/request";

const props = defineProps<{
  table: any | null;
  knowledgeTask?: any | null;
  knowledgeSyncing?: boolean;
  schemaSyncing?: boolean;
}>();

const emit = defineEmits(["sync", "sync-knowledge", "sync-table"]);
const message = useMessage();
const isKnowledgeSyncActive = computed(() => Boolean(props.knowledgeSyncing));
const isDatasourceKnowledgeSyncActive = computed(() => {
  if (!isKnowledgeSyncActive.value) return false;
  return props.knowledgeTask?.scope !== "table";
});

const fields = ref<any[]>([]);
const tableRemark = ref("");

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
      fetchFields(newTable.id);
    } else {
      tableRemark.value = "";
      fields.value = [];
    }
  },
  { immediate: true },
);

let saveTimeout: any = null;
const handleTableRemarkChange = (tableId: number, remark: string) => {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(async () => {
    try {
      await patch(`/schema/tables/${tableId}/remark`, { remark });
    } catch {
      message.error("保存表级备注网络异常");
    }
  }, 500);
};

const handleRemarkChange = (fieldId: number, remark: string) => {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(async () => {
    try {
      await patch(`/schema/fields/${fieldId}/remark`, { remark });
    } catch {
      message.error("保存备注网络异常");
    }
  }, 500);
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
          :loading="schemaSyncing"
          :disabled="isKnowledgeSyncActive || schemaSyncing"
          @click="emit('sync')"
        >
          <template #icon>
            <n-icon><SyncOutline /></n-icon>
          </template>
          全量数据源同步
        </n-button>
        <n-button
          type="primary"
          size="small"
          :loading="isDatasourceKnowledgeSyncActive"
          :disabled="isKnowledgeSyncActive || schemaSyncing"
          @click="emit('sync-knowledge')"
        >
          <template #icon>
            <n-icon><BookOutline /></n-icon>
          </template>
          {{ isDatasourceKnowledgeSyncActive ? "同步中..." : "全量知识库同步" }}
        </n-button>
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
      <div class="panel section">
        <label class="section-label">表级补充备注</label>
        <n-input
          v-model:value="tableRemark"
          type="textarea"
          placeholder="补充业务背景、关键口径或表的用途说明..."
          :autosize="{ minRows: 3, maxRows: 6 }"
          @update:value="handleTableRemarkChange(table.id, tableRemark)"
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
                <td class="code-font" :title="field.name">{{ field.name }}</td>
                <td class="code-font type-text" :title="field.type">
                  {{ field.type }}
                </td>
                <td class="comment-text" :title="field.original_comment">
                  {{ field.original_comment }}
                </td>
                <td>
                  <n-input
                    v-model:value="field.supplementary_comment"
                    placeholder="添加说明..."
                    size="small"
                    @update:value="(val) => handleRemarkChange(field.id, val)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
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

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #414753;
  margin-bottom: 8px;
  display: block;
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
  border-collapse: collapse;
  font-size: 13px;
}

.native-table {
  width: 100%;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.code-font {
  font-family: "JetBrains Mono", monospace;
  overflow: hidden;
  text-overflow: ellipsis;
}

.type-text {
  color: #8250df;
  font-size: 12px;
}

.comment-text {
  color: #717785;
}
</style>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  NButton,
  NCard,
  NInput,
  NModal,
  NSelect,
  NTreeSelect,
  NIcon,
  useDialog,
  useMessage,
} from "naive-ui";
import { AddOutline, CreateOutline, TrashOutline } from "@vicons/ionicons5";
import { post, get, request } from "../../services/request";
import DemandTableList from "./components/DemandTableList.vue";
import DemandTableEditor from "./components/DemandTableEditor.vue";
import type {
  DemandCategoryNode,
  DemandCategoryTreeResponse,
  DemandDraftTable,
  DemandField,
  SchemaTableOption,
} from "./types";

const message = useMessage();
const dialog = useDialog();
const currentSource = ref<number | null>(null);
const sourceOptions = ref<{ label: string; value: number }[]>([]);
const demandName = ref<string | null>(null);
const demandTree = ref<DemandCategoryNode[]>([]);
const schemaTables = ref<SchemaTableOption[]>([]);
const tables = ref<DemandDraftTable[]>([]);
const selectedTableId = ref<string | null>(null);
const saving = ref(false);
const categoryModalMode = ref<"create" | "rename">("create");
const showCategoryModal = ref(false);
const categoryFormValue = ref("");
const demandRootKey = ref("demand");
const demandRootLabel = ref("demand");

const selectedTable = computed(() => {
  return tables.value.find((table) => table.id === selectedTableId.value) || null;
});

const selectedCategoryLabel = computed(() => {
  if (!demandName.value) return "";
  return demandName.value.split("/").filter(Boolean).join(" / ");
});

const canRenameCategory = computed(() => {
  return Boolean(demandName.value && demandName.value !== demandRootKey.value);
});
const canDeleteCategory = computed(() => {
  return Boolean(demandName.value && demandName.value !== demandRootKey.value);
});

const createField = (): DemandField => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  name: "",
  type: "",
  original_comment: "",
  supplementary_comment: "",
});

const createTable = (): DemandDraftTable => ({
  id: `table-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  name: "",
  comment: "",
  relatedTables: [],
  relatedTableDetails: {},
  fields: [createField()],
});

const fetchSources = async () => {
  try {
    const data = await get("/datasources/");
    sourceOptions.value = data.map((ds: any) => ({
      label: `${ds.name} (${ds.db_type})`,
      value: ds.id,
    }));
    if (data.length > 0 && !currentSource.value) {
      currentSource.value = data[0].id;
    }
  } catch {
    message.error("无法加载数据源");
  }
};

const fetchSchemaTables = async () => {
  if (!currentSource.value) {
    schemaTables.value = [];
    return;
  }
  try {
    const data = await get(`/schema/tables/${currentSource.value}`);
    schemaTables.value = data.map((item: any) => ({
      name: item.name,
      original_comment: item.original_comment || "",
    }));
  } catch {
    schemaTables.value = [];
    message.error("无法加载元数据表列表");
  }
};

const fetchDemandCategories = async () => {
  if (!currentSource.value) {
    demandTree.value = [];
    demandName.value = null;
    return;
  }
  try {
    const payload = await get<DemandCategoryTreeResponse>(
      `/demand/categories/${currentSource.value}`,
    );
    demandTree.value = [payload.tree];
    demandRootKey.value = payload.root_key;
    demandRootLabel.value = payload.root_label;
    if (!demandName.value && payload.default_key) {
      demandName.value = payload.default_key;
    }
  } catch (error: any) {
    message.error(error?.message || "无法加载需求分类");
  }
};

const fetchDemandDocuments = async () => {
  if (!currentSource.value || !demandName.value) {
    tables.value = [];
    selectedTableId.value = null;
    return;
  }
  try {
    const data = await get(`/demand/documents/${currentSource.value}?demand_name=${encodeURIComponent(demandName.value)}`);
    tables.value = data.map((item: any) => ({
      id: item.id,
      name: item.name || "",
      comment: item.comment || "",
      relatedTables: item.related_tables || [],
      relatedTableDetails: item.related_table_details || {},
      savedPath: item.saved_path || "",
      fields: (item.fields || []).map((field: any) => ({
        id: `${item.id}:${field.name}`,
        name: field.name || "",
        type: field.type || "",
        original_comment: field.original_comment || "",
        supplementary_comment: field.supplementary_comment || "",
      })),
    }));
    selectedTableId.value = tables.value[0]?.id || null;
  } catch (error: any) {
    tables.value = [];
    selectedTableId.value = null;
    message.error(error?.message || "无法加载需求表");
  }
};

const handleAddTable = () => {
  const draft = createTable();
  tables.value.unshift(draft);
  selectedTableId.value = draft.id;
};

const handleRemoveTable = (tableId: string) => {
  const target = tables.value.find((table) => table.id === tableId);
  if (!target) return;

  dialog.warning({
    title: "删除表草稿",
    content: `确定删除 ${target.name || "未命名表"} 吗？`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        if (target.savedPath && currentSource.value) {
          await request("/demand/documents", {
            method: "DELETE",
            body: {
              datasource_id: currentSource.value,
              saved_path: target.savedPath,
            },
          });
        }
        tables.value = tables.value.filter((table) => table.id !== tableId);
        if (selectedTableId.value === tableId) {
          selectedTableId.value = tables.value[0]?.id || null;
        }
        if (target.savedPath) {
          message.success("需求文档已删除");
        }
      } catch (error: any) {
        message.error(error?.message || "删除失败");
      }
    },
  });
};

const updateSelectedTableName = (value: string) => {
  if (!selectedTable.value) return;
  selectedTable.value.name = value;
};

const updateSelectedTableComment = (value: string) => {
  if (!selectedTable.value) return;
  selectedTable.value.comment = value;
};

const updateSelectedRelatedTables = (value: string[]) => {
  if (!selectedTable.value) return;
  selectedTable.value.relatedTables = value;
  const nextDetails: Record<string, string> = {};
  value.forEach((key) => {
    nextDetails[key] = selectedTable.value?.relatedTableDetails[key] || "";
  });
  selectedTable.value.relatedTableDetails = nextDetails;
};

const updateSelectedRelatedTableDetail = (key: string, value: string) => {
  if (!selectedTable.value) return;
  selectedTable.value.relatedTableDetails[key] = value;
};

const updateField = (fieldId: string, key: keyof DemandField, value: string) => {
  const field = selectedTable.value?.fields.find((item) => item.id === fieldId);
  if (!field) return;
  field[key] = value;
};

const addField = () => {
  if (!selectedTable.value) return;
  selectedTable.value.fields.push(createField());
};

const removeField = (fieldId: string) => {
  if (!selectedTable.value) return;
  if (selectedTable.value.fields.length === 1) {
    message.warning("至少保留一个字段");
    return;
  }
  selectedTable.value.fields = selectedTable.value.fields.filter((field) => field.id !== fieldId);
};

const validateBeforeSave = () => {
  if (!currentSource.value) {
    throw new Error("请先选择数据源");
  }
  if (!demandName.value?.trim()) {
    throw new Error("请先选择需求分类");
  }
  if (!selectedTable.value) {
    throw new Error("请先新建一个表");
  }
  if (!selectedTable.value.name.trim()) {
    throw new Error("请填写表名");
  }
  if (selectedTable.value.fields.length === 0) {
    throw new Error("请至少填写一个字段");
  }
  const hasInvalidField = selectedTable.value.fields.some(
    (field) => !field.name.trim() || !field.type.trim(),
  );
  if (hasInvalidField) {
    throw new Error("请完整填写每个字段的字段名和类型");
  }
};

const saveCurrentTable = async () => {
  try {
    validateBeforeSave();
  } catch (error: any) {
    message.error(error.message || "表单校验失败");
    return;
  }

  saving.value = true;
  try {
    const result = await post("/demand/documents", {
      datasource_id: currentSource.value,
      demand_name: demandName.value!.trim(),
      table_name: selectedTable.value!.name.trim(),
      table_comment: selectedTable.value!.comment.trim(),
      original_saved_path: selectedTable.value!.savedPath || undefined,
      related_tables: selectedTable.value!.relatedTables.map((key) => ({
        table_name: key,
        relation_detail: selectedTable.value!.relatedTableDetails[key] || "",
      })),
      fields: selectedTable.value!.fields.map(({ name, type, original_comment, supplementary_comment }) => ({
        name: name.trim(),
        type: type.trim(),
        original_comment: original_comment.trim(),
        supplementary_comment: supplementary_comment.trim(),
      })),
    });
    selectedTable.value!.savedPath = result.relative_path;
    await fetchDemandDocuments();
    message.success(`已生成 Wiki：${result.relative_path}`);
  } catch (error: any) {
    message.error(error?.message || "保存失败");
  } finally {
    saving.value = false;
  }
};

const openCreateCategoryModal = () => {
  categoryModalMode.value = "create";
  categoryFormValue.value = "";
  showCategoryModal.value = true;
};

const openRenameCategoryModal = () => {
  if (!demandName.value) {
    message.warning("请先选择一个需求分类");
    return;
  }
  categoryModalMode.value = "rename";
  categoryFormValue.value = demandName.value.split("/").pop() || "";
  showCategoryModal.value = true;
};

const submitCategoryModal = async () => {
  const name = categoryFormValue.value.trim();
  if (!name) {
    message.warning("请输入分类名称");
    return;
  }

  try {
    if (categoryModalMode.value === "create") {
      const created = await post("/demand/categories", {
        datasource_id: currentSource.value,
        name,
        parent_path: demandName.value || demandRootKey.value,
      });
      await fetchDemandCategories();
      demandName.value = created.key;
      message.success("需求分类已新增");
    } else {
      const renamed = await patchCategory({
        datasource_id: currentSource.value!,
        path: demandName.value!,
        new_name: name,
      });
      await fetchDemandCategories();
      demandName.value = renamed.key;
      message.success("需求分类已重命名");
    }
    showCategoryModal.value = false;
  } catch (error: any) {
    message.error(error?.message || "分类操作失败");
  }
};

const patchCategory = (payload: { datasource_id: number; path: string; new_name: string }) => {
  return request("/demand/categories", { method: "PATCH", body: payload });
};

const deleteCategory = async () => {
  if (!demandName.value) {
    message.warning("请先选择一个需求分类");
    return;
  }
  const currentPath = demandName.value;
  dialog.warning({
    title: "删除需求分类",
    content: `确定删除 ${currentPath} 吗？该分类下已有文档也会一起删除。`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await request("/demand/categories", {
          method: "DELETE",
          body: { datasource_id: currentSource.value, path: currentPath },
        });
        demandName.value = "";
        await fetchDemandCategories();
        message.success("需求分类已删除");
      } catch (error: any) {
        message.error(error?.message || "删除失败");
      }
    },
  });
};

watch(currentSource, () => {
  demandName.value = null;
  tables.value = [];
  selectedTableId.value = null;
  fetchDemandCategories();
  fetchSchemaTables();
});

watch(demandName, () => {
  fetchDemandDocuments();
});

onMounted(() => {
  fetchSources();
  handleAddTable();
});
</script>

<template>
  <div class="demand-page">
    <n-card class="top-card" :bordered="false">
      <div class="top-grid">
        <div class="field-block">
          <label class="top-label">数据源</label>
          <n-select
            v-model:value="currentSource"
            :options="sourceOptions"
            placeholder="请选择数据源"
          />
        </div>
        <div class="field-block field-block-wide">
          <label class="top-label">需求分类</label>
          <div class="category-row">
            <n-tree-select
              v-model:value="demandName"
              :options="demandTree"
              key-field="key"
              label-field="label"
              children-field="children"
              default-expand-all
              filterable
              clearable
              placeholder="请选择需求分类"
            />
            <n-button secondary @click="openCreateCategoryModal">
              <template #icon>
                <n-icon :component="AddOutline" />
              </template>
            </n-button>
            <n-button secondary :disabled="!canRenameCategory" @click="openRenameCategoryModal">
              <template #icon>
                <n-icon :component="CreateOutline" />
              </template>
            </n-button>
            <n-button secondary :disabled="!canDeleteCategory" @click="deleteCategory">
              <template #icon>
                <n-icon :component="TrashOutline" />
              </template>
            </n-button>
          </div>
        </div>
      </div>
    </n-card>

    <div class="workspace">
      <div class="sidebar">
        <DemandTableList
          :tables="tables"
          :selected-table-id="selectedTableId"
          @select="selectedTableId = $event"
          @add="handleAddTable"
          @remove="handleRemoveTable"
        />
      </div>
      <div class="editor">
        <DemandTableEditor
          :table="selectedTable"
          :demand-name="selectedCategoryLabel || 'demand'"
          :schema-tables="schemaTables"
          :saving="saving"
          @update-table-name="updateSelectedTableName"
          @update-table-comment="updateSelectedTableComment"
          @update-related-tables="updateSelectedRelatedTables"
          @update-related-table-detail="updateSelectedRelatedTableDetail"
          @update-field="updateField"
          @add-field="addField"
          @remove-field="removeField"
          @save="saveCurrentTable"
        />
      </div>
    </div>

    <n-modal
      v-model:show="showCategoryModal"
      preset="card"
      :title="categoryModalMode === 'create' ? '新增需求分类' : '重命名需求分类'"
      style="width: 480px"
    >
      <div class="modal-body">
        <div class="modal-tip">
          {{
            categoryModalMode === "create"
              ? `父级分类：${selectedCategoryLabel || demandRootLabel}`
              : `当前分类：${selectedCategoryLabel}`
          }}
        </div>
        <n-input
          v-model:value="categoryFormValue"
          :placeholder="categoryModalMode === 'create' ? '请输入新分类名称' : '请输入新的分类名称'"
          @keydown.enter.prevent="submitCategoryModal"
        />
        <div class="modal-actions">
          <n-button @click="showCategoryModal = false">取消</n-button>
          <n-button type="primary" @click="submitCategoryModal">确定</n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.demand-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.top-card {
  border-radius: 16px;
  border: 1px solid #efeff5;
  box-shadow: 0 8px 24px rgba(20, 35, 90, 0.04);
}

.top-grid {
  display: grid;
  grid-template-columns: 280px minmax(280px, 1fr);
  gap: 16px;
  align-items: end;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-block-wide {
  min-width: 0;
}

.top-label {
  font-size: 13px;
  font-weight: 600;
  color: #1f2225;
}

.category-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 40px 40px 40px;
  gap: 8px;
  align-items: center;
}

.workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
  overflow: hidden;
}

.sidebar,
.editor {
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.modal-tip {
  font-size: 13px;
  color: #717785;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1080px) {
  .top-grid,
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>

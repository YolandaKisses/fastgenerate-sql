<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import {
  NSelect,
  NButton,
  NIcon,
  NTabs,
  NTabPane,
  NTag,
  useMessage,
  useDialog,
} from "naive-ui";
import {
  SyncOutline,
  BookOutline,
  CodeSlashOutline,
  SparklesOutline,
} from "@vicons/ionicons5";
import TableList from "./components/TableList.vue";
import RoutineList from "./components/RoutineList.vue";
import SchemaEditor from "./components/SchemaEditor.vue";
import { get, post, streamSse } from "../../services/request";

const message = useMessage();
const dialog = useDialog();
const currentSource = ref<number | null>(null);
const sourceOptions = ref<{ label: string; value: number }[]>([]);
const tables = ref<any[]>([]);
const selectedTable = ref<any | null>(null);
const routines = ref<any[]>([]);
const selectedRoutine = ref<any | null>(null);
const knowledgeTask = ref<any | null>(null);
const latestDatasourceTask = ref<any | null>(null);
const actualTableCount = ref(0);
const knowledgeSyncing = ref(false);
const schemaSyncing = ref(false);
const routineSyncing = ref(false);
const activeTab = ref<"schema" | "routines">("schema");
const LS_KEY = "fastgenerate_last_datasource_id";

// 当前活跃的知识库同步流式请求
let activeKnowledgeController: AbortController | null = null;

// 当前处理中的表名（用于实时展示）
// 移除了独立的 currentSyncTable ref，改用 knowledgeTask.current_table

const formatKnowledgeBanner = (task: any | null) => {
  if (!task) return "尚未同步知识库";
  const completed = task.completed_tables ?? 0;
  const total = task.total_tables ?? 0;

  if (task.status === "completed") {
    if (actualTableCount.value > total) {
      return `知识库已过期 (${total}/${actualTableCount.value} 表已同步)`;
    }
    return `知识库已同步成功 ${completed} / ${total}`;
  }
  if (task.status === "partial_success") {
    return `知识库部分同步成功 ${completed} / ${total}`;
  }
  if (task.status === "failed") {
    return `知识库同步失败 ${completed} / ${total}`;
  }

  // running 状态下显示当前正在处理的表名
  if (task.current_table) {
    return `同步进行中 ${completed} / ${total} — 正在处理: ${task.current_table}`;
  }
  return `知识库同步进行中 ${completed} / ${total}`;
};

const knowledgeDetailMessage = (task: any | null) => {
  if (!task) return "";
  if (task.status === "partial_success" || task.status === "failed") {
    return task.error_message || task.last_message || "";
  }
  return "";
};

const fetchSources = async () => {
  try {
    const data = await get("/datasources/");
    sourceOptions.value = data.map((ds: any) => ({
      label: `${ds.name} (${ds.db_type})`,
      value: ds.id,
    }));

    // 尝试从本地存储恢复上一次的选择
    const lastId = localStorage.getItem(LS_KEY);
    if (!currentSource.value && lastId) {
      const id = parseInt(lastId);
      if (sourceOptions.value.find((opt) => opt.value === id)) {
        currentSource.value = id;
      }
    }

    // 校验当前选中项是否依然有效
    if (
      currentSource.value &&
      !sourceOptions.value.find((opt) => opt.value === currentSource.value)
    ) {
      currentSource.value = null;
    }

    if (data.length > 0 && !currentSource.value) {
      currentSource.value = data[0].id;
    }
  } catch (error) {
    message.error("无法加载数据源");
  }
};

const fetchTables = async (dsId: number) => {
  try {
    tables.value = await get(`/schema/tables/${dsId}`);
    if (tables.value.length > 0) {
      selectedTable.value = tables.value[0];
    } else {
      selectedTable.value = null;
    }
  } catch (error) {
    message.error("无法加载表结构");
  }
};

const fetchRoutines = async (dsId: number) => {
  try {
    routines.value = await get(`/schema/routines/${dsId}`);
    selectedRoutine.value =
      routines.value.length > 0 ? routines.value[0] : null;
  } catch (error) {
    routines.value = [];
    selectedRoutine.value = null;
    message.error("无法加载存储过程");
  }
};

const fetchLatestKnowledgeTask = async (dsId: number) => {
  try {
    const data = await get(`/schema/knowledge/status/${dsId}`);
    knowledgeTask.value = data.task;
    latestDatasourceTask.value = data.latest_datasource_task;
    actualTableCount.value = data.actual_table_count;

    if (
      data.task &&
      (data.task.status === "running" || data.task.status === "pending")
    ) {
      knowledgeSyncing.value = true;
      subscribeKnowledgeTask(data.task.id);
    } else {
      knowledgeSyncing.value = false;
    }
  } catch (error) {
    console.error("无法加载知识库任务状态", error);
  }
};

// 清理活跃的 SSE 连接
const cleanupKnowledgeSSE = () => {
  if (activeKnowledgeController) {
    activeKnowledgeController.abort();
    activeKnowledgeController = null;
  }
};

watch(currentSource, (newVal) => {
  knowledgeTask.value = null;
  latestDatasourceTask.value = null;
  knowledgeSyncing.value = false;
  routines.value = [];
  selectedRoutine.value = null;
  cleanupKnowledgeSSE();
  if (newVal) {
    localStorage.setItem(LS_KEY, newVal.toString());
    fetchTables(newVal);
    fetchRoutines(newVal);
    fetchLatestKnowledgeTask(newVal);
  }
});

onMounted(() => {
  fetchSources();
});

onUnmounted(() => {
  cleanupKnowledgeSSE();
});

const handleSelectTable = (table: any) => {
  selectedTable.value = table;
};

const handleSelectRoutine = (routine: any) => {
  selectedRoutine.value = routine;
};

const handleSync = async () => {
  if (!currentSource.value || schemaSyncing.value) return;
  const sourceId = currentSource.value;

  dialog.info({
    title: "同步数据源结构",
    content: "将从数据库重新读取表和字段信息，确定继续吗？",
    positiveText: "开始同步",
    negativeText: "取消",
    onPositiveClick: () => {
      schemaSyncing.value = true;
      message.info("同步任务已在后台启动，请稍候...");
      post(`/schema/sync/${sourceId}`)
        .then((data) => {
          if (data.success) {
            message.success(data.message);
            fetchTables(sourceId);
            fetchLatestKnowledgeTask(sourceId);
          } else {
            message.error(data.message);
          }
        })
        .catch(() => {
          message.error("同步请求失败");
        })
        .finally(() => {
          schemaSyncing.value = false;
        });
      // 不返回 Promise，让弹窗立即关闭
    },
  });
};

// ---------------------------------------------------------------------------
// SSE 知识库同步：后端任务后台跑，前端只订阅进度
// ---------------------------------------------------------------------------
const subscribeKnowledgeTask = (taskId: number) => {
  cleanupKnowledgeSSE();

  const controller = new AbortController();
  activeKnowledgeController = controller;

  const refreshAfterTerminal = () => {
    controller.abort();
    activeKnowledgeController = null;
    if (currentSource.value) {
      fetchTables(currentSource.value);
      fetchLatestKnowledgeTask(currentSource.value);
      fetchSources();
    }
  };

  streamSse(
    `/schema/knowledge/tasks/${taskId}/events`,
    {
      status: (data) => {
        const status = data.status || "running";

        const currentScope = data.scope || knowledgeTask.value?.scope;
        knowledgeTask.value = {
          ...knowledgeTask.value,
          id: data.task_id ?? knowledgeTask.value?.id,
          status,
          scope: currentScope,
          mode: data.mode ?? knowledgeTask.value?.mode,
          completed_tables:
            data.completed_tables ?? knowledgeTask.value?.completed_tables ?? 0,
          failed_tables:
            data.failed_tables ?? knowledgeTask.value?.failed_tables ?? 0,
          total_tables:
            data.total_tables ?? knowledgeTask.value?.total_tables ?? 0,
          current_table: data.current_table ?? null,
          error_message:
            data.error_message ?? knowledgeTask.value?.error_message,
        };

        if (currentScope !== "table") {
          latestDatasourceTask.value = knowledgeTask.value;
        }

        if (status === "completed") {
          knowledgeSyncing.value = false;
          const currentScope = knowledgeTask.value?.scope;
          if (currentScope === "table") {
            message.success(data.message || "知识库同步完成", {
              duration: 0,
              closable: true,
            });
          } else {
            message.success(data.message || "知识库同步完成");
          }
          refreshAfterTerminal();
        } else if (status === "partial_success") {
          knowledgeSyncing.value = false;
          if (knowledgeTask.value?.scope === "table") {
            message.warning(data.message || "知识库部分同步成功", {
              duration: 0,
              closable: true,
            });
          } else {
            message.warning(data.message || "知识库部分同步成功");
          }
          refreshAfterTerminal();
        } else if (status === "failed") {
          knowledgeSyncing.value = false;
          if (knowledgeTask.value?.scope === "table") {
            message.error(
              data.error_message || data.message || "知识库同步失败",
              { duration: 0, closable: true },
            );
          } else {
            message.error(
              data.error_message || data.message || "知识库同步失败",
            );
          }
          refreshAfterTerminal();
        }
      },

      error: (data) => {
        if (data.message) {
          if (knowledgeTask.value?.scope === "table") {
            message.error(data.message, { duration: 0, closable: true });
          } else {
            message.error(data.message);
          }
        }
        knowledgeSyncing.value = false;
        controller.abort();
        activeKnowledgeController = null;
        if (currentSource.value) {
          fetchLatestKnowledgeTask(currentSource.value);
          fetchSources();
        }
      },
    },
    { signal: controller.signal },
  ).catch((error) => {
    if (controller.signal.aborted) return;
    if (knowledgeTask.value?.scope === "table") {
      message.error(error?.message || "知识库同步 SSE 连接中断", {
        duration: 0,
        closable: true,
      });
    } else {
      message.error(error?.message || "知识库同步 SSE 连接中断");
    }
    knowledgeSyncing.value = false;
    activeKnowledgeController = null;
    if (currentSource.value) {
      fetchLatestKnowledgeTask(currentSource.value);
      fetchSources();
    }
  });
};

const handleKnowledgeSync = async () => {
  if (!currentSource.value) return;
  const sourceId = currentSource.value;
  const totalTables = tables.value.length;

  dialog.warning({
    title: "确认同步知识库",
    content: "是否已完成本地补充配置？确认后将开始知识库同步。",
    positiveText: "确认开始",
    negativeText: "取消",
    onPositiveClick: async () => {
      cleanupKnowledgeSSE();
      knowledgeSyncing.value = true;
      knowledgeTask.value = {
        status: "pending",
        completed_tables: 0,
        total_tables: totalTables,
      };

      try {
        const task = await post(`/schema/knowledge/sync/${sourceId}`, {
          mode: "basic",
        });
        knowledgeTask.value = task;
        fetchSources();
        subscribeKnowledgeTask(task.id);
      } catch (error: any) {
        knowledgeSyncing.value = false;
        message.error(error.message || "知识库同步启动失败");
      }
    },
  });
};

const handleKnowledgeAiSync = async () => {
  if (!currentSource.value) return;
  const sourceId = currentSource.value;
  const totalTables = tables.value.length;

  dialog.warning({
    title: "确认 AI 全量同步",
    content: `将对数据源全部 ${totalTables} 张表执行 AI 分析，预计耗时较长（约 ${Math.ceil(totalTables * 0.5)} 分钟）。是否继续？`,
    positiveText: "确认开始",
    negativeText: "取消",
    onPositiveClick: async () => {
      cleanupKnowledgeSSE();
      knowledgeSyncing.value = true;
      knowledgeTask.value = {
        status: "pending",
        completed_tables: 0,
        total_tables: totalTables,
      };

      try {
        const task = await post(`/schema/knowledge/sync/${sourceId}`, {
          mode: "ai_enhanced",
        });
        knowledgeTask.value = task;
        fetchSources();
        subscribeKnowledgeTask(task.id);
      } catch (error: any) {
        knowledgeSyncing.value = false;
        message.error(error.message || "AI 全量同步启动失败");
      }
    },
  });
};

const handleRoutineSync = async () => {
  if (!currentSource.value || routineSyncing.value) return;
  const sourceId = currentSource.value;

  dialog.info({
    title: "同步存储过程",
    content:
      "将从 Oracle 重新读取当前 Schema 下的存储过程与函数原文，确定继续吗？",
    positiveText: "开始同步",
    negativeText: "取消",
    onPositiveClick: async () => {
      routineSyncing.value = true;
      message.info("存储过程同步任务已启动，请稍候...");
      try {
        const data = await post(`/schema/routines/sync/${sourceId}`);
        if (data.success) {
          message.success(data.message || "存储过程同步完成");
          await fetchRoutines(sourceId);
          fetchSources();
        } else {
          message.error(data.message || "存储过程同步失败");
        }
      } catch (error: any) {
        message.error(error?.message || "存储过程同步失败");
      } finally {
        routineSyncing.value = false;
      }
    },
  });
};

const handleSingleTableSync = async (mode: "basic" | "ai_enhanced") => {
  if (!selectedTable.value || knowledgeSyncing.value) return;
  const tableId = selectedTable.value.id;

  cleanupKnowledgeSSE();
  knowledgeSyncing.value = true;
  knowledgeTask.value = {
    status: "pending",
    scope: "table",
    completed_tables: 0,
    total_tables: 1,
    current_table: selectedTable.value.name,
  };

  try {
    const task = await post(`/schema/knowledge/sync-table/${tableId}`, {
      mode,
    });
    knowledgeTask.value = task;
    subscribeKnowledgeTask(task.id);
    if (mode === "ai_enhanced") {
      message.info("正在执行 AI 深度分析，请稍候...");
    }
  } catch (error: any) {
    knowledgeSyncing.value = false;
    message.error(error?.message || "启动单表同步失败");
  }
};
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div class="header-top">
        <div class="header-left">
          <h1 class="page-title">Schema备注管理与存储过程</h1>
          <p class="page-subtitle">
            管理数据库元数据与存储过程，同步结构事实并为 AI
            深度解析提供更完整的业务上下文。
          </p>
        </div>
        <div class="header-status">
          <template v-if="latestDatasourceTask">
            <div
              class="knowledge-banner"
              :class="[
                `is-${latestDatasourceTask.status}`,
                {
                  'is-expired':
                    latestDatasourceTask.status === 'completed' &&
                    actualTableCount > latestDatasourceTask.total_tables,
                },
              ]"
            >
              <span class="status-dot"></span>
              {{ formatKnowledgeBanner(latestDatasourceTask) }}
            </div>
            <div
              v-if="knowledgeDetailMessage(latestDatasourceTask)"
              class="knowledge-detail"
            >
              {{ knowledgeDetailMessage(latestDatasourceTask) }}
            </div>
          </template>
          <div v-else class="knowledge-banner is-none">
            <span class="status-dot"></span>
            尚未同步知识库
          </div>
        </div>
      </div>
      <div class="toolbar-row">
        <div class="toolbar-primary">
          <n-select
            v-model:value="currentSource"
            :options="sourceOptions"
            placeholder="选择数据源"
            style="width: 260px"
          />
          <n-button
            secondary
            size="small"
            :loading="schemaSyncing"
            :disabled="knowledgeSyncing || schemaSyncing || routineSyncing"
            @click="handleSync"
          >
            <template #icon>
              <n-icon><SyncOutline /></n-icon>
            </template>
            同步数据源Schema
          </n-button>
          <n-button
            secondary
            size="small"
            :loading="routineSyncing"
            :disabled="knowledgeSyncing || schemaSyncing || routineSyncing"
            @click="handleRoutineSync"
          >
            <template #icon>
              <n-icon><CodeSlashOutline /></n-icon>
            </template>
            同步存储过程
          </n-button>
          <n-button
            type="primary"
            size="small"
            :loading="knowledgeSyncing && knowledgeTask?.scope !== 'table'"
            :disabled="knowledgeSyncing || schemaSyncing || routineSyncing"
            @click="handleKnowledgeSync"
          >
            <template #icon>
              <n-icon><BookOutline /></n-icon>
            </template>
            {{
              knowledgeSyncing && knowledgeTask?.scope !== "table"
                ? "同步中..."
                : "基础全量同步（WIKI）"
            }}
          </n-button>
          <n-button
            type="warning"
            size="small"
            :loading="knowledgeSyncing && knowledgeTask?.scope !== 'table'"
            :disabled="knowledgeSyncing || schemaSyncing || routineSyncing"
            @click="handleKnowledgeAiSync"
          >
            <template #icon>
              <n-icon><SparklesOutline /></n-icon>
            </template>
            {{
              knowledgeSyncing && knowledgeTask?.scope !== "table"
                ? "同步中..."
                : "AI 全量同步（WIKI）"
            }}
          </n-button>
        </div>
      </div>
    </div>

    <div class="content-shell">
      <n-tabs
        v-model:value="activeTab"
        type="line"
        animated
        class="manager-tabs"
      >
        <n-tab-pane name="schema" tab="Schema">
          <div class="schema-container">
            <div class="sider-panel">
              <TableList
                :tables="tables"
                :selected-table="selectedTable"
                @select="handleSelectTable"
              />
            </div>
            <div class="main-panel">
              <SchemaEditor
                :table="selectedTable"
                :all-tables="tables"
                :knowledge-task="knowledgeTask"
                :knowledge-syncing="knowledgeSyncing"
                :schema-syncing="schemaSyncing"
                @sync="handleSync"
                @sync-knowledge="handleKnowledgeSync"
                @sync-table="handleSingleTableSync"
              />
            </div>
          </div>
        </n-tab-pane>
        <n-tab-pane name="routines" tab="存储过程">
          <div class="schema-container">
            <div class="sider-panel routine-sider">
              <div class="panel-caption">
                <span>已同步对象</span>
                <n-tag size="small" round type="info" :bordered="false">
                  {{ routines.length }}
                </n-tag>
              </div>
              <RoutineList
                :routines="routines"
                :selected-routine="selectedRoutine"
                @select="handleSelectRoutine"
              />
            </div>
            <div class="main-panel">
              <div class="routine-preview-card">
                <template v-if="selectedRoutine">
                  <div class="routine-preview-header">
                    <div>
                      <h3 class="routine-preview-title">
                        {{ selectedRoutine.name }}
                      </h3>
                      <p class="routine-preview-subtitle">
                        {{ selectedRoutine.owner }} ·
                        {{ selectedRoutine.routine_type }}
                      </p>
                    </div>
                  </div>
                  <pre class="routine-preview-body">{{
                    selectedRoutine.definition_text
                  }}</pre>
                </template>
                <div v-else class="routine-empty-state">
                  请选择左侧存储过程查看原文；若列表为空，请先点击上方“同步存储过程”。
                </div>
              </div>
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.page-header {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-bottom: 5px;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.header-status {
  display: flex;
  align-items: flex-end;
  flex-direction: column;
  gap: 8px;
}

.toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  border: 1px solid #e8ebf2;
  border-radius: 12px;
  background: linear-gradient(135deg, #ffffff 0%, #f7f9fc 100%);
}

.toolbar-primary {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.content-shell {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.manager-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

:deep(.manager-tabs .n-tabs-nav) {
  flex: 0 0 auto;
}

:deep(.manager-tabs .n-tabs-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

:deep(.manager-tabs .n-tabs-pane-wrapper) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

:deep(.manager-tabs .n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 28px;
  margin: 0 0 8px 0;
  color: #181c22;
}

.page-subtitle {
  font-size: 14px;
  line-height: 22px;
  color: #717785;
  margin: 0;
}

.knowledge-banner {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  gap: 8px;
}

.knowledge-detail {
  max-width: 420px;
  color: #8a4b0f;
  font-size: 12px;
  line-height: 1.4;
  text-align: right;
}

.knowledge-banner.is-expired {
  color: #8a6700;
  background: #fff7db;
  border: 1px solid #f3df9b;
}

.knowledge-banner.is-none {
  color: #717785;
  background: #f4f5f7;
  border: 1px solid #e1e3e6;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.knowledge-banner.is-pending,
.knowledge-banner.is-running {
  color: #8a6700;
  background: #fff7db;
  border: 1px solid #f3df9b;
}

.knowledge-banner.is-completed {
  color: #17623a;
  background: #e9f8ef;
  border: 1px solid #b8e2c6;
}

.knowledge-banner.is-partial_success {
  color: #a16207;
  background: #fefce8;
  border: 1px solid #fef08a;
}

.knowledge-banner.is-failed {
  color: #a53a3a;
  background: #fdeeee;
  border: 1px solid #f3c3c3;
}

.schema-container {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 24px;
  padding-top: 8px;
  overflow: hidden;
}

.sider-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.routine-sider {
  width: 360px;
}

.panel-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 2px;
  font-size: 13px;
  font-weight: 600;
  color: #4f5666;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.routine-preview-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border: 1px solid #e6e9f0;
  border-radius: 16px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.05);
  overflow: hidden;
}

.routine-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 22px 24px 16px;
  border-bottom: 1px solid #edf1f7;
}

.routine-preview-title {
  margin: 0 0 6px 0;
  font-size: 18px;
  line-height: 1.3;
  color: #1b2230;
}

.routine-preview-subtitle {
  margin: 0;
  font-size: 12px;
  color: #7b8190;
}

.routine-preview-body {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 22px 24px 28px;
  overflow: auto;
  background: linear-gradient(180deg, #fbfcfe 0%, #f4f7fb 100%);
  color: #253041;
  font-size: 13px;
  line-height: 1.6;
  font-family: "SFMono-Regular", "Menlo", "Monaco", "Consolas", monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

.routine-empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #7b8190;
  font-size: 14px;
  text-align: center;
}

@media (max-width: 1100px) {
  .header-top,
  .toolbar-row,
  .schema-container {
    flex-direction: column;
    align-items: stretch;
  }

  .header-status {
    align-items: flex-start;
  }

  .knowledge-detail {
    text-align: left;
  }

  .sider-panel,
  .routine-sider {
    width: 100%;
  }
}
</style>

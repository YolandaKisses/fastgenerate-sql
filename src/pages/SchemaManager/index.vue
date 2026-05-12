<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import {
  NSelect,
  NButton,
  NIcon,
  NTabs,
  NTabPane,
  NTag,
  NTooltip,
  NModal,
  NList,
  NListItem,
  NScrollbar,
  useMessage,
  useDialog,
} from "naive-ui";
import {
  SyncOutline,
  BookOutline,
  CodeSlashOutline,
  SparklesOutline,
  CloseOutline,
  RefreshOutline,
  GitNetworkOutline,
} from "@vicons/ionicons5";
import TableList from "./components/TableList.vue";
import RoutineList from "./components/RoutineList.vue";
import ViewList from "./components/ViewList.vue";
import SchemaEditor from "./components/SchemaEditor.vue";
import LineageExplorer from "./components/LineageExplorer.vue";
import { get, post, streamSse } from "../../services/request";

const message = useMessage();
const dialog = useDialog();
const currentSource = ref<number | null>(null);
const sourceOptions = ref<{ label: string; value: number }[]>([]);
const tables = ref<any[]>([]);
const selectedTable = ref<any | null>(null);
const views = ref<any[]>([]);
const selectedView = ref<any | null>(null);
const routines = ref<any[]>([]);
const selectedRoutine = ref<any | null>(null);
const knowledgeTask = ref<any | null>(null);
const latestDatasourceTask = ref<any | null>(null);
const actualTableCount = ref(0);
const wikiTableCount = ref(0);
const knowledgeSyncing = ref(false);
const schemaSyncing = ref(false);
const routineSyncing = ref(false);
const viewSyncing = ref(false);
const metadataSyncing = ref(false);
const activeTab = ref<"schema" | "views" | "routines" | "lineage">("schema");
const selectedLineageObject = ref<{ type: string; name: string } | null>(null);
const bannerDismissed = ref(false);
const showFailedModal = ref(false);
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
    if (wikiTableCount.value === 0) {
      return "尚未同步知识库";
    }
    if (wikiTableCount.value < total) {
      return `知识库已过期 (${wikiTableCount.value}/${total} 页仍存在)`;
    }
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
  if (task.status === "cancelled") {
    return `知识库同步已由用户终止 ${completed} / ${total}`;
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
    if (task.failed_tables > 0) {
      return `共有 ${task.failed_tables} 张表同步失败`;
    }
    return task.error_message || task.last_message || "";
  }
  return "";
};

const parseFailedTableNames = (task: any | null): string[] => {
  if (!task || !task.failed_table_names) return [];
  try {
    const parsed = JSON.parse(task.failed_table_names);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
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

const fetchViews = async (dsId: number) => {
  try {
    views.value = await get(`/schema/views/${dsId}`);
    selectedView.value = views.value.length > 0 ? views.value[0] : null;
  } catch (error) {
    views.value = [];
    selectedView.value = null;
    message.error("无法加载视图");
  }
};

const fetchLatestKnowledgeTask = async (dsId: number) => {
  try {
    const data = await get(`/schema/knowledge/status/${dsId}`);
    knowledgeTask.value = data.task;
    latestDatasourceTask.value = data.latest_datasource_task;
    actualTableCount.value = data.actual_table_count;
    wikiTableCount.value = data.wiki_table_count ?? 0;

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
  wikiTableCount.value = 0;
  views.value = [];
  selectedView.value = null;
  routines.value = [];
  selectedRoutine.value = null;
  bannerDismissed.value = false;
  if (newVal) {
    localStorage.setItem(LS_KEY, newVal.toString());
    fetchTables(newVal);
    fetchViews(newVal);
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

const handleSelectView = (view: any) => {
  selectedView.value = view;
};

const normalizeMetadataSyncMessage = (messageText: string | undefined, fallback: string) => {
  const text = (messageText || fallback).trim();
  return text
    .replace("，请继续同步到知识库", "")
    .replace("请继续同步到知识库", "")
    .trim();
};

const runSchemaSync = async (sourceId: number) => {
  schemaSyncing.value = true;
  try {
    const data = await post(`/schema/sync/${sourceId}`);
    if (!data.success) {
      throw new Error(data.message || "表结构同步失败");
    }
    await fetchTables(sourceId);
    await fetchLatestKnowledgeTask(sourceId);
    return data;
  } finally {
    schemaSyncing.value = false;
  }
};

const runRoutineSync = async (sourceId: number) => {
  routineSyncing.value = true;
  try {
    const data = await post(`/schema/routines/sync/${sourceId}`);
    if (!data.success) {
      throw new Error(data.message || "存储过程同步失败");
    }
    await fetchRoutines(sourceId);
    return data;
  } finally {
    routineSyncing.value = false;
  }
};

const runViewSync = async (sourceId: number) => {
  viewSyncing.value = true;
  try {
    const data = await post(`/schema/views/sync/${sourceId}`);
    if (!data.success) {
      throw new Error(data.message || "视图同步失败");
    }
    await fetchViews(sourceId);
    return data;
  } finally {
    viewSyncing.value = false;
  }
};

const handleSync = async () => {
  if (!currentSource.value || schemaSyncing.value) return;
  const sourceId = currentSource.value;

  dialog.info({
    title: "同步数据源结构",
    content: "将从数据库重新读取表和字段信息，确定继续吗？",
    positiveText: "开始同步",
    negativeText: "取消",
    onPositiveClick: async () => {
      message.info("表结构同步任务已启动，请稍候...");
      try {
        const data = await runSchemaSync(sourceId);
        message.success(
          normalizeMetadataSyncMessage(data.message, "表结构同步完成"),
        );
      } catch (error: any) {
        message.error(error?.message || "同步请求失败");
      }
    },
  });
};

const handleMetadataSync = async () => {
  if (
    !currentSource.value ||
    metadataSyncing.value ||
    knowledgeSyncing.value ||
    schemaSyncing.value ||
    routineSyncing.value ||
    viewSyncing.value
  ) {
    return;
  }
  const sourceId = currentSource.value;

  dialog.info({
    title: "同步数据库对象",
    content: "将按顺序同步表结构、存储过程和视图，确定继续吗？",
    positiveText: "开始同步",
    negativeText: "取消",
    onPositiveClick: () => {
      void (async () => {
        metadataSyncing.value = true;
        try {
          message.info("开始同步表结构...");
          const schemaData = await runSchemaSync(sourceId);
          message.success(
            normalizeMetadataSyncMessage(schemaData.message, "表结构同步完成"),
          );

          message.info("开始同步存储过程...");
          const routineData = await runRoutineSync(sourceId);
        message.success(routineData.message || "存储过程同步完成");

        message.info("开始同步视图...");
        const viewData = await runViewSync(sourceId);
        message.success(viewData.message || "视图同步完成");

        await fetchSources();
        message.success("数据库对象已同步完成");
        } catch (error: any) {
          message.error(error?.message || "数据库对象同步失败");
        } finally {
          metadataSyncing.value = false;
        }
      })();
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
          failed_table_names:
            data.failed_table_names ?? knowledgeTask.value?.failed_table_names,
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
        } else if (status === "cancelled") {
          knowledgeSyncing.value = false;
          message.info(data.message || "知识库同步已取消");
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

const handleStopKnowledgeSync = async (taskId: number) => {
  try {
    const res: any = await post(`/schema/knowledge/tasks/${taskId}/stop`, {});
    if (res.success) {
      message.success("已发送停止指令");
    } else {
      message.warning("停止任务失败");
    }
  } catch (err) {
    message.error("请求失败");
  }
};

const handleKnowledgeSync = async () => {
  if (!currentSource.value) return;
  const sourceId = currentSource.value;
  const totalTables = tables.value.length;

  dialog.warning({
    title: "确认全量同步知识库 (WIKI)",
    content:
      "将同步本地备注、关联表及存储过程事实。注意：此操作将清空并重建当前数据源下所有已生成的知识库页面。是否继续？",
    positiveText: "确认重建",
    negativeText: "取消",
    onPositiveClick: async () => {
      cleanupKnowledgeSSE();
      bannerDismissed.value = false;
      knowledgeSyncing.value = true;
      knowledgeTask.value = {
        status: "pending",
        completed_tables: 0,
        total_tables: totalTables,
        is_incremental: true,
      };

      try {
        const task = await post(`/schema/knowledge/sync/${sourceId}`, {
          mode: "basic",
          is_incremental: true, // 默认增量，避免误删
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

const handleKnowledgeFullRebuild = async (mode: "basic" | "ai_enhanced") => {
  if (!currentSource.value) return;
  const sourceId = currentSource.value;
  const totalTables = tables.value.length;

  dialog.warning({
    title:
      mode === "ai_enhanced" ? "确认 AI 深度全量重建" : "确认全量重建知识库",
    content:
      "此操作将【彻底清空】当前数据源下所有已生成的页面并重新生成。确定要重建吗？",
    positiveText: "确定重建",
    negativeText: "取消",
    onPositiveClick: async () => {
      cleanupKnowledgeSSE();
      bannerDismissed.value = false;
      knowledgeSyncing.value = true;
      knowledgeTask.value = {
        status: "pending",
        completed_tables: 0,
        total_tables: totalTables,
        is_incremental: false,
      };
      try {
        const task = await post(`/schema/knowledge/sync/${sourceId}`, {
          mode,
          is_incremental: false,
        });
        knowledgeTask.value = task;
        subscribeKnowledgeTask(task.id);
      } catch (error: any) {
        knowledgeSyncing.value = false;
        message.error(error.message || "重建启动失败");
      }
    },
  });
};

const handleKnowledgeAiSync = async () => {
  if (!currentSource.value) return;
  const sourceId = currentSource.value;
  const totalTables = tables.value.length;

  dialog.warning({
    title: "确认增量同步知识库",
    content:
      "将调用 AI 仅对尚未生成知识库文档的表进行深度业务解读。已生成的文档将被安全跳过，不会被覆盖。是否继续？",
    positiveText: "确认增量同步",
    negativeText: "取消",
    onPositiveClick: async () => {
      cleanupKnowledgeSSE();
      bannerDismissed.value = false;
      knowledgeSyncing.value = true;
      knowledgeTask.value = {
        status: "pending",
        completed_tables: 0,
        total_tables: totalTables,
        is_incremental: true,
      };

      try {
        const task = await post(`/schema/knowledge/sync/${sourceId}`, {
          mode: "ai_enhanced",
          is_incremental: true, // 默认增量
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
      message.info("存储过程同步任务已启动，请稍候...");
      try {
        const data = await runRoutineSync(sourceId);
        message.success(data.message || "存储过程同步完成");
        fetchSources();
      } catch (error: any) {
        message.error(error?.message || "存储过程同步失败");
      }
    },
  });
};

const handleViewSync = async () => {
  if (!currentSource.value || viewSyncing.value) return;
  const sourceId = currentSource.value;

  dialog.info({
    title: "同步视图",
    content: "将从 Oracle 重新读取当前 Schema 下的视图定义与备注，确定继续吗？",
    positiveText: "开始同步",
    negativeText: "取消",
    onPositiveClick: async () => {
      message.info("视图同步任务已启动，请稍候...");
      try {
        const data = await runViewSync(sourceId);
        message.success(data.message || "视图同步完成");
        fetchSources();
      } catch (error: any) {
        message.error(error?.message || "视图同步失败");
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

const viewLineage = (type: string, name: string) => {
  selectedLineageObject.value = { type, name };
  activeTab.value = "lineage";
};
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div class="header-top">
        <div class="header-left">
          <h1 class="page-title">元数据与脚本管理</h1>
          <p class="page-subtitle">
            管理数据库元数据、视图与存储过程，同步结构事实并为 AI
            深度解析提供更完整的业务上下文。
          </p>
        </div>
        <div class="header-status" v-if="!bannerDismissed">
          <template v-if="latestDatasourceTask">
            <div
              class="knowledge-banner"
              :class="[
                latestDatasourceTask.status === 'completed' &&
                wikiTableCount === 0
                  ? 'is-none'
                  : `is-${latestDatasourceTask.status}`,
                {
                  'is-expired':
                    latestDatasourceTask.status === 'completed' &&
                    (wikiTableCount === 0 ||
                      wikiTableCount < latestDatasourceTask.total_tables ||
                      actualTableCount > latestDatasourceTask.total_tables),
                },
              ]"
            >
              <span class="status-dot"></span>
              {{ formatKnowledgeBanner(latestDatasourceTask) }}
              <n-button
                v-if="latestDatasourceTask.status === 'running' || latestDatasourceTask.status === 'pending'"
                text
                type="error"
                size="tiny"
                style="margin-left: 12px; font-weight: 600"
                @click="handleStopKnowledgeSync(latestDatasourceTask.id)"
              >
                停止同步
              </n-button>
              <n-button
                v-if="
                  latestDatasourceTask.status !== 'running' &&
                  latestDatasourceTask.status !== 'pending'
                "
                quaternary
                circle
                size="tiny"
                class="banner-close"
                @click="bannerDismissed = true"
              >
                <template #icon
                  ><n-icon><CloseOutline /></n-icon
                ></template>
              </n-button>
            </div>
            <div
              v-if="knowledgeDetailMessage(latestDatasourceTask)"
              class="knowledge-detail"
            >
              {{ knowledgeDetailMessage(latestDatasourceTask) }}
              <n-button
                v-if="parseFailedTableNames(latestDatasourceTask).length > 0"
                text
                type="primary"
                size="tiny"
                style="margin-left: 8px"
                @click="showFailedModal = true"
              >
                查看失败列表
              </n-button>
            </div>
          </template>
          <div v-else class="knowledge-banner is-none">
            <span class="status-dot"></span>
            尚未同步知识库
          </div>
        </div>
        <div v-else class="header-status-dismissed">
          <n-button quaternary size="tiny" @click="bannerDismissed = false">
            <template #icon
              ><n-icon><RefreshOutline /></n-icon
            ></template>
            恢复显示状态
          </n-button>
        </div>
      </div>
      <div class="toolbar-row">
        <div class="toolbar-primary">
          <n-select
            v-model:value="currentSource"
            :options="sourceOptions"
            placeholder="选择数据源"
            size="small"
            style="width: 260px"
          />
          <n-button
            secondary
            size="small"
            :loading="metadataSyncing"
            :disabled="
              knowledgeSyncing ||
              metadataSyncing ||
              schemaSyncing ||
              routineSyncing ||
              viewSyncing
            "
            @click="handleMetadataSync"
          >
            <template #icon>
              <n-icon><SyncOutline /></n-icon>
            </template>
            同步数据库对象
          </n-button>

          <!-- <n-tooltip trigger="hover">
            <template #trigger>
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
                    : "基础增量同步"
                }}
              </n-button>
            </template>
            快速同步本地备注、表间关系及存储过程事实。
          </n-tooltip> -->
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button
                type="warning"
                size="small"
                :loading="
                  knowledgeSyncing &&
                  knowledgeTask?.scope !== 'table' &&
                  knowledgeTask?.is_incremental !== false
                "
                :disabled="
                  knowledgeSyncing ||
                  schemaSyncing ||
                  routineSyncing ||
                  viewSyncing
                "
                @click="handleKnowledgeAiSync"
              >
                <template #icon>
                  <n-icon><SparklesOutline /></n-icon>
                </template>
                {{
                  knowledgeSyncing &&
                  knowledgeTask?.scope !== "table" &&
                  knowledgeTask?.is_incremental !== false
                    ? "同步中..."
                    : "增量同步知识库"
                }}
              </n-button>
            </template>
            仅对未解析或新增的表进行 AI 深度解读，速度较快。
          </n-tooltip>

          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button
                type="warning"
                size="small"
                :loading="
                  knowledgeSyncing &&
                  knowledgeTask?.scope !== 'table' &&
                  knowledgeTask?.is_incremental === false
                "
                :disabled="
                  knowledgeSyncing ||
                  schemaSyncing ||
                  routineSyncing ||
                  viewSyncing
                "
                @click="handleKnowledgeFullRebuild('ai_enhanced')"
              >
                <template #icon>
                  <n-icon><RefreshOutline /></n-icon>
                </template>
                {{
                  knowledgeSyncing &&
                  knowledgeTask?.scope !== "table" &&
                  knowledgeTask?.is_incremental === false
                    ? "同步中..."
                    : "全量同步知识库"
                }}
              </n-button>
            </template>
            清空并彻底重新生成所有页面，用于解决结构性错误。
          </n-tooltip>
        </div>
      </div>
    </div>

    <div class="content-shell">
      <n-tabs
        v-model:value="activeTab"
        type="line"
        class="manager-tabs"
        pane-style="flex: 1; display: flex; flex-direction: column; min-height: 0;"
      >
        <n-tab-pane name="schema" tab="表结构">
          <div class="schema-container">
            <div class="sider-panel">
              <div class="panel-caption">
                <span>已同步对象</span>
                <n-tag size="small" round type="info" :bordered="false">
                  {{ tables.length }}
                </n-tag>
              </div>
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
                @view-lineage="(name) => viewLineage('table', name)"
              />
            </div>
          </div>
        </n-tab-pane>
        <n-tab-pane name="views" tab="视图">
          <div class="schema-container">
            <div class="sider-panel routine-sider">
              <div class="panel-caption">
                <span>已同步对象</span>
                <n-tag size="small" round type="success" :bordered="false">
                  {{ views.length }}
                </n-tag>
              </div>
              <ViewList
                :views="views"
                :selected-view="selectedView"
                @select="handleSelectView"
              />
            </div>
            <div class="main-panel">
              <div class="routine-preview-card">
                <template v-if="selectedView">
                  <div class="routine-preview-header">
                    <div>
                      <h3 class="routine-preview-title">{{ selectedView.name }}</h3>
                      <p class="routine-preview-subtitle">
                        {{ selectedView.owner }} · VIEW
                      </p>
                    </div>
                    <n-button secondary size="small" @click="viewLineage('view', selectedView.name)">
                      <template #icon><n-icon><GitNetworkOutline /></n-icon></template>
                      查看血缘
                    </n-button>
                  </div>
                  <div class="view-detail-body">
                    <div class="view-detail-section">
                      <label class="view-detail-label">视图备注</label>
                      <div class="view-detail-text">
                        {{ selectedView.original_comment || "无视图备注" }}
                      </div>
                    </div>
                    <div class="view-detail-section">
                      <label class="view-detail-label">视图定义</label>
                      <n-scrollbar style="max-height: 520px">
                        <pre class="routine-preview-body">{{
                          selectedView.definition_text
                        }}</pre>
                      </n-scrollbar>
                    </div>
                  </div>
                </template>
                <div v-else class="routine-empty-state">
                  请选择左侧视图查看定义；若列表为空，请先点击上方“同步视图”。
                </div>
              </div>
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
                    <n-button secondary size="small" @click="viewLineage('routine', selectedRoutine.owner + '.' + selectedRoutine.name)">
                      <template #icon><n-icon><GitNetworkOutline /></n-icon></template>
                      查看血缘
                    </n-button>
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
        <n-tab-pane name="lineage" tab="血缘图谱">
          <LineageExplorer
            v-if="currentSource"
            :datasource-id="currentSource"
            :initial-object="selectedLineageObject"
          />
          <div v-else class="routine-empty-state">
            请先选择一个数据源
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>

    <!-- 失败列表弹窗 -->
    <n-modal
      v-model:show="showFailedModal"
      preset="card"
      title="同步失败的表列表"
      style="width: 400px"
    >
      <n-scrollbar style="max-height: 400px">
        <n-list bordered>
          <n-list-item
            v-for="name in parseFailedTableNames(latestDatasourceTask)"
            :key="name"
          >
            {{ name }}
          </n-list-item>
        </n-list>
      </n-scrollbar>
      <template #footer>
        <div style="text-align: right">
          <n-button @click="showFailedModal = false">关闭</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.page-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 8px;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
}

.header-status {
  display: flex;
  align-items: center;
  flex-direction: row;
  gap: 12px;
}

.toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
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
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.manager-tabs {
  flex: 1;
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

.view-detail-body {
  flex: 1;
  min-height: 0;
  padding: 22px 24px 28px;
  overflow: auto;
  background: linear-gradient(180deg, #fbfcfe 0%, #f4f7fb 100%);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.view-detail-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.view-detail-label {
  font-size: 13px;
  font-weight: 600;
  color: #4f5666;
}

.view-detail-text {
  padding: 12px 14px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e6e9f0;
  color: #253041;
  font-size: 13px;
  line-height: 1.6;
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

.banner-close {
  margin-left: 4px;
  opacity: 0.6;
  transition: all 0.2s;
}
.banner-close:hover {
  opacity: 1;
  background-color: rgba(0, 0, 0, 0.05);
}

.header-status-dismissed {
  display: flex;
  align-items: center;
  height: 32px;
}
</style>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from "vue";
import { NSelect, NButton, useMessage, useDialog } from "naive-ui";
import AiAssistant from "./components/AiAssistant.vue";
import SqlEditor from "./components/SqlEditor.vue";
import QueryResult from "./components/QueryResult.vue";
import HermesProcess from "./components/HermesProcess.vue";
import type { HermesStep } from "./components/HermesProcess.vue";
import {
  appendHermesClarification,
  compactMessageHistoryForStorage,
  compactResultForStorage,
  formatClarification,
  startNextProcessRound,
} from "./workbenchState";
import type { MessageHistoryEntry } from "./workbenchState";
import { get, post, streamSse } from "../../services/request";

const STORAGE_KEY = "workbench_state";

const message = useMessage();
const dialog = useDialog();
const loading = ref(false);
const currentDatasource = ref<number | null>(null);
const datasourceOptions = ref<{ label: string; value: number }[]>([]);

const generatedSql = ref("");
const displayedSql = ref("");
const isRendering = ref(false);
const sqlExplanation = ref("");
const clarification = ref("");
const queryResult = ref<any | null>(null);
const hasExecutedSql = ref(false);
const currentAuditLogId = ref<number | null>(null);
const hermesSessionId = ref<string | null>(null);
const validationState = ref<"idle" | "validating" | "valid" | "invalid">(
  "idle",
);
const validationReasons = ref<string[]>([]);

// Hermes 工作过程步骤
const hermesSteps = ref<HermesStep[]>([]);
const hermesProcessRef = ref<InstanceType<typeof HermesProcess> | null>(null);

// 对话上下文历史 (用于多轮澄清)
const messageHistory = ref<MessageHistoryEntry[]>([]);

const canAskDatasource = (ds: any) => {
  return ds.status === "connection_ok" && ds.sync_status === "sync_success";
};

// 清除上下文
const handleResetContext = () => {
  dialog.warning({
    title: "确认清除上下文",
    content: "清除后将丢失当前的对话历史和生成的 SQL。确定继续吗？",
    positiveText: "确定清除",
    negativeText: "取消",
    onPositiveClick: () => {
      messageHistory.value = [];
      generatedSql.value = "";
      displayedSql.value = "";
      sqlExplanation.value = "";
      clarification.value = "";
      queryResult.value = null;
      hasExecutedSql.value = false;
      hermesSteps.value = [];
      currentAuditLogId.value = null;
      hermesSessionId.value = null;
      message.info("上下文已清除");
    },
  });
};

// 当前活跃的流式请求控制器
let activeStreamController: AbortController | null = null;

// 渐进渲染的 requestAnimationFrame ID
let renderRafId: number | null = null;

// 从 sessionStorage 恢复上次的工作状态
const restoreState = () => {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      const state = JSON.parse(saved);
      currentDatasource.value = state.datasourceId ?? null;
      generatedSql.value = state.sql ?? "";
      sqlExplanation.value = state.explanation ?? "";
      clarification.value = state.clarification ?? "";
      queryResult.value = state.result ?? null;
      hasExecutedSql.value = Boolean(state.executed ?? state.result);
      messageHistory.value = compactMessageHistoryForStorage(
        state.history ?? [],
      );
      currentAuditLogId.value = state.auditLogId ?? null;
      hermesSessionId.value = state.hermesSessionId ?? null;
      hermesSteps.value = state.hermesSteps ?? [];
    }
  } catch (error) {
    console.warn("恢复工作台状态失败", error);
  }
};

// 保存工作状态到 sessionStorage
const saveState = () => {
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        datasourceId: currentDatasource.value,
        sql: generatedSql.value,
        explanation: sqlExplanation.value,
        clarification: clarification.value,
        result: compactResultForStorage(queryResult.value),
        executed: hasExecutedSql.value,
        // Hermes session 持有模型上下文；这里保留最近记录只用于 UI 展示和浏览器存储容量保护。
        history: compactMessageHistoryForStorage(messageHistory.value),
        auditLogId: currentAuditLogId.value,
        hermesSessionId: hermesSessionId.value,
        hermesSteps: hermesSteps.value,
      }),
    );
  } catch (error) {
    console.warn("保存工作台状态失败", error);
  }
};

watch(
  [
    currentDatasource,
    generatedSql,
    sqlExplanation,
    clarification,
    queryResult,
    hasExecutedSql,
    messageHistory,
    currentAuditLogId,
    hermesSessionId,
    hermesSteps,
  ],
  saveState,
  { deep: true },
);

watch(generatedSql, async (newSql) => {
  if (!newSql) {
    validationState.value = "idle";
    validationReasons.value = [];
    return;
  }

  validationState.value = "validating";
  validationReasons.value = [];
  try {
    const data = await post("/workbench/validate", { sql: newSql });
    validationState.value = data.status === "valid" ? "valid" : "invalid";
    validationReasons.value = data.reasons || [];
  } catch {
    validationState.value = "invalid";
    validationReasons.value = ["SQL 校验请求失败"];
  }
});

onMounted(async () => {
  restoreState();

  try {
    const data = await get("/datasources/");
    datasourceOptions.value = data
      .filter(canAskDatasource)
      .map((ds: any) => ({
        label: `${ds.name} (${ds.db_type})`,
        value: ds.id,
      }));

    // 校验恢复的状态是否依然有效
    if (
      currentDatasource.value &&
      !datasourceOptions.value.find(
        (opt) => opt.value === currentDatasource.value,
      )
    ) {
      currentDatasource.value = null;
    }

    // 仅在没有有效选中项时，默认选第一个
    if (datasourceOptions.value.length > 0 && !currentDatasource.value) {
      currentDatasource.value = datasourceOptions.value[0].value;
    }
  } catch (error) {
    message.error("无法加载数据源列表");
  }
});

onUnmounted(() => {
  // 清理活跃的流式请求
  if (activeStreamController) {
    activeStreamController.abort();
    activeStreamController = null;
  }
  // 清理渐进渲染
  if (renderRafId !== null) {
    cancelAnimationFrame(renderRafId);
    renderRafId = null;
  }
});

// ---------------------------------------------------------------------------
// SQL 渐进渲染
// ---------------------------------------------------------------------------
const startProgressiveRender = (fullSql: string) => {
  displayedSql.value = "";
  isRendering.value = true;
  let index = 0;

  // 根据 SQL 长度动态调整速度：短 SQL 快渲，长 SQL 慢渲
  const totalLen = fullSql.length;
  const baseChunk = totalLen < 100 ? 4 : totalLen < 300 ? 3 : 2;

  const render = () => {
    const chunkSize = Math.min(baseChunk, totalLen - index);
    displayedSql.value += fullSql.slice(index, index + chunkSize);
    index += chunkSize;

    if (index < totalLen) {
      renderRafId = requestAnimationFrame(render);
    } else {
      isRendering.value = false;
      generatedSql.value = fullSql;
      renderRafId = null;
    }
  };

  renderRafId = requestAnimationFrame(render);
};

const processActorForPhase = (phase: string): HermesStep["actor"] => {
  if (phase === "searching_notes" || phase === "warning") return "system";
  return "hermes";
};

// ---------------------------------------------------------------------------
// SSE 流式问答
// ---------------------------------------------------------------------------
const handleQuerySubmit = (question: string) => {
  if (!currentDatasource.value) {
    message.warning("请先选择一个数据源");
    return;
  }

  // 重置状态
  loading.value = true;
  clarification.value = "";
  generatedSql.value = "";
  displayedSql.value = "";
  isRendering.value = false;
  sqlExplanation.value = "";
  queryResult.value = null;
  hasExecutedSql.value = false;
  hermesSteps.value = startNextProcessRound(
    hermesSteps.value,
    question,
  ) as HermesStep[];
  currentAuditLogId.value = null;

  // 将当前问题存入本地历史记录（用于 UI 展示和审计；Hermes 上下文由 session 持有）
  messageHistory.value.push({ role: "user", content: question });
  messageHistory.value = compactMessageHistoryForStorage(messageHistory.value);

  // 取消之前的流式请求 / 渲染
  if (activeStreamController) {
    activeStreamController.abort();
    activeStreamController = null;
  }
  if (renderRafId !== null) {
    cancelAnimationFrame(renderRafId);
    renderRafId = null;
  }

  // 启动计时器
  hermesProcessRef.value?.startTimer();

  // 构建流式请求路径
  const params = new URLSearchParams();
  params.set("datasource_id", String(currentDatasource.value));
  params.set("question", question);
  if (hermesSessionId.value) {
    params.set("hermes_session_id", hermesSessionId.value);
  }

  const controller = new AbortController();
  activeStreamController = controller;

  streamSse(`/workbench/ask_stream?${params.toString()}`, {
  status: (data) => {
    const lastStep = hermesSteps.value[hermesSteps.value.length - 1];
    if (
      data.phase === "failed" &&
      lastStep?.phase === "failed" &&
      lastStep.message === data.message
    ) {
      return;
    }
    hermesSteps.value.push({
      phase: data.phase,
      actor: processActorForPhase(data.phase),
      message: data.message,
      timestamp: Date.now(),
    });

    // 当完成或失败时停止计时器
    if (data.phase === "completed" || data.phase === "failed") {
      hermesProcessRef.value?.stopTimer();
    }
  },

  note_hit: (data) => {
    const lastStep = hermesSteps.value[hermesSteps.value.length - 1];

    if (lastStep && lastStep.phase === "note_hit") {
      // 合并逻辑：将新的表名和备注追加到现有步骤中
      lastStep.message += `, ${data.note}`;
      if (data.comment) {
        lastStep.detail = lastStep.detail
          ? `${lastStep.detail}; ${data.comment}`
          : data.comment;
      }
    } else {
      hermesSteps.value.push({
        phase: "note_hit",
        actor: "system",
        message: `命中笔记: ${data.note}`,
        detail: data.comment || undefined,
        timestamp: Date.now(),
      });
    }
  },

  note_used: (data) => {
    const lastStep = hermesSteps.value[hermesSteps.value.length - 1];

    if (lastStep && lastStep.phase === "note_used") {
      lastStep.message += `, ${data.note}`;
      if (data.comment) {
        lastStep.detail = lastStep.detail
          ? `${lastStep.detail}; ${data.comment}`
          : data.comment;
      }
    } else {
      hermesSteps.value.push({
        phase: "note_used",
        actor: "hermes",
        message: `参考笔记: ${data.note}`,
        detail: data.comment || undefined,
        timestamp: Date.now(),
      });
    }
  },

  hermes_trace: (data) => {
    if (!data.message) return;
  },

  result: (data) => {
    console.log("SSE result:", data);

    if (data.audit_log_id) {
      currentAuditLogId.value = data.audit_log_id;
    }
    if (data.hermes_session_id) {
      hermesSessionId.value = data.hermes_session_id;
    }

    if (data.type === "sql_candidate") {
      // 启动渐进渲染
      sqlExplanation.value = data.explanation || "";
      startProgressiveRender(data.sql);
      message.success("SQL 生成成功，请确认后执行");

      // 存入历史
      messageHistory.value.push({
        role: "assistant",
        content: data.explanation || "已生成 SQL 候选语句。",
      });
      messageHistory.value = compactMessageHistoryForStorage(
        messageHistory.value,
      );
    } else if (data.type === "clarification") {
      clarification.value = data.message;
      hermesSteps.value = appendHermesClarification(
        hermesSteps.value,
        data.message,
      ) as HermesStep[];
      message.info("AI 需要您进一步澄清问题");

      // 存入历史
      messageHistory.value.push({ role: "assistant", content: data.message });
      messageHistory.value = compactMessageHistoryForStorage(
        messageHistory.value,
      );
    }
    if (data.warning) {
      message.warning(data.warning);
    }

    controller.abort();
    activeStreamController = null;
    loading.value = false;
  },

  error: (data) => {
    if (data.message) {
      message.error(data.message);
      const lastStep = hermesSteps.value[hermesSteps.value.length - 1];
      if (!(lastStep?.phase === "failed" && lastStep.message === data.message)) {
        hermesSteps.value.push({
          phase: "failed",
          actor: "hermes",
          message: data.message,
          timestamp: Date.now(),
        });
      }
    }

    hermesProcessRef.value?.stopTimer();
    controller.abort();
    activeStreamController = null;
    loading.value = false;
  },
  }, { signal: controller.signal }).catch((error) => {
    if (controller.signal.aborted) return;
    message.error(error?.message || "SSE 连接中断，请检查后端服务");
    hermesProcessRef.value?.stopTimer();
    activeStreamController = null;
    loading.value = false;
  });
};

const handleExecuteSql = async () => {
  if (!currentDatasource.value || !generatedSql.value || loading.value) return;
  loading.value = true;
  queryResult.value = null;
  hasExecutedSql.value = false;

  try {
    const data = await post("/workbench/execute", {
      datasource_id: currentDatasource.value,
      sql: generatedSql.value,
      audit_log_id: currentAuditLogId.value,
    });
    console.log("Execute result:", data);
    queryResult.value = data;
    hasExecutedSql.value = true;

    if (data.status === "success") {
      message.success(
        `查询完成，返回 ${data.row_count} 条记录 (${data.duration_ms}ms)`,
      );
    } else if (data.status === "empty") {
      message.info("查询成功，但没有返回数据");
    } else {
      message.error(data.message || "执行失败");
    }
    if (data.warning) {
      message.warning(data.warning);
    }

    // 滚动到结果区域
    setTimeout(() => {
      const el = document.querySelector(".result-container");
      if (el) el.scrollIntoView({ behavior: "smooth" });
    }, 100);
  } catch (error) {
    hasExecutedSql.value = false;
    message.error("执行请求失败");
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div class="header-content">
        <div>
          <h1 class="page-title">工作台</h1>
          <p class="page-subtitle">已支持连接测试通过的数据源直接问答。</p>
        </div>
        <div class="header-actions">
          <div class="datasource-picker">
            <span class="picker-label">当前数据源</span>
            <n-select
              v-model:value="currentDatasource"
              :options="datasourceOptions"
              placeholder="请选择数据源"
              style="width: 300px"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="page-content">
      <AiAssistant
        :disabled="loading || !currentDatasource"
        @submit="handleQuerySubmit"
      />

      <div class="workbench-grid">
        <div class="main-area">
          <!-- 澄清提示 -->
          <div v-if="clarification" class="clarification-box">
            <span class="clarification-icon">💬</span>
            <div class="clarification-content">
              <div class="clarification-title">AI 需要澄清</div>
              <div class="clarification-text">
                {{ formatClarification(clarification) }}
              </div>
            </div>
          </div>

          <div class="workbench-sections">
            <section class="panel">
              <h2 class="panel-title">SQL 候选</h2>
              <SqlEditor
                v-if="generatedSql || isRendering"
                :sql="generatedSql"
                :displayed-sql="displayedSql"
                :is-rendering="isRendering"
                :explanation="sqlExplanation"
                :validation-state="validationState"
                :validation-reasons="validationReasons"
                :executed="hasExecutedSql"
                :execution-status="queryResult?.status"
                @execute="handleExecuteSql"
              />
              <div v-else class="panel-placeholder">
                生成 SQL 后会展示候选语句与解释说明。
              </div>
            </section>

            <section class="panel">
              <h2 class="panel-title">执行结果</h2>
              <QueryResult v-if="queryResult" :result="queryResult" />
              <div v-else class="panel-placeholder">
                执行完成后，这里会展示结果表格或错误信息。
              </div>
            </section>
          </div>
        </div>

        <div class="side-area" :class="{ 'is-active': hermesSteps.length > 0 }">
          <!-- 调用追踪面板 -->
          <HermesProcess
            ref="hermesProcessRef"
            :steps="hermesSteps"
            :loading="loading"
            :history-count="messageHistory.length"
            :active-clarification="formatClarification(clarification)"
            :hermes-session-id="hermesSessionId"
            @reset="handleResetContext"
          />

          <div v-if="hermesSteps.length === 0" class="side-placeholder">
            <div class="placeholder-icon">🤖</div>
            <p>准备就绪。在这里将展示 Hermes 调用日志、参考笔记与执行结果。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 20px;
}

.datasource-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.picker-label {
  font-size: 11px;
  font-weight: 600;
  color: #8c92a0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.page-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.workbench-grid {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.main-area {
  flex: 1;
  min-width: 0; /* 防止子元素撑破容器 */
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.side-area {
  width: 400px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: sticky;
  top: 0;
}

.side-placeholder {
  padding: 40px 24px;
  border: 1px dashed #e2e8f0;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #94a3b8;
}

.placeholder-icon {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.side-placeholder p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
}

.workbench-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel {
  border: 1px solid #efeff5;
  border-radius: 12px;
  background: #fff;
  padding: 24px;
}

.panel-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
  color: #181c22;
}

.panel-placeholder {
  margin: 0;
  color: #717785;
  font-size: 14px;
}

.clarification-box {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 18px;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 1px solid #fcd34d;
  border-radius: 10px;
  font-size: 14px;
}

.clarification-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.clarification-content {
  min-width: 0;
  flex: 1;
}

.clarification-title {
  margin-bottom: 6px;
  color: #181c22;
  font-size: 15px;
  font-weight: 600;
  line-height: 20px;
}

.clarification-text {
  color: #414753;
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-line;
  word-break: break-word;
}
</style>

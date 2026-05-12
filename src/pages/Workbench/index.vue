<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  NButton,
  NCard,
  NCode,
  NEmpty,
  NInput,
  NSelect,
  NSpin,
  NTag,
  useMessage,
  NIcon,
  NScrollbar,
} from "naive-ui";
import {
  AddOutline,
  TerminalOutline,
  CopyOutline,
  PlayOutline,
  AttachOutline,
  TimeOutline,
  CodeSlashOutline,
  LayersOutline,
  FlashOutline,
  PersonOutline,
  ChatboxEllipsesOutline,
} from "@vicons/ionicons5";

import { get, streamSse } from "../../services/request";
import {
  buildWorkbenchAskStreamParams,
  formatClarification,
} from "./workbenchState";

type DataSourceOption = { label: string; value: number };
type HermesSessionItem = {
  title: string;
  preview: string;
  last_active: string;
  session_id: string;
};
type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  kind?: "text" | "sql" | "clarification";
  sql?: string;
  duration?: number;
  isThought?: boolean;
  hidden?: boolean;
  isCollapsed?: boolean; // 新增：是否折叠
  wordCount?: number; // 新增：字数统计
};

const message = useMessage();
const datasourceId = ref<number | null>(
  localStorage.getItem("fastgenerate_last_datasource_id")
    ? Number(localStorage.getItem("fastgenerate_last_datasource_id"))
    : null,
);

watch(datasourceId, (newId) => {
  if (newId !== null) {
    localStorage.setItem("fastgenerate_last_datasource_id", String(newId));
  }
});
const datasourceOptions = ref<DataSourceOption[]>([]);
const sessionItems = ref<HermesSessionItem[]>([]);
const inputValue = ref("");
const loading = ref(false);
const sessionId = ref<string | null>(null);
const sql = ref("");
const explanation = ref("");
const chatMessages = ref<ChatMessage[]>([]);
const scroller = ref<HTMLElement | null>(null);
const selectedSessionId = ref<string | null>(null);
const globalDuration = ref<number | 0>(0);
const liveTimer = ref<number>(0);
let timerInterval: any = null;

const copyToClipboard = (text: string | undefined) => {
  if (!text) return;
  navigator.clipboard
    .writeText(text)
    .then(() => {
      message.success("SQL 已成功复制到剪贴板");
    })
    .catch(() => {
      message.error("复制失败，请手动选择复制");
    });
};

const createNewSession = () => {
  sessionId.value = null;
  selectedSessionId.value = null;
  chatMessages.value = [];
  sql.value = "";
  explanation.value = "";
  inputValue.value = "";
};

const canSend = computed(() =>
  Boolean(datasourceId.value && inputValue.value.trim() && !loading.value),
);

const scrollToBottom = async () => {
  await nextTick();
  if (scroller.value) {
    scroller.value.scrollTop = scroller.value.scrollHeight;
  }
};

const pushMessage = (messageItem: ChatMessage) => {
  chatMessages.value.push(messageItem);
  void scrollToBottom();
};

const fetchDataSources = async () => {
  try {
    const data = await get<any[]>("/datasources/");
    datasourceOptions.value = data.map((item) => ({
      label: `${item.name} (${item.db_type})`,
      value: item.id,
    }));

    // 如果当前没选，且有缓存，尝试恢复
    const cachedId = localStorage.getItem("fastgenerate_last_datasource_id");
    if (!datasourceId.value && cachedId && data.length > 0) {
      const match = data.find((d) => String(d.id) === String(cachedId));
      if (match) datasourceId.value = match.id;
    }

    // 如果依然没选，默认选第一个
    if (!datasourceId.value && data.length > 0) {
      datasourceId.value = data[0].id;
    }
  } catch (error: any) {
    message.error(error.message || "加载数据源失败");
  }
};

const fetchSessions = async () => {
  try {
    const data = await get<{ items: HermesSessionItem[] }>(
      "/workbench/sessions",
    );
    sessionItems.value = data.items;
  } catch (error: any) {
    message.error(error.message || "加载 Hermes 历史失败");
  }
};

const activateSession = async (item: HermesSessionItem) => {
  selectedSessionId.value = item.session_id;
  sessionId.value = item.session_id;
  loading.value = true;
  try {
    const data = await get<{ messages: ChatMessage[] }>(
      `/workbench/sessions/${item.session_id}`,
    );
    chatMessages.value = data.messages.map((msg, index) => ({
      ...msg,
      id: `hist-${item.session_id}-${index}`,
    }));
    if (chatMessages.value.length === 0) {
      chatMessages.value.push({
        id: `session-${item.session_id}`,
        role: "system",
        content: `已继续 Hermes 会话：${item.title || item.preview}\n最近活动：${item.last_active}`,
        kind: "text",
      });
    }
    void scrollToBottom();
  } catch (error: any) {
    message.error(error.message || "加载会话详情失败");
  } finally {
    loading.value = false;
  }
  sql.value = "";
  explanation.value = "";
};

const handleSend = async () => {
  if (!canSend.value || !datasourceId.value) return;

  const question = inputValue.value.trim();
  inputValue.value = "";
  loading.value = true;
  const startTime = Date.now();
  globalDuration.value = 0;
  liveTimer.value = 0;

  // 开启实时计时器
  timerInterval = setInterval(() => {
    liveTimer.value = Date.now() - startTime;
  }, 100);
  pushMessage({
    id: `user-${Date.now()}`,
    role: "user",
    content: question,
    kind: "text",
  });

  const history = chatMessages.value
    .filter((item) => item.role === "user" || item.role === "assistant")
    .map((item) => ({
      role:
        item.role === "assistant" ? ("assistant" as const) : ("user" as const),
      content: item.content,
    }));

  const params = buildWorkbenchAskStreamParams({
    datasourceId: datasourceId.value,
    question,
    history,
    hermesSessionId: sessionId.value,
  });

  try {
    await streamSse(`/workbench/ask_stream?${params.toString()}`, {
      session_id: (data) => {
        // 后端一旦分配 ID 立即更新
        if (data.session_id) {
          sessionId.value = data.session_id;
          selectedSessionId.value = data.session_id;
        }
      },
      hermes_trace: (data) => {
        // 同时支持在 trace 中携带 session_id (双重保险)
        if (data.session_id && !sessionId.value) {
          sessionId.value = data.session_id;
          selectedSessionId.value = data.session_id;
        }
        const lastMsg = chatMessages.value[chatMessages.value.length - 1];
        const isThinkingLine =
          data.message.includes("[thinking]") ||
          data.message.includes("AI Agent initialized");

        if (
          lastMsg &&
          lastMsg.role === "assistant" &&
          (lastMsg.isThought || lastMsg.id.startsWith("trace-"))
        ) {
          lastMsg.content += (lastMsg.content ? "\n" : "") + data.message;
          lastMsg.isThought = true;
          lastMsg.wordCount = lastMsg.content.length; // 统计字数
        } else {
          pushMessage({
            id: `trace-${Date.now()}`,
            role: "assistant",
            content: data.message,
            kind: "text",
            isThought: true,
            wordCount: data.message.length,
          });
        }
      },
      note_used: (data) => {
        const lastMsg = chatMessages.value[chatMessages.value.length - 1];
        if (lastMsg && lastMsg.isThought) {
          lastMsg.content += `\n💡 召回知识: ${data.note}`;
        } else {
          pushMessage({
            id: `note-${Date.now()}`,
            role: "assistant",
            content: `💡 召回知识: ${data.note}`,
            isThought: true,
          });
        }
      },
      result: (data) => {
        // 1. 结果返回，停止计时
        if (timerInterval) clearInterval(timerInterval);
        loading.value = false;

        // 2. 核心：将之前的推理过程设为“已折叠”
        chatMessages.value.forEach((m) => {
          if (m.isThought) {
            m.isCollapsed = true;
          }
        });

        // 3. 更新 Session ID
        if (data.session_id) {
          sessionId.value = data.session_id;
          selectedSessionId.value = data.session_id;
        } else if (data.hermes_session_id) {
          sessionId.value = data.hermes_session_id;
          selectedSessionId.value = data.hermes_session_id;
        }

        const duration = Date.now() - startTime;
        globalDuration.value = duration;

        if (data.type === "sql_candidate") {
          sql.value = data.sql || "";
          explanation.value = data.explanation || "";
          pushMessage({
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: data.explanation || "已生成 SQL",
            kind: "sql",
            sql: data.sql || "",
            duration,
          });
        } else if (data.type === "clarification") {
          pushMessage({
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: formatClarification(data.message || "需要进一步澄清"),
            kind: "clarification",
            duration,
          });
        }
      },
      error: (data) => {
        pushMessage({
          id: `error-${Date.now()}`,
          role: "system",
          content: data.message || "请求失败",
          kind: "text",
        });
      },
    });
  } catch (error: any) {
    message.error(error.message || "会话请求失败");
  } finally {
    loading.value = false;
    // 关闭实时计时器
    if (timerInterval) clearInterval(timerInterval);
    void fetchSessions();
  }
};

onMounted(() => {
  void fetchDataSources();
  void fetchSessions();
});
</script>

<template>
  <div class="workbench-page">
    <!-- <aside class="sidebar">
      <div class="sidebar-header">
        <div class="brand-row">
          <div class="brand-tag">HERMES Q&A</div>
          <n-button
            quaternary
            circle
            size="small"
            class="new-chat-btn"
            @click="createNewSession"
          >
            <template #icon>
              <n-icon><AddOutline /></n-icon>
            </template>
          </n-button>
        </div>
        <h3 class="sidebar-title">会话历史</h3>
      </div>
      
      <n-scrollbar class="sidebar-scroll">
        <div class="history-list">
          <div
            v-for="item in sessionItems"
            :key="item.session_id"
            class="history-item"
            :class="{ active: selectedSessionId === item.session_id }"
            @click="activateSession(item)"
          >
            <div class="history-item-icon">
              <n-icon><CodeSlashOutline /></n-icon>
            </div>
            <div class="history-item-content">
              <div class="history-item-title">{{ item.title || "未命名会话" }}</div>
              <div class="history-item-meta">{{ item.last_active }}</div>
            </div>
          </div>
        </div>
      </n-scrollbar>
    </aside> -->

    <main class="main-content">
      <header class="content-header">
        <div class="header-left">
          <n-select
            v-model:value="datasourceId"
            :options="datasourceOptions"
            placeholder="请选择数据源"
            class="datasource-select"
            size="medium"
          />
        </div>
        <div class="header-right">
          <div
            v-if="loading || globalDuration"
            class="status-chip duration"
            :class="{ 'is-loading': loading }"
          >
            <n-icon><TimeOutline /></n-icon>
            <span>{{
              loading
                ? (liveTimer / 1000).toFixed(1) + "s"
                : globalDuration + "ms"
            }}</span>
          </div>

          <div class="status-chip session">
            <n-icon><ChatboxEllipsesOutline /></n-icon>
            <span>ID: {{ sessionId || "NEW" }}</span>
          </div>

          <div v-if="loading" class="status-chip loading">
            <n-spin size="small" />
            <span>THINKING...</span>
          </div>
        </div>
      </header>

      <div class="chat-container" ref="scroller">
        <div class="message-list">
          <div v-if="chatMessages.length === 0" class="empty-state">
            <div class="empty-icon">
              <n-icon><FlashOutline /></n-icon>
            </div>
            <h2>开始您的 SQL 探索</h2>
            <p>选择数据源并提问，Hermes 将基于 Wiki 知识库为您生成专业 SQL。</p>
          </div>

          <div
            v-for="item in chatMessages"
            :key="item.id"
            v-show="!item.hidden"
            class="message-wrapper"
            :class="item.role"
          >
            <!-- User Message -->
            <div v-if="item.role === 'user'" class="message user">
              <div class="user-content">
                <div class="user-name">User</div>
                <div class="bubble user">
                  {{ item.content }}
                </div>
                <div class="message-meta">
                  {{
                    new Date().toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }}
                </div>
              </div>
              <div class="user-avatar">
                <n-icon><PersonOutline /></n-icon>
              </div>
            </div>

            <!-- Assistant Message -->
            <div
              v-else-if="item.role === 'assistant'"
              class="message assistant"
            >
              <div class="assistant-avatar">
                <n-icon><TerminalOutline /></n-icon>
              </div>
              <div class="assistant-content">
                <div class="assistant-name">SQL Assistant</div>
                <!-- Professional Thought block -->
                <details
                  v-if="item.isThought"
                  class="thought-details"
                  :open="!item.isCollapsed"
                >
                  <summary class="thought-summary">
                    <div class="thought-summary-left">
                      <n-icon class="thought-icon"><FlashOutline /></n-icon>
                      <span class="thought-label">思考过程</span>
                      <span v-if="item.wordCount" class="thought-word-count">
                        · {{ item.wordCount }} 字
                      </span>
                    </div>
                  </summary>
                  <div class="thought-content-box">
                    {{ item.content }}
                  </div>
                </details>

                <!-- Text / Explanation -->
                <div
                  v-if="!item.isThought && item.kind !== 'sql'"
                  class="bubble assistant"
                >
                  {{ item.content }}
                </div>

                <!-- SQL Card (Light Theme) -->
                <div v-if="item.kind === 'sql'" class="sql-card light-theme">
                  <div class="sql-card-header">
                    <span class="sql-card-title">GENERATED SQL</span>
                    <n-button
                      quaternary
                      size="tiny"
                      class="copy-btn"
                      @click="copyToClipboard(item.sql)"
                    >
                      <template #icon>
                        <n-icon><CopyOutline /></n-icon>
                      </template>
                      Copy Code
                    </n-button>
                  </div>
                  <div
                    class="sql-code-wrapper"
                    style="padding: 0px 10px !important"
                  >
                    <n-code :code="item.sql || ''" language="sql" word-wrap />
                  </div>
                  <div class="sql-card-footer">
                    <div class="explanation-text">{{ item.content }}</div>
                    <div class="result-preview-bar">
                      <span class="preview-label">RESULT PREVIEW</span>
                      <div class="preview-status">
                        <span class="status-tag success">SUCCESS</span>
                        <span class="duration-tag">{{ item.duration }}ms</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- System Message -->
            <div v-else-if="item.role === 'system'" class="message system">
              <div class="system-bubble">
                {{ item.content }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <footer class="composer-area">
        <div class="composer-container">
          <div class="composer-card">
            <textarea
              v-model="inputValue"
              class="composer-textarea"
              placeholder="输入您的业务需求或 SQL 片段... (Enter 发送)"
              :disabled="!datasourceId || loading"
              @keydown.enter.exact.prevent="handleSend"
            ></textarea>

            <div class="composer-actions">
              <div class="action-group">
                <n-button
                  type="primary"
                  class="run-btn"
                  :disabled="!canSend"
                  :loading="loading"
                  @click="handleSend"
                >
                  <span>Run Query</span>
                  <template #icon>
                    <n-icon><PlayOutline /></n-icon>
                  </template>
                </n-button>
              </div>
            </div>
          </div>
          <div class="composer-footer">
            <p>
              Connected to <span>production_read_only</span>. Use natural
              language to query your data.
            </p>
          </div>
        </div>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.workbench-page {
  height: 100%;
  display: flex;
  background: #faf8ff;
  color: #131b2e;
  font-family: "Inter", sans-serif;
  overflow: hidden;
}

.sidebar {
  width: 280px;
  background: #1e293b;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #334155;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 24px 16px;
  border-bottom: 1px solid #334155;
}

.brand-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.brand-tag {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #94a3b8;
  text-transform: uppercase;
}

.new-chat-btn {
  color: #94a3b8 !important;
}
.new-chat-btn:hover {
  background: rgba(255, 255, 255, 0.1) !important;
  color: #fff !important;
}

.sidebar-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #f8fafc;
}

.sidebar-scroll {
  flex: 1;
}

.history-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.history-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.history-item.active {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
}

.history-item-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  flex-shrink: 0;
}

.history-item.active .history-item-icon {
  background: #6366f1;
  color: #fff;
}

.history-item-content {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-meta {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

.content-header {
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  z-index: 10;
}

.datasource-select {
  width: 280px;
}

:deep(.n-base-selection-label) {
  color: #1e293b !important;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  border-radius: 999px;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.status-chip.duration.is-loading {
  background: #fffbeb;
  color: #d97706;
  border-color: #fde68a;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
  100% {
    opacity: 1;
  }
}

.chip-label {
  color: #64748b;
}

.chip-value {
  font-weight: 700;
  color: #0058be;
}

.ready-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.message-list {
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px 300px; /* 大幅增加底部间距 */
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  text-align: center;
  color: #64748b;
}

.empty-icon {
  font-size: 48px;
  color: #e2e8f0;
  margin-bottom: 16px;
}

.empty-state h2 {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 8px;
}

.message-wrapper {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.message.user {
  display: flex;
  flex-direction: row;
  justify-content: flex-end;
  gap: 12px;
}

.user-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  max-width: 80%;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 4px;
}

.user-avatar {
  width: 36px;
  height: 36px;
  background: #3b82f6;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.user-avatar .n-icon {
  font-size: 22px;
}

.bubble.user {
  background: #3b82f6;
  color: #fff;
  padding: 12px 18px;
  border-radius: 16px 16px 4px 16px;
  font-size: 15px;
  line-height: 1.5;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.message-meta {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  font-family: "JetBrains Mono", monospace;
}

.message.assistant {
  display: flex;
  flex-direction: row;
  gap: 16px;
}

.assistant-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #4648d4;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.assistant-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 90%;
}

.assistant-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}

.bubble.assistant {
  background: #fff;
  border: 1px solid #e2e8f0;
  padding: 12px 18px;
  border-radius: 4px 16px 16px 16px;
  font-size: 15px;
  line-height: 1.6;
  color: #334155;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
}

.thought-details {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.thought-summary {
  list-style: none;
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  user-select: none;
}

.thought-summary::-webkit-details-marker {
  display: none;
}

.thought-summary-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.thought-icon {
  font-size: 14px;
  color: #f59e0b;
}

.thought-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.thought-word-count {
  font-size: 12px;
  color: #94a3b8;
}

.thought-content-box {
  padding: 0 12px 12px 34px;
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
  white-space: pre-wrap;
  border-top: 1px dashed transparent; /* 展开时可以变色 */
  max-height: 350px;
  overflow-y: auto;
}

.thought-details[open] {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.thought-details[open] .thought-content-box {
  border-top-color: #e2e8f0;
  margin-top: 4px;
  padding-top: 12px;
}

.sql-card.light-theme {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  margin-top: 12px;
  display: flex;
  flex-direction: column;
}

.sql-card-header {
  padding: 12px 18px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top-left-radius: 11px; /* 补齐圆角，防止左上角空缺 */
  border-top-right-radius: 11px;
}

.sql-card-title {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.copy-btn {
  color: #3b82f6 !important;
  font-weight: 600;
}

.sql-code-wrapper {
  background: #ffffff;
  max-height: 400px;
  overflow-y: auto;
  border-bottom: 1px solid #f1f5f9;
}

:deep(.n-code) {
  padding: 16px 10px !important; /* 上下 16px，左右 10px */
  background-color: #ffffff !important;
  font-size: 14px !important;
}

:deep(.n-code pre) {
  margin: 0 !important;
  color: #1e293b !important;
}

:deep(.n-code pre) {
  font-family: "JetBrains Mono", monospace !important;
  font-size: 13px !important;
  line-height: 1.5 !important;
}

.sql-card-footer {
  padding: 16px;
  background: #fff;
}

.explanation-text {
  font-size: 14px;
  color: #475569;
  line-height: 1.6;
  margin-bottom: 16px;
}

.result-preview-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px dashed #e2e8f0;
}

.preview-label {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
}

.preview-status {
  display: flex;
  gap: 8px;
}

.status-tag {
  font-size: 10px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
}

.status-tag.success {
  background: #ecfdf5;
  color: #059669;
}

.duration-tag {
  font-size: 11px;
  font-family: "JetBrains Mono", monospace;
  color: #64748b;
}

/* System Message */
.message.system {
  align-items: center;
  margin: 16px 0;
}

.system-bubble {
  font-size: 12px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 4px 16px;
  border-radius: 999px;
}

/* Composer Styling */
.composer-area {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 24px;
  background: linear-gradient(transparent, #faf8ff 40%);
  pointer-events: none; /* Let clicks pass through to scroll area underneath if not in container */
}

.composer-container {
  max-width: 1000px;
  margin: 0 auto;
  pointer-events: auto;
}

.composer-card {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.composer-card:focus-within {
  background: #fff;
  border-color: #0058be;
  box-shadow: 0 20px 50px rgba(0, 88, 190, 0.12);
  transform: translateY(-2px);
}

.composer-textarea {
  width: 100%;
  border: none;
  background: transparent;
  padding: 16px;
  font-family: "JetBrains Mono", monospace;
  font-size: 14px;
  color: #1e293b;
  min-height: 80px;
  max-height: 300px;
  resize: none;
}

.composer-textarea:focus {
  outline: none;
}

.composer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: rgba(248, 250, 252, 0.8);
  border-top: 1px solid rgba(226, 232, 240, 0.5);
}

.action-group {
  display: flex;
  gap: 16px;
  align-items: center;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 0;
  transition: color 0.2s;
}

.action-btn:hover {
  color: #0058be;
}

.run-btn {
  height: 40px !important;
  font-weight: 700 !important;
  padding: 0 20px !important;
  border-radius: 8px !important;
}

.composer-footer {
  margin-top: 12px;
  text-align: center;
}

.composer-footer p {
  font-size: 12px;
  color: #94a3b8;
}

.composer-footer span {
  color: #64748b;
  font-weight: 700;
}

/* Animations */
.message-wrapper {
  animation: slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes slide-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Scrollbar Styling */
:deep(.n-scrollbar-rail) {
  width: 6px !important;
}
:deep(.n-scrollbar-thumb) {
  background-color: #cbd5e1 !important;
}
:deep(.n-scrollbar-thumb:hover) {
  background-color: #94a3b8 !important;
}
</style>

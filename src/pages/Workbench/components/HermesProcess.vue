<script setup lang="ts">
import { computed, ref, onUnmounted } from "vue";

export interface HermesStep {
  phase: string;
  message: string;
  detail?: string;
  timestamp: number;
}

const props = defineProps<{
  steps: HermesStep[];
  loading: boolean;
  historyCount: number;
}>();

defineEmits(["reset"]);

// 计时器
const elapsed = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

const startTimer = () => {
  elapsed.value = 0;
  timer = setInterval(() => {
    elapsed.value++;
  }, 1000);
};

const stopTimer = () => {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
};

// 根据 loading 状态自动启停计时器
const startWatching = () => {
  if (props.loading && !timer) startTimer();
};

defineExpose({ startTimer, stopTimer });

onUnmounted(() => stopTimer());

const phaseIcon = (phase: string) => {
  const map: Record<string, string> = {
    started: "🚀",
    searching_notes: "🔍",
    note_hit: "📄",
    calling_hermes: "🤖",
    generating_sql: "⏳",
    completed: "✅",
    failed: "❌",
  };
  return map[phase] || "•";
};

const phaseClass = (phase: string) => {
  if (phase === "completed") return "step-success";
  if (phase === "failed") return "step-error";
  return "";
};

const formattedElapsed = computed(() => {
  const m = Math.floor(elapsed.value / 60);
  const s = elapsed.value % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
});

const isActive = computed(() => props.steps.length > 0);
</script>

<template>
  <div v-if="isActive" class="hermes-process">
    <div class="process-header">
      <div class="process-title">
        <span class="title-icon">⚡</span>
        <span>Hermes Process</span>
      </div>
      <div class="process-actions">
        <div v-if="historyCount > 0" class="context-pill">
          <span class="round-count"
            >第 {{ Math.ceil(historyCount / 2) }} 轮对话</span
          >
          <i class="pill-divider"></i>
          <button class="clear-action" @click="$emit('reset')">清除历史</button>
        </div>
        <div class="process-timer">
          <span v-if="loading" class="timer-pulse"></span>
          <span class="timer-text">{{ formattedElapsed }}</span>
        </div>
      </div>
    </div>

    <div class="process-timeline">
      <TransitionGroup name="step-enter">
        <div
          v-for="(step, idx) in steps"
          :key="idx"
          class="timeline-step"
          :class="[
            phaseClass(step.phase),
            { 'is-last': idx === steps.length - 1 && loading },
          ]"
        >
          <div class="step-connector">
            <span class="step-dot" :class="phaseClass(step.phase)">
              {{ phaseIcon(step.phase) }}
            </span>
            <div
              v-if="idx < steps.length - 1 || loading"
              class="step-line"
            ></div>
          </div>
          <div
            class="step-content"
            :class="{ 'is-note-hit': step.phase === 'note_hit' }"
          >
            <span class="step-message">{{ step.message }}</span>
            <span v-if="step.detail" class="step-detail">{{
              step.detail
            }}</span>
          </div>
        </div>
      </TransitionGroup>

      <!-- loading spinner for the current active step -->
      <div v-if="loading" class="timeline-step is-loading">
        <div class="step-connector">
          <span class="step-dot step-spinner">
            <span class="spinner"></span>
          </span>
        </div>
        <div class="step-content">
          <span class="step-message step-message-loading">处理中...</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hermes-process {
  border: 1px solid #e8e5f0;
  border-radius: 12px;
  background: linear-gradient(135deg, #fafafe 0%, #f5f3ff 100%);
  overflow: hidden;
}

.process-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: linear-gradient(90deg, #f0ecff 0%, #e8f0ff 100%);
  border-bottom: 1px solid #e8e5f0;
}

.process-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #3b2e8a;
}

.title-icon {
  font-size: 16px;
}

.process-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.context-pill {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(107, 95, 191, 0.15);
  border-radius: 20px;
  padding: 4px 14px;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(107, 95, 191, 0.04);
}

.round-count {
  font-size: 12px;
  font-weight: 500;
  color: #5c53a3;
  white-space: nowrap;
}

.pill-divider {
  width: 1px;
  height: 12px;
  background: rgba(107, 95, 191, 0.2);
}

.clear-action {
  background: transparent;
  border: none;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: #8c8ab0;
  cursor: pointer;
  transition: all 0.2s;
  outline: none;
}

.clear-action:hover {
  color: #ef4444;
}

.process-timer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b5fbf;
  font-variant-numeric: tabular-nums;
}

.timer-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6b5fbf;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.4;
    transform: scale(0.8);
  }
}

.timer-text {
  font-family: "JetBrains Mono", "SF Mono", monospace;
  font-weight: 500;
}

.process-timeline {
  padding: 16px 20px 20px;
}

.timeline-step {
  display: flex;
  gap: 12px;
  min-height: 32px;
}

.step-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}

.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  background: #fff;
  border: 2px solid #e0ddf0;
  flex-shrink: 0;
  z-index: 1;
}

.step-dot.step-success {
  border-color: #22c55e;
  background: #f0fdf4;
}

.step-dot.step-error {
  border-color: #ef4444;
  background: #fef2f2;
}

.step-line {
  width: 2px;
  flex: 1;
  min-height: 8px;
  background: linear-gradient(180deg, #d4d0ef 0%, #e8e5f0 100%);
  margin: 2px 0;
}

.step-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 4px 0 12px;
  gap: 2px;
  min-width: 0;
}

.step-content.is-note-hit {
  flex-direction: row;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.step-message {
  font-size: 13px;
  font-weight: 500;
  color: #2d2b3d;
  line-height: 20px;
}

.step-message-loading {
  color: #8c8ab0;
  font-weight: 400;
}

.step-detail {
  font-size: 12px;
  color: #8c8ab0;
  line-height: 16px;
}

.step-content.is-note-hit .step-detail {
  line-height: 20px;
}

.step-spinner {
  border-color: #c4bfef;
  background: #f5f3ff;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #d4d0ef;
  border-top-color: #6b5fbf;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* TransitionGroup animations */
.step-enter-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.step-enter-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.step-enter-enter-to {
  opacity: 1;
  transform: translateY(0);
}
</style>

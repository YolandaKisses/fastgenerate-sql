<script setup lang="ts">
import { computed, ref, onUnmounted } from "vue";
import { groupHermesProcessRounds } from "../workbenchState";

export interface HermesStep {
  phase: string;
  message: string;
  detail?: string;
  actor?: "user" | "system" | "hermes";
  timestamp: number;
}

const props = defineProps<{
  steps: HermesStep[];
  loading: boolean;
  historyCount: number;
  activeClarification?: string;
  hermesSessionId?: string | null;
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
    user_question: "👤",
    started: "🚀",
    retrieving_schema: "🗂️",
    note_used: "📚",
    rule_used: "📋",
    clarification: "💬",
    calling_hermes: "🤖",
    hermes_trace: "🔎",
    completed: "✅",
    failed: "❌",
  };
  return map[phase] || "•";
};

const stepActor = (step: HermesStep) => {
  if (step.actor) return step.actor;
  return step.phase === "user_question" ? "user" : "hermes";
};

const isUserStep = (step: HermesStep) => stepActor(step) === "user";

const actorLabel = (step: HermesStep) => {
  if (isUserStep(step)) return "我";
  return stepActor(step) === "system" ? "系统" : "Hermes";
};

const actorClass = (step: HermesStep) => {
  if (stepActor(step) === "system") return "actor-system";
  return isUserStep(step) ? "actor-user" : "actor-hermes";
};

const dotActorClass = (step: HermesStep) => {
  if (stepActor(step) === "system") return "dot-system";
  return isUserStep(step) ? "dot-user" : "dot-hermes";
};

const shouldShowLine = (
  roundSteps: HermesStep[],
  idx: number,
  isLatestRound: boolean,
) => {
  const step = roundSteps[idx];
  const nextStep = roundSteps[idx + 1];
  if (!step || isUserStep(step)) return false;
  if (nextStep && isUserStep(nextStep)) return false;
  return idx < roundSteps.length - 1 || (isLatestRound && props.loading);
};

const detailLines = (detail: string) => {
  return detail.split("\n").filter((line) => line.trim().length > 0);
};

const stepDetailLines = (step: HermesStep) => {
  return step.detail ? detailLines(step.detail) : [];
};

const shouldShowDetail = (step: HermesStep) => {
  if (!step.detail) return false;
  const isLastStep = props.steps[props.steps.length - 1] === step;
  const isActiveClarification =
    step.phase === "clarification" &&
    isLastStep &&
    step.detail === props.activeClarification;
  return !isActiveClarification;
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

const roundCount = computed(() => Math.ceil(props.historyCount / 2));

const processRounds = computed(() => groupHermesProcessRounds(props.steps));

const expandedRoundKeys = ref<Set<string>>(new Set());

const isLatestRound = (roundIdx: number) =>
  roundIdx === processRounds.value.length - 1;

const isRoundExpanded = (roundKey: string, roundIdx: number) =>
  isLatestRound(roundIdx) || expandedRoundKeys.value.has(roundKey);

const toggleRound = (roundKey: string, roundIdx: number) => {
  if (isLatestRound(roundIdx)) return;
  const nextExpanded = new Set(expandedRoundKeys.value);
  if (nextExpanded.has(roundKey)) {
    nextExpanded.delete(roundKey);
  } else {
    nextExpanded.add(roundKey);
  }
  expandedRoundKeys.value = nextExpanded;
};

const roundStatusText = (roundSteps: HermesStep[]) => {
  const lastStep = roundSteps[roundSteps.length - 1];
  if (!lastStep) return "无记录";
  if (lastStep.phase === "completed") return lastStep.message || "已完成";
  if (lastStep.phase === "failed") return lastStep.message || "失败";
  if (lastStep.phase === "clarification") return "需要澄清";
  return lastStep.message;
};

const shortSessionId = computed(() => {
  if (!props.hermesSessionId) return "未建立";
  return props.hermesSessionId.length > 12
    ? `${props.hermesSessionId.slice(0, 6)}…${props.hermesSessionId.slice(-4)}`
    : props.hermesSessionId;
});
</script>

<template>
  <div v-if="isActive" class="hermes-process">
    <div class="process-header">
      <div class="process-title">
        <div class="title-svg-icon">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M13 2L3 14H12L11 22L21 10H12L13 2Z"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
        <span>调用追踪</span>
      </div>
      <div class="process-actions">
        <div v-if="historyCount > 0" class="context-pill">
          <!-- <span class="round-count">第 {{ roundCount }} 轮对话</span> -->
          <!-- <i class="pill-divider"></i> -->
          <button class="clear-action" @click="$emit('reset')">清除历史</button>
        </div>
        <div class="session-meta">
          <span
            class="meta-item"
            :title="hermesSessionId || 'Hermes session 尚未建立'"
          >
            {{ shortSessionId }}
          </span>
        </div>
        <div class="process-timer">
          <span v-if="loading" class="timer-pulse"></span>
          <span class="timer-text">{{ formattedElapsed }}</span>
        </div>
      </div>
    </div>

    <div class="process-timeline">
      <template v-for="(round, roundIdx) in processRounds" :key="round.key">
        <button
          v-if="!isRoundExpanded(round.key, roundIdx)"
          type="button"
          class="round-summary"
          @click="toggleRound(round.key, roundIdx)"
        >
          <span class="round-summary-title">第 {{ round.index }} 轮</span>
          <span class="round-summary-question">{{ round.question }}</span>
          <span class="round-summary-meta">
            {{ roundStatusText(round.steps) }} · {{ round.steps.length }} 条记录
          </span>
        </button>

        <div v-else class="round-expanded">
          <button
            v-if="!isLatestRound(roundIdx)"
            type="button"
            class="round-summary round-summary-expanded"
            @click="toggleRound(round.key, roundIdx)"
          >
            <span class="round-summary-title">第 {{ round.index }} 轮</span>
            <span class="round-summary-question">{{ round.question }}</span>
            <span class="round-summary-meta">收起</span>
          </button>

          <TransitionGroup name="step-enter" class="round-steps" tag="div">
            <div
              v-for="(step, idx) in round.steps"
              :key="`${round.key}-${idx}`"
              class="timeline-step"
              :class="[
                phaseClass(step.phase),
                { 'is-user-step': isUserStep(step) },
                {
                  'is-last':
                    idx === round.steps.length - 1 &&
                    loading &&
                    isLatestRound(roundIdx),
                },
              ]"
            >
              <div class="step-connector">
                <span
                  class="step-dot"
                  :class="[phaseClass(step.phase), dotActorClass(step)]"
                >
                  {{ phaseIcon(step.phase) }}
                </span>
                <div
                  v-if="
                    shouldShowLine(round.steps, idx, isLatestRound(roundIdx))
                  "
                  class="step-line"
                ></div>
              </div>
              <div
                class="step-content"
              >
                <div class="step-main">
                  <span class="actor-badge" :class="actorClass(step)">
                    <span class="badge-icon">
                      <svg
                        v-if="isUserStep(step)"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.5"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path
                          d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"
                        ></path>
                        <circle cx="12" cy="7" r="4"></circle>
                      </svg>
                      <svg
                        v-else-if="stepActor(step) === 'system'"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.5"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <circle cx="11" cy="11" r="7"></circle>
                        <path d="M20 20l-4-4"></path>
                      </svg>
                      <svg
                        v-else
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.5"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <rect x="3" y="11" width="18" height="10" rx="2"></rect>
                        <circle cx="12" cy="5" r="2"></circle>
                        <path d="M12 7v4"></path>
                      </svg>
                    </span>
                    {{ actorLabel(step) }}
                  </span>
                  <span class="step-message">{{ step.message }}</span>
                </div>
                <span v-if="shouldShowDetail(step)" class="step-detail">
                  <span
                    v-for="(line, lineIdx) in stepDetailLines(step)"
                    :key="lineIdx"
                    class="step-detail-line"
                  >
                    {{ line }}
                  </span>
                </span>
              </div>
            </div>
          </TransitionGroup>
        </div>
      </template>

      <!-- loading spinner for the current active step -->
      <div v-if="loading" class="timeline-step is-loading">
        <div class="step-connector">
          <span class="step-dot step-spinner">
            <span class="spinner"></span>
          </span>
        </div>
        <div class="step-content">
          <div class="step-main">
            <span class="actor-badge actor-hermes">
              <span class="badge-icon pulse-icon">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect x="3" y="11" width="18" height="10" rx="2"></rect>
                  <circle cx="12" cy="5" r="2"></circle>
                  <path d="M12 7v4"></path>
                </svg>
              </span>
              Hermes
            </span>
            <span class="step-message step-message-loading">处理中...</span>
          </div>
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
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 20px;
  background: linear-gradient(90deg, #f0ecff 0%, #e8f0ff 100%);
  border-bottom: 1px solid #e8e5f0;
}

.process-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #3b2e8a;
  flex-shrink: 0;
  white-space: nowrap;
}

.title-svg-icon {
  width: 18px;
  height: 18px;
  color: #6b5fbf;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: svg-pulse 2s ease-in-out infinite;
}

@keyframes svg-pulse {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
    filter: drop-shadow(0 0 4px rgba(107, 95, 191, 0.4));
  }
  100% {
    transform: scale(1);
    opacity: 0.8;
  }
}

.process-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
  min-width: 0;
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

.session-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 10px;
  border: 1px solid rgba(107, 95, 191, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.36);
  color: #6b5fbf;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
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

.round-summary {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 34px;
  margin: 0 0 10px;
  padding: 6px 10px;
  border: 1px solid #ded9fb;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.62);
  color: #5c53a3;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.2s,
    background 0.2s,
    box-shadow 0.2s;
}

.round-summary:hover {
  border-color: #c4bfef;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(107, 95, 191, 0.08);
}

.round-summary-expanded {
  margin-bottom: 12px;
  background: rgba(241, 239, 255, 0.72);
}

.round-summary-title,
.round-summary-meta {
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.round-summary-question {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #2d2b3d;
  font-size: 13px;
  font-weight: 600;
}

.round-summary-meta {
  color: #8c8ab0;
  font-weight: 600;
}

.round-steps + .round-summary {
  margin-top: 4px;
}

.timeline-step {
  display: flex;
  gap: 12px;
  min-height: 32px;
}

.timeline-step.is-user-step {
  justify-content: flex-end;
  margin-top: 8px;
  margin-bottom: 12px;
}

.timeline-step.is-user-step .step-connector {
  display: none;
}

.timeline-step.is-user-step .step-content {
  align-items: flex-end;
  padding: 4px 0;
}

.timeline-step.is-user-step .step-main {
  flex-direction: row-reverse;
  gap: 10px;
}

/* 统一样式：去掉背景、边框和阴影，仅保留纯净文字和 Badge */
.timeline-step.is-user-step .step-main,
.timeline-step .step-main {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
}

.timeline-step.is-user-step .step-message {
  text-align: right;
  color: #174ea6; /* 用户文字用深蓝色区分，但保持无气泡 */
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

.step-dot.dot-user {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.step-dot.dot-hermes {
  border-color: #dcd8ff;
}

.step-dot.dot-system {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.actor-user + .step-message {
  color: #174ea6;
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

.step-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.actor-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  gap: 6px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 22px;
  white-space: nowrap;
  flex-shrink: 0;
}

.badge-icon {
  width: 12px;
  height: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pulse-icon {
  animation: svg-pulse 1.5s ease-in-out infinite;
}

.actor-user {
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.actor-hermes {
  color: #5c53a3;
  background: #f1efff;
  border: 1px solid #dcd8ff;
}

.actor-system {
  color: #475569;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
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
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
  color: #8c8ab0;
  line-height: 16px;
  margin-top: 5px;
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

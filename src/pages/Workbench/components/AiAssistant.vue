<script setup lang="ts">
import { ref } from "vue";
import { NText, NInput, NButton, NIcon } from "naive-ui";
import { ChatbubbleOutline, ArrowForwardOutline } from "@vicons/ionicons5";

const props = defineProps<{
  disabled?: boolean;
}>();

const emit = defineEmits(["submit"]);
const query = ref("");

const handleGenerate = (e?: KeyboardEvent) => {
  // 检查是否在输入法合成过程中
  if (e?.isComposing) return;

  if (query.value.trim() && !props.disabled) {
    emit("submit", query.value);
    query.value = "";
  }
};
</script>

<template>
  <div class="ai-assistant">
    <div style="margin-bottom: 16px">
      <n-text style="font-size: 20px; font-weight: 600; color: #181c22"
        >AI 查询助手</n-text
      >
      <div class="assistant-hint">常见澄清场景将优先提示，不会直接猜测。</div>
    </div>

    <div class="input-wrapper">
      <n-input
        v-model:value="query"
        size="large"
        placeholder="描述您想查询的数据，例如：'按城市统计用户数量'"
        :disabled="disabled"
        @keydown.enter="handleGenerate"
        class="custom-n-input"
      >
        <template #prefix>
          <n-icon :component="ChatbubbleOutline" color="#2080f0" />
        </template>
        <template #suffix>
          <n-button
            type="primary"
            :disabled="disabled || !query.trim()"
            @click="handleGenerate"
            size="medium"
          >
            生成 SQL
            <template #icon>
              <n-icon :component="ArrowForwardOutline" />
            </template>
          </n-button>
        </template>
      </n-input>
    </div>
  </div>
</template>

<style scoped>
.ai-assistant {
  display: flex;
  flex-direction: column;
}

.assistant-hint {
  font-size: 13px;
  color: #717785;
  margin-top: 8px;
}

.input-wrapper {
  position: relative;
}

::v-deep(.custom-n-input .n-input__input-el) {
  height: 54px;
}

::v-deep(.custom-n-input .n-input-wrapper) {
  padding-right: 4px;
}
</style>

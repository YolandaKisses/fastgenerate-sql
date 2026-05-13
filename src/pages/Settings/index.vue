<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  NCard,
  NForm,
  NFormItem,
  NInput,
  NButton,
  NSpace,
  NTag,
  useMessage,
} from "naive-ui";
import {
  CheckmarkCircleOutline,
  CloseCircleOutline,
  BuildOutline,
  FolderOpenOutline,
  RefreshOutline,
} from "@vicons/ionicons5";
import { NIcon } from "naive-ui";
import { get, post } from "../../services/request";

const message = useMessage();

const hermesPath = ref("");
const hermesDefault = ref("");
const hermesStatus = ref<"idle" | "testing" | "success" | "error">("idle");
const hermesMessage = ref("");

const wikiRoot = ref("");
const wikiDefault = ref("");

const fetchSettings = async () => {
  try {
    const data = await get("/settings/");
    hermesPath.value =
      data.hermes_cli_path.value || data.hermes_cli_path.default;
    hermesDefault.value = data.hermes_cli_path.default;
    wikiRoot.value = data.wiki_root.value || data.wiki_root.default;
    wikiDefault.value = data.wiki_root.default;
  } catch (e) {
    message.error("获取设置失败");
  }
};

const saveSetting = async (
  key: string,
  value: string,
  options: { silent?: boolean } = {},
) => {
  try {
    await post(`/settings/${key}`, { value });
    if (!options.silent) {
      message.success("保存成功");
    }
  } catch (e: any) {
    message.error(e.message || "保存请求失败");
  }
};

const handleSaveWikiRoot = async () => {
  await saveSetting("wiki_root", wikiRoot.value);
};

const resetWikiRoot = () => {
  wikiRoot.value = wikiDefault.value;
};

const runHermesTest = async () => {
  hermesStatus.value = "testing";
  hermesMessage.value = "正在测试 Hermes CLI...";
  try {
    const data = await post("/settings/test/hermes");
    hermesStatus.value = data.status === "success" ? "success" : "error";
    hermesMessage.value = data.message;
  } catch (e: any) {
    hermesStatus.value = "error";
    hermesMessage.value = "测试请求失败";
  }
};

const testHermes = async () => {
  await saveSetting("hermes_cli_path", hermesPath.value);
  await runHermesTest();
};

const resetHermes = () => {
  hermesPath.value = hermesDefault.value;
};

onMounted(async () => {
  await fetchSettings();
  if (hermesPath.value) runHermesTest();
});
</script>

<template>
  <div class="settings-container">
    <div class="page-header">
      <h2 class="page-title">系统运行设置</h2>
      <p class="page-desc">配置本地环境路径与知识库存储位置</p>
    </div>

    <div class="settings-content">
      <!-- 知识库配置 -->
      <n-card title="知识库存储设置" class="setting-card">
        <n-form label-placement="top">
          <n-form-item label="知识库根目录 (WIKI_ROOT)">
            <n-input
              v-model:value="wikiRoot"
              placeholder="例如: /Users/yolanda/Documents/Wiki"
            />
            <template #feedback>
              生成的 Markdown 文件将存放在此目录下。修改后即时生效。
            </template>
          </n-form-item>

          <n-space style="margin-top: 16px">
            <n-button type="primary" @click="handleSaveWikiRoot">
              <template #icon
                ><n-icon><FolderOpenOutline /></n-icon
              ></template>
              保存路径
            </n-button>
            <n-button @click="resetWikiRoot">
              <template #icon
                ><n-icon><RefreshOutline /></n-icon
              ></template>
              恢复默认值
            </n-button>
          </n-space>
        </n-form>
      </n-card>

      <n-card title="Hermes CLI 引擎" class="setting-card">
        <template #header-extra>
          <n-tag
            :type="
              hermesStatus === 'success'
                ? 'success'
                : hermesStatus === 'error'
                  ? 'error'
                  : 'default'
            "
            round
          >
            <template #icon>
              <n-icon v-if="hermesStatus === 'success'"
                ><CheckmarkCircleOutline
              /></n-icon>
              <n-icon v-else-if="hermesStatus === 'error'"
                ><CloseCircleOutline
              /></n-icon>
            </template>
            {{
              hermesStatus === "success"
                ? "可用"
                : hermesStatus === "error"
                  ? "不可用"
                  : "未测试"
            }}
          </n-tag>
        </template>

        <n-form label-placement="top">
          <n-form-item label="CLI 执行路径">
            <n-input
              v-model:value="hermesPath"
              placeholder="例如: ~/.local/bin/hermes"
            />
          </n-form-item>

          <div v-if="hermesMessage" class="test-message" :class="hermesStatus">
            {{ hermesMessage }}
          </div>

          <n-space style="margin-top: 16px">
            <n-button
              type="primary"
              :loading="hermesStatus === 'testing'"
              @click="testHermes"
            >
              <template #icon
                ><n-icon><BuildOutline /></n-icon
              ></template>
              测试并保存
            </n-button>
            <n-button @click="resetHermes">
              <template #icon
                ><n-icon><RefreshOutline /></n-icon
              ></template>
              恢复默认值
            </n-button>
          </n-space>
        </n-form>
      </n-card>

    </div>
  </div>
</template>

<style scoped>
.settings-container {
  height: 100%;
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 500;
  color: #1f2225;
}

.page-desc {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-bottom: 24px;
}

.setting-card {
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.test-message {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  word-break: break-all;
}

.test-message.success {
  background-color: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
}

.test-message.error {
  background-color: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.test-message.testing {
  background-color: #f8fafc;
  color: #475569;
  border: 1px solid #e2e8f0;
}
</style>

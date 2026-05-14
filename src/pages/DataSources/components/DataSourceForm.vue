<script setup lang="ts">
import { ref, watch } from "vue";
import {
  NAlert,
  NButton,
  NForm,
  NFormItem,
  NFormItemGi,
  NGrid,
  NIcon,
  NInput,
  NInputNumber,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpace,
  NTag,
  NText,
  useMessage,
  type FormInst,
  type FormRules,
} from "naive-ui";
import {
  CloudOutline,
  DocumentAttachOutline,
  FlaskOutline,
  SaveOutline,
  ShieldCheckmarkOutline,
  TrashOutline,
} from "@vicons/ionicons5";

const props = defineProps<{
  sourceData: any | null;
}>();

const emit = defineEmits(["save", "test", "delete"]);
const message = useMessage();

const formRef = ref<FormInst | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const selectedFiles = ref<File[]>([]);
const formModel = ref({
  id: null as number | null,
  name: "",
  db_type: "oracle",
  host: "",
  port: 1521,
  database: "",
  username: "",
  password: "",
  auth_type: "password",
  source_mode: "connection",
  source_status: "draft",
  source_message: "",
  source_file_count: 0,
});

const connectionTypeOptions = [{ label: "Oracle", value: "oracle" }];
const fileTypeOptions = [{ label: "Oracle DDL / PL/SQL", value: "oracle" }];

watch(
  () => props.sourceData,
  (newVal) => {
    selectedFiles.value = [];
    const defaults = {
      id: null,
      name: "",
      db_type: "oracle",
      host: "",
      port: 1521,
      database: "",
      username: "",
      password: "",
      auth_type: "password",
      source_mode: "connection",
      source_status: "draft",
      source_message: "",
      source_file_count: 0,
    };
    if (newVal) {
      formModel.value = {
        ...defaults,
        ...newVal,
        password: "",
      };
      return;
    }
    formModel.value = defaults;
  },
  { immediate: true },
);

const rules: FormRules = {
  name: { required: true, message: "请输入数据源名称", trigger: "blur" },
  db_type: { required: true, message: "请选择数据库类型", trigger: "change" },
  host: {
    validator() {
      if (formModel.value.source_mode === "connection" && !formModel.value.host) {
        return new Error("请输入主机地址");
      }
      return true;
    },
    trigger: ["blur", "input"],
  },
  port: {
    validator() {
      if (formModel.value.source_mode === "connection" && !formModel.value.port) {
        return new Error("请输入端口");
      }
      return true;
    },
    trigger: ["blur", "input"],
  },
  database: {
    validator() {
      if (
        formModel.value.source_mode === "connection" &&
        !formModel.value.database
      ) {
        return new Error("请输入数据库名");
      }
      return true;
    },
    trigger: ["blur", "input"],
  },
  username: {
    validator() {
      if (
        formModel.value.source_mode === "connection" &&
        formModel.value.auth_type === "password" &&
        !formModel.value.username
      ) {
        return new Error("请输入用户名");
      }
      return true;
    },
    trigger: ["blur", "input"],
  },
  password: {
    validator() {
      if (
        formModel.value.source_mode === "connection" &&
        formModel.value.auth_type === "password" &&
        !formModel.value.id &&
        !formModel.value.password
      ) {
        return new Error("请输入密码");
      }
      return true;
    },
    trigger: ["blur", "input"],
  },
};

const handlePickFiles = () => {
  fileInputRef.value?.click();
};

const handleFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement;
  selectedFiles.value = Array.from(input.files || []);
};

const getModeLabel = (mode: string) =>
  mode === "sql_file" ? "SQL 文件导入" : "手动连接";

const getSourceStatusLabel = (status: string) => {
  switch (status) {
    case "connection_ok":
      return "连接正常";
    case "file_uploaded":
      return "已上传";
    case "parse_success":
      return "已解析";
    case "parse_failed":
      return "解析失败";
    case "syncing":
      return "处理中";
    case "sync_failed":
      return "失败";
    default:
      return "草稿";
  }
};

const handleSave = async () => {
  if (!formRef.value) return;
  try {
    await formRef.value.validate();
    if (
      formModel.value.source_mode === "sql_file" &&
      !formModel.value.id &&
      selectedFiles.value.length === 0
    ) {
      throw new Error("首次创建 SQL 文件型数据源时，必须上传至少一个 .sql 文件");
    }

    // 构造干净的 payload，避免参数污染
    const {
      id,
      name,
      db_type,
      source_mode,
      host,
      port,
      database,
      username,
      password,
      auth_type,
    } = formModel.value;

    const payload: any = { id, name, db_type, source_mode };

    if (source_mode === "connection") {
      Object.assign(payload, {
        host,
        port,
        database,
        username,
        auth_type,
      });
      // 只有输入了密码才发送（支持修改时不改密码）
      if (password) {
        payload.password = password;
      }
    }

    emit("save", {
      data: payload,
      files: selectedFiles.value,
    });
  } catch (error: any) {
    if (error?.message) {
      message.error(error.message);
    }
  }
};
</script>

<template>
  <div v-if="props.sourceData" class="form-container">
    <div class="form-header">
      <div class="title-group">
        <n-text class="main-title">{{ formModel.name || "新建数据源" }}</n-text>
        <n-space align="center" :size="8">
          <n-tag size="small" :bordered="false">{{ getModeLabel(formModel.source_mode) }}</n-tag>
          <n-tag size="small" :bordered="false" type="info">
            {{ getSourceStatusLabel(formModel.source_status) }}
          </n-tag>
        </n-space>
      </div>
      <n-space :size="12">
        <n-button
          type="error"
          quaternary
          :disabled="!formModel.id"
          @click="emit('delete', formModel.id)"
        >
          <template #icon>
            <n-icon><TrashOutline /></n-icon>
          </template>
          删除数据源
        </n-button>
        <n-button
          v-if="formModel.source_mode === 'connection'"
          secondary
          :disabled="!formModel.id"
          @click="emit('test', formModel.id)"
        >
          <template #icon>
            <n-icon><FlaskOutline /></n-icon>
          </template>
          测试连接
        </n-button>
        <n-button type="primary" @click="handleSave">
          <template #icon>
            <n-icon><SaveOutline /></n-icon>
          </template>
          {{ formModel.id ? "保存修改" : formModel.source_mode === "sql_file" ? "创建并上传" : "保存数据源" }}
        </n-button>
      </n-space>
    </div>

    <n-form
      ref="formRef"
      :model="formModel"
      :rules="rules"
      label-placement="top"
      size="small"
    >
      <div class="section">
        <div class="section-header">
          <n-icon size="20" color="#2080f0"><CloudOutline /></n-icon>
          <n-text class="section-title">来源模式</n-text>
        </div>
        <n-form-item label="选择来源类型">
          <n-radio-group v-model:value="formModel.source_mode" name="source_mode">
            <n-radio-button value="connection">手动连接</n-radio-button>
            <n-radio-button value="sql_file">SQL 文件导入</n-radio-button>
          </n-radio-group>
        </n-form-item>
      </div>

      <div class="section">
        <div class="section-header">
          <n-icon size="20" color="#2080f0"><DocumentAttachOutline /></n-icon>
          <n-text class="section-title">基本信息</n-text>
        </div>

        <n-grid :cols="2" :x-gap="24">
          <n-form-item-gi label="数据源名称" path="name">
            <n-input v-model:value="formModel.name" placeholder="例如：监管 ODS SQL 文件" />
          </n-form-item-gi>
          <n-form-item-gi label="数据库类型" path="db_type">
            <n-select
              v-model:value="formModel.db_type"
              :options="formModel.source_mode === 'sql_file' ? fileTypeOptions : connectionTypeOptions"
            />
          </n-form-item-gi>
        </n-grid>
      </div>

      <div v-if="formModel.source_mode === 'connection'" class="section">
        <div class="section-header">
          <n-icon size="20" color="#2080f0"><CloudOutline /></n-icon>
          <n-text class="section-title">连接信息</n-text>
        </div>

        <n-grid :cols="2" :x-gap="24">
          <n-form-item-gi label="主机地址 / 端点" path="host" span="2">
            <n-input
              v-model:value="formModel.host"
              class="mono-input"
              placeholder="127.0.0.1"
            />
          </n-form-item-gi>
          <n-form-item-gi label="端口" path="port">
            <n-input-number
              v-model:value="formModel.port"
              :show-button="false"
              class="full-width"
            />
          </n-form-item-gi>
          <n-form-item-gi label="数据库名 / 服务名" path="database">
            <n-input v-model:value="formModel.database" placeholder="orclpdb" />
          </n-form-item-gi>
        </n-grid>
      </div>

      <div v-if="formModel.source_mode === 'connection'" class="section no-border">
        <div class="section-header">
          <n-icon size="20" color="#2080f0"><ShieldCheckmarkOutline /></n-icon>
          <n-text class="section-title">身份验证</n-text>
        </div>



        <n-grid :cols="2" :x-gap="24">
          <n-form-item-gi label="用户名" path="username">
            <n-input v-model:value="formModel.username" />
          </n-form-item-gi>
          <n-form-item-gi label="密码" path="password">
            <n-input
              v-model:value="formModel.password"
              type="password"
              show-password-on="click"
            />
          </n-form-item-gi>
        </n-grid>
      </div>

      <div v-else class="section no-border">
        <div class="section-header">
          <n-icon size="20" color="#2080f0"><DocumentAttachOutline /></n-icon>
          <n-text class="section-title">SQL 文件</n-text>
        </div>

        <n-alert type="info" :bordered="false" class="file-alert">
          文件型数据源支持一次上传多个 `.sql` 文件。系统会在元数据管理页按最新批次执行“解析并同步”，并用该批次结果全量替换旧对象。
        </n-alert>

        <div class="file-panel">
          <n-space vertical :size="12" style="width: 100%">
            <n-space align="center" justify="space-between">
              <div>
                <div class="file-title">上传 SQL 文件</div>
                <div class="file-hint">
                  {{ selectedFiles.length > 0 ? `已选择 ${selectedFiles.length} 个文件` : `当前批次文件数：${formModel.source_file_count || 0}` }}
                </div>
              </div>
              <n-button secondary @click="handlePickFiles">
                <template #icon>
                  <n-icon><DocumentAttachOutline /></n-icon>
                </template>
                {{ formModel.id ? "选择替换文件" : "选择 SQL 文件" }}
              </n-button>
            </n-space>

            <input
              ref="fileInputRef"
              type="file"
              accept=".sql"
              multiple
              class="hidden-file-input"
              @change="handleFileChange"
            />

            <div v-if="selectedFiles.length > 0" class="file-list">
              <div v-for="file in selectedFiles" :key="file.name" class="file-item">
                {{ file.name }}
              </div>
            </div>
            <n-text v-else depth="3">
              {{ formModel.id ? "未选择新的替换文件" : "请至少选择一个 .sql 文件" }}
            </n-text>

            <n-alert
              v-if="formModel.source_message"
              type="default"
              :bordered="false"
            >
              {{ formModel.source_message }}
            </n-alert>
          </n-space>
        </div>
      </div>
    </n-form>
  </div>
  <div v-else class="empty-state">
    <div class="empty-content">
      <n-text depth="3">请在左侧选择或新建一个数据源</n-text>
    </div>
  </div>
</template>

<style scoped>
.form-container {
  padding: 12px 16px;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f5;
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.main-title {
  font-size: 18px;
  font-weight: 600;
  color: #181c22;
}

.section {
  margin-bottom: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #181c22;
}

:deep(.n-form-item) {
  margin-bottom: 12px;
}

:deep(.n-form-item-label) {
  padding-bottom: 2px !important;
}

.mono-input {
  font-family: "Fira Code", monospace;
}

.full-width {
  width: 100%;
}

.file-alert {
  margin-bottom: 16px;
}

.file-panel {
  border: 1px dashed #d8deee;
  border-radius: 12px;
  padding: 16px;
  background: #fafcff;
}

.file-title {
  font-size: 14px;
  font-weight: 600;
  color: #181c22;
}

.file-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #7b8190;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #edf1f8;
  font-size: 13px;
  color: #3b4252;
}

.hidden-file-input {
  display: none;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
}
</style>

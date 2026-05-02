<script setup lang="ts">
import { ref, watch } from "vue";
import {
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NInputNumber,
  NButton,
  NSpace,
  NText,
  NRadioGroup,
  NRadioButton,
  FormRules,
  FormInst,
  NGrid,
  NFormItemGi,
  NAlert,
} from "naive-ui";
import {
  ShieldCheckmarkOutline,
  CloudOutline,
  TrashOutline,
  FlaskOutline,
  SaveOutline,
} from "@vicons/ionicons5";
import { NIcon } from "naive-ui";

const props = defineProps<{
  sourceData: any | null;
}>();

const emit = defineEmits(["save", "test", "delete"]);

const formRef = ref<FormInst | null>(null);
const formModel = ref({
  id: null as number | null,
  name: "",
  db_type: "mysql",
  host: "",
  port: 3306,
  database: "",
  username: "",
  password: "",
  auth_type: "password",
});

watch(
  () => props.sourceData,
  (newVal) => {
    if (newVal) {
      // 确保 auth_type 有默认值，同时保留已有状态
      formModel.value = {
        auth_type: newVal.auth_type || "password",
        password: "",
        ...newVal,
      };
    } else {
      formModel.value = {
        id: null,
        name: "",
        db_type: "mysql",
        host: "",
        port: 3306,
        database: "",
        username: "",
        password: "",
        auth_type: "password",
      };
    }
  },
  { immediate: true },
);

const rules: FormRules = {
  name: { required: true, message: "请输入连接名称", trigger: "blur" },
  db_type: { required: true, message: "请选择数据库类型", trigger: "change" },
  host: { required: true, message: "请输入主机地址", trigger: "blur" },
  port: {
    required: true,
    type: "number",
    message: "请输入端口",
    trigger: "blur",
  },
  database: { required: true, message: "请输入数据库名", trigger: "blur" },
  username: {
    validator(rule, value) {
      if (formModel.value.auth_type === "password" && !value)
        return new Error("请输入用户名");
      return true;
    },
    trigger: ["input", "blur"],
  },
  password: {
    validator(rule, value) {
      const isExistingSource = Boolean(formModel.value.id);
      if (formModel.value.auth_type === "password" && !isExistingSource && !value)
        return new Error("请输入密码");
      return true;
    },
    trigger: ["input", "blur"],
  },
};

const typeOptions = [
  { label: "PostgreSQL", value: "postgresql" },
  { label: "MySQL", value: "mysql" },
  { label: "Oracle", value: "oracle" },
];

const handleSave = async () => {
  if (!formRef.value) return;
  try {
    await formRef.value.validate();
    const payload = { ...formModel.value };
    if (payload.id && payload.auth_type === "password" && !payload.password) {
      delete (payload as Partial<typeof payload>).password;
    }
    emit("save", payload);
  } catch (errors) {
    console.debug("表单校验未通过", errors);
  }
};
</script>

<template>
  <div v-if="props.sourceData" class="form-container">
    <!-- 头部操作区 -->
    <div class="form-header">
      <div class="title-group">
        <n-text class="main-title">{{
          formModel.name || "新建连接配置"
        }}</n-text>
        <n-text depth="3" class="sub-title"
          >配置数据库连接凭据及访问策略</n-text
        >
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
        <n-button secondary @click="emit('test', formModel.id)">
          <template #icon>
            <n-icon><FlaskOutline /></n-icon>
          </template>
          测试连接
        </n-button>
        <n-button type="primary" @click="handleSave" class="save-btn">
          <template #icon>
            <n-icon><SaveOutline /></n-icon>
          </template>
          保存修改
        </n-button>
      </n-space>
    </div>

    <n-form
      ref="formRef"
      :model="formModel"
      :rules="rules"
      label-placement="top"
      size="large"
    >
      <!-- 基本信息区块 -->
      <div class="section">
        <div class="section-header">
          <n-icon size="20" color="#2080f0"><CloudOutline /></n-icon>
          <n-text class="section-title">基本信息</n-text>
        </div>

        <n-grid :cols="2" :x-gap="24">
          <n-form-item-gi label="连接名称" path="name">
            <n-input
              v-model:value="formModel.name"
              placeholder="例如: Production_DB"
            />
          </n-form-item-gi>
          <n-form-item-gi label="数据库类型" path="db_type">
            <n-select
              v-model:value="formModel.db_type"
              :options="typeOptions"
            />
          </n-form-item-gi>

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
          <n-form-item-gi label="数据库名" path="database">
            <n-input v-model:value="formModel.database" placeholder="app_db" />
          </n-form-item-gi>
        </n-grid>
      </div>

      <!-- 身份验证区块 -->
      <div class="section no-border">
        <div class="section-header">
          <n-icon size="20" color="#2080f0"><ShieldCheckmarkOutline /></n-icon>
          <n-text class="section-title">身份验证</n-text>
        </div>

        <n-form-item label="认证方式" class="auth-toggle">
          <n-radio-group
            v-model:value="formModel.auth_type"
            name="auth_type"
            size="medium"
          >
            <n-radio-button value="password">用户名密码</n-radio-button>
            <n-radio-button value="ssh">SSH 通道模式</n-radio-button>
          </n-radio-group>
        </n-form-item>

        <div class="auth-content">
          <transition name="fade-slide" mode="out-in">
            <div v-if="formModel.auth_type === 'password'" key="password">
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
            <div v-else key="ssh" class="ssh-placeholder">
              <n-alert title="SSH 通道连接" type="info" :bordered="false">
                当前已启用 SSH
                通道模式。系统将直接通过上述基本信息中的主机与端口，利用预设的网关进行隧道连接，无需额外凭据。
              </n-alert>
            </div>
          </transition>
        </div>
      </div>
    </n-form>
  </div>
  <div v-else class="empty-state">
    <div class="empty-content">
      <n-text depth="3">请在左侧选择或新建一个连接</n-text>
    </div>
  </div>
</template>

<style scoped>
.form-container {
  padding: 12px 4px;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f0f0f5;
}

.main-title {
  font-size: 22px;
  font-weight: 600;
  color: #181c22;
  display: block;
  margin-bottom: 4px;
}

.sub-title {
  font-size: 13px;
}

.section {
  margin-bottom: 40px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #181c22;
}

.mono-input {
  font-family: "Fira Code", monospace;
}

.full-width {
  width: 100%;
}

.auth-toggle {
  margin-bottom: 24px;
}

.auth-content {
  min-height: 80px;
}

.save-btn {
  padding: 0 24px;
  font-weight: 500;
}

.empty-state {
  display: flex;
  height: 100%;
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
}

/* 动画效果 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.25s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>

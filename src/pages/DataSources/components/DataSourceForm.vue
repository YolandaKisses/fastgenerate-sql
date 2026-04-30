<script setup lang="ts">
import { ref, watch } from 'vue'
import { NForm, NFormItem, NInput, NSelect, NInputNumber, NButton, NSpace, NText } from 'naive-ui'

const props = defineProps<{
  sourceData: any | null
}>()

const emit = defineEmits(['save', 'test', 'delete'])

const formModel = ref({
  id: null as number | null,
  name: '',
  db_type: 'mysql',
  host: '',
  port: 3306,
  database: '',
  username: '',
  password: ''
})

watch(() => props.sourceData, (newVal) => {
  if (newVal) {
    formModel.value = { ...newVal }
  } else {
    formModel.value = {
      id: null,
      name: '',
      db_type: 'mysql',
      host: '',
      port: 3306,
      database: '',
      username: '',
      password: ''
    }
  }
}, { immediate: true })

const typeOptions = [
  { label: 'PostgreSQL', value: 'postgresql' },
  { label: 'MySQL', value: 'mysql' },
  { label: 'Oracle', value: 'oracle' }
]
</script>

<template>
  <div v-if="props.sourceData">
    <n-space justify="space-between" align="center" style="margin-bottom: 24px;">
      <div>
        <n-text style="font-size: 20px; font-weight: 600;">{{ formModel.name || '新建连接配置' }}</n-text>
        <br>
        <n-text depth="3" style="font-size: 14px;">管理连接凭据、访问策略及基本同步设置。</n-text>
      </div>
      <n-space>
        <n-button type="error" ghost :disabled="!formModel.id" @click="emit('delete', formModel.id)">删除数据源</n-button>
        <n-button @click="emit('test', formModel.id)">测试连接</n-button>
        <n-button type="primary" @click="emit('save', formModel)">保存修改</n-button>
      </n-space>
    </n-space>

    <n-form :model="formModel" label-placement="top" size="large">
      <div class="section-title">
        <div class="indicator"></div>
        <n-text style="font-size: 16px; font-weight: 600;">基本信息</n-text>
      </div>
      
      <n-space vertical :size="16">
        <n-space :size="24" item-style="width: calc(50% - 12px);">
          <n-form-item label="连接名称" path="name">
            <n-input v-model:value="formModel.name" placeholder="例如: Production_DB" />
          </n-form-item>
          <n-form-item label="数据库类型" path="db_type">
            <n-select v-model:value="formModel.db_type" :options="typeOptions" />
          </n-form-item>
        </n-space>
        
        <n-form-item label="主机地址 / 端点" path="host">
          <n-input v-model:value="formModel.host" style="font-family: monospace;" placeholder="127.0.0.1" />
        </n-form-item>
        
        <n-space :size="24" item-style="width: calc(50% - 12px);">
          <n-form-item label="端口" path="port">
            <n-input-number v-model:value="formModel.port" :show-button="false" style="width: 100%;" />
          </n-form-item>
          <n-form-item label="数据库名 (Database/Schema)" path="database">
            <n-input v-model:value="formModel.database" />
          </n-form-item>
        </n-space>
      </n-space>

      <div class="section-title" style="margin-top: 32px;">
        <div class="indicator"></div>
        <n-text style="font-size: 16px; font-weight: 600;">身份验证</n-text>
      </div>
      
      <div class="auth-box">
        <n-space :size="24" item-style="width: calc(50% - 12px);">
          <n-form-item label="用户名" path="username">
            <n-input v-model:value="formModel.username" />
          </n-form-item>
          <n-form-item label="密码" path="password">
            <n-input v-model:value="formModel.password" type="password" show-password-on="click" />
          </n-form-item>
        </n-space>
      </div>
    </n-form>
  </div>
  <div v-else style="display: flex; height: 100%; align-items: center; justify-content: center;">
    <n-text depth="3">请在左侧选择或新建一个连接</n-text>
  </div>
</template>

<style scoped>
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.indicator {
  width: 6px;
  height: 20px;
  background-color: #2080f0;
  border-radius: 4px;
}
.auth-box {
  padding: 24px;
  background-color: #fbfcfd;
  border: 1px solid #efeff5;
  border-radius: 8px;
}
</style>

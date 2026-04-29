<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  NCard, NSpace, NForm, NFormItem, NInput, NButton, NText, NInputNumber, useMessage
} from 'naive-ui'

const message = useMessage()

const modelConfig = ref({
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  model_name: 'gpt-4o',
  timeout: 30,
  temperature: 0.0
})

onMounted(async () => {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/model-config/')
    if (res.ok) {
      const data = await res.json()
      modelConfig.value = data
    }
  } catch (error) {
    // 后端未启动时静默
  }
})

const handleSave = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/model-config/', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(modelConfig.value)
    })
    if (res.ok) {
      message.success('模型配置已保存')
    } else {
      message.error('保存失败')
    }
  } catch (error) {
    message.error('请求失败')
  }
}

const handleTestConnection = async () => {
  // 简单测试：尝试请求模型列表
  try {
    const res = await fetch(`${modelConfig.value.base_url}/models`, {
      headers: { 'Authorization': `Bearer ${modelConfig.value.api_key}` }
    })
    if (res.ok) {
      message.success('API 连接成功')
    } else {
      message.error(`API 连接失败 (${res.status})`)
    }
  } catch (error) {
    message.error('无法连接到 API 服务')
  }
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h1 class="page-title">设置</h1>
      <p class="page-subtitle">配置您的 SQL AI 工作区，调整模型连接及本地偏好。</p>
    </div>

    <n-space vertical :size="24">
      <n-card class="custom-card" title="模型配置" size="large" :bordered="true">
        <template #header-extra>
          <n-text depth="3" class="meta-note">当前启用配置</n-text>
        </template>
        <n-form :model="modelConfig" label-placement="top" size="large">
          <n-form-item label="API 基础 URL" path="base_url">
            <n-input v-model:value="modelConfig.base_url" placeholder="https://api.openai.com/v1" />
          </n-form-item>
          <n-form-item label="API 密钥 (API Key)" path="api_key">
            <n-input v-model:value="modelConfig.api_key" type="password" show-password-on="click" placeholder="sk-..." />
          </n-form-item>
          <n-space :size="24" item-style="width: calc(33% - 16px);">
            <n-form-item label="模型名称" path="model_name">
              <n-input v-model:value="modelConfig.model_name" placeholder="gpt-4o" />
            </n-form-item>
            <n-form-item label="超时 (秒)" path="timeout">
              <n-input-number v-model:value="modelConfig.timeout" :min="5" :max="120" style="width: 100%;" />
            </n-form-item>
            <n-form-item label="Temperature" path="temperature">
              <n-input-number v-model:value="modelConfig.temperature" :min="0" :max="2" :step="0.1" style="width: 100%;" />
            </n-form-item>
          </n-space>
          <n-space>
            <n-button type="primary" @click="handleSave">保存修改</n-button>
            <n-button @click="handleTestConnection">测试连接</n-button>
          </n-space>
        </n-form>
      </n-card>
    </n-space>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 960px;
  margin: 0 auto;
  font-family: 'Inter', sans-serif;
  color: #181c22;
}

.page-header {
  margin-bottom: 32px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 28px;
  margin: 0 0 8px 0;
}

.page-subtitle {
  font-size: 14px;
  line-height: 22px;
  color: #717785;
  margin: 0;
}

.meta-note {
  font-size: 13px;
  color: #2080f0;
  font-weight: 500;
}

.custom-card {
  box-shadow: none;
}
</style>

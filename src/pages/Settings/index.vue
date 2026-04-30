<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NForm, NFormItem, NInput, NButton, NSpace, NTag, useMessage } from 'naive-ui'
import { CheckmarkCircleOutline, CloseCircleOutline, BuildOutline, FolderOpenOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { get, post } from '../../services/request'

const message = useMessage()

const hermesPath = ref('')
const hermesDefault = ref('')
const hermesStatus = ref<'idle' | 'testing' | 'success' | 'error'>('idle')
const hermesMessage = ref('')

const obsidianRoot = ref('')
const obsidianDefault = ref('')
const obsidianStatus = ref<'idle' | 'testing' | 'success' | 'error'>('idle')
const obsidianMessage = ref('')

const fetchSettings = async () => {
  try {
    const data = await get('/settings/')
    hermesPath.value = data.hermes_cli_path.value || data.hermes_cli_path.default
    hermesDefault.value = data.hermes_cli_path.default
    
    obsidianRoot.value = data.obsidian_vault_root.value || data.obsidian_vault_root.default
    obsidianDefault.value = data.obsidian_vault_root.default
  } catch (e) {
    message.error('获取设置失败')
  }
}

const saveSetting = async (key: string, value: string) => {
  try {
    await post(`/settings/${key}`, { value })
    message.success('保存成功')
  } catch (e: any) {
    message.error(e.message || '保存请求失败')
  }
}

const runHermesTest = async () => {
  hermesStatus.value = 'testing'
  hermesMessage.value = '正在测试 Hermes CLI...'
  try {
    const data = await post('/settings/test/hermes')
    hermesStatus.value = data.status === 'success' ? 'success' : 'error'
    hermesMessage.value = data.message
  } catch (e: any) {
    hermesStatus.value = 'error'
    hermesMessage.value = '测试请求失败'
  }
}

const runObsidianTest = async () => {
  obsidianStatus.value = 'testing'
  obsidianMessage.value = '正在检查知识库目录...'
  try {
    const data = await post('/settings/test/obsidian')
    obsidianStatus.value = data.status === 'success' ? 'success' : 'error'
    obsidianMessage.value = data.message
  } catch (e: any) {
    obsidianStatus.value = 'error'
    obsidianMessage.value = '测试请求失败'
  }
}

const testHermes = async () => {
  await saveSetting('hermes_cli_path', hermesPath.value)
  await runHermesTest()
}

const testObsidian = async () => {
  await saveSetting('obsidian_vault_root', obsidianRoot.value)
  await runObsidianTest()
}

const resetHermes = () => {
  hermesPath.value = hermesDefault.value
}

const resetObsidian = () => {
  obsidianRoot.value = obsidianDefault.value
}

onMounted(async () => {
  await fetchSettings()
  // 页面加载时自动执行一次静默检查
  if (hermesPath.value) runHermesTest()
  if (obsidianRoot.value) runObsidianTest()
})
</script>

<template>
  <div class="settings-container">
    <div class="page-header">
      <h2 class="page-title">本地运行设置</h2>
      <p class="page-desc">配置本地环境路径，覆盖默认环境变量</p>
    </div>

    <div class="settings-content">
      <!-- Hermes CLI 配置 -->
      <n-card title="Hermes CLI 引擎" class="setting-card">
        <template #header-extra>
          <n-tag :type="hermesStatus === 'success' ? 'success' : (hermesStatus === 'error' ? 'error' : 'default')" round>
            <template #icon>
              <n-icon v-if="hermesStatus === 'success'"><CheckmarkCircleOutline /></n-icon>
              <n-icon v-else-if="hermesStatus === 'error'"><CloseCircleOutline /></n-icon>
            </template>
            {{ hermesStatus === 'success' ? '可用' : (hermesStatus === 'error' ? '不可用' : '未测试') }}
          </n-tag>
        </template>
        
        <n-form label-placement="top">
          <n-form-item label="CLI 执行路径">
            <n-input v-model:value="hermesPath" placeholder="例如: ~/.local/bin/hermes" />
          </n-form-item>
          
          <div v-if="hermesMessage" class="test-message" :class="hermesStatus">
            {{ hermesMessage }}
          </div>
          
          <n-space style="margin-top: 16px;">
            <n-button type="primary" :loading="hermesStatus === 'testing'" @click="testHermes">
              <template #icon><n-icon><BuildOutline /></n-icon></template>
              测试并保存
            </n-button>
            <n-button @click="resetHermes">恢复默认值</n-button>
          </n-space>
        </n-form>
      </n-card>

      <!-- Obsidian 配置 -->
      <n-card title="Obsidian 知识库" class="setting-card">
        <template #header-extra>
          <n-tag :type="obsidianStatus === 'success' ? 'success' : (obsidianStatus === 'error' ? 'error' : 'default')" round>
            <template #icon>
              <n-icon v-if="obsidianStatus === 'success'"><CheckmarkCircleOutline /></n-icon>
              <n-icon v-else-if="obsidianStatus === 'error'"><CloseCircleOutline /></n-icon>
            </template>
            {{ obsidianStatus === 'success' ? '目录正常' : (obsidianStatus === 'error' ? '目录异常' : '未测试') }}
          </n-tag>
        </template>
        
        <n-form label-placement="top">
          <n-form-item label="知识库根目录">
            <n-input v-model:value="obsidianRoot" placeholder="例如: ~/Documents/obsidian知识库/FastGenerate SQL" />
          </n-form-item>
          
          <div v-if="obsidianMessage" class="test-message" :class="obsidianStatus">
            {{ obsidianMessage }}
          </div>
          
          <n-space style="margin-top: 16px;">
            <n-button type="primary" :loading="obsidianStatus === 'testing'" @click="testObsidian">
              <template #icon><n-icon><FolderOpenOutline /></n-icon></template>
              检查并保存
            </n-button>
            <n-button @click="resetObsidian">恢复默认值</n-button>
          </n-space>
        </n-form>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.settings-container {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
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

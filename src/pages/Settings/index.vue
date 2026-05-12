<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NForm, NFormItem, NInput, NButton, NSpace, NTag, NSelect, NSwitch, useMessage } from 'naive-ui'
import { CheckmarkCircleOutline, CloseCircleOutline, BuildOutline, FolderOpenOutline, RefreshOutline, FlashOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { get, post } from '../../services/request'

const message = useMessage()

const hermesPath = ref('')
const hermesDefault = ref('')
const hermesStatus = ref<'idle' | 'testing' | 'success' | 'error'>('idle')
const hermesMessage = ref('')

const wikiRoot = ref('')
const wikiDefault = ref('')
const ragRebuilding = ref(false)
const ragBackend = ref<'local' | 'lightrag'>('local')
const ragBackendDefault = ref<'local' | 'lightrag'>('local')
const lightragBaseUrl = ref('')
const lightragBaseUrlDefault = ref('')
const lightragApiKey = ref('')
const lightragApiKeyDefault = ref('')
const lightragTimeoutSeconds = ref('20')
const lightragTimeoutDefault = ref('20')
const lightragEnableRemoteRebuild = ref(false)
const lightragEnableRemoteRebuildDefault = ref(false)
const lightragEnableRemoteAsk = ref(false)
const lightragEnableRemoteAskDefault = ref(false)
const lightragStatus = ref<'idle' | 'testing' | 'success' | 'error'>('idle')
const lightragMessage = ref('')

const ragBackendOptions = [
  { label: '本地兼容后端', value: 'local' },
  { label: 'LightRAG 后端', value: 'lightrag' },
]

const fetchSettings = async () => {
  try {
    const data = await get('/settings/')
    hermesPath.value = data.hermes_cli_path.value || data.hermes_cli_path.default
    hermesDefault.value = data.hermes_cli_path.default
    
    wikiRoot.value = data.wiki_root.value || data.wiki_root.default
    wikiDefault.value = data.wiki_root.default

    ragBackend.value = (data.rag_retrieval_backend.value || data.rag_retrieval_backend.default || 'local') as 'local' | 'lightrag'
    ragBackendDefault.value = (data.rag_retrieval_backend.default || 'local') as 'local' | 'lightrag'
    lightragBaseUrl.value = data.lightrag_base_url.value || data.lightrag_base_url.default || ''
    lightragBaseUrlDefault.value = data.lightrag_base_url.default || ''
    lightragApiKey.value = data.lightrag_api_key.value || data.lightrag_api_key.default || ''
    lightragApiKeyDefault.value = data.lightrag_api_key.default || ''
    lightragTimeoutSeconds.value = data.lightrag_timeout_seconds.value || data.lightrag_timeout_seconds.default || '20'
    lightragTimeoutDefault.value = data.lightrag_timeout_seconds.default || '20'
    const rebuildValue = (data.lightrag_enable_remote_rebuild.value || data.lightrag_enable_remote_rebuild.default || 'false').toLowerCase()
    lightragEnableRemoteRebuild.value = rebuildValue === 'true'
    lightragEnableRemoteRebuildDefault.value = (data.lightrag_enable_remote_rebuild.default || 'false').toLowerCase() === 'true'
    const askValue = (data.lightrag_enable_remote_ask.value || data.lightrag_enable_remote_ask.default || 'false').toLowerCase()
    lightragEnableRemoteAsk.value = askValue === 'true'
    lightragEnableRemoteAskDefault.value = (data.lightrag_enable_remote_ask.default || 'false').toLowerCase() === 'true'
  } catch (e) {
    message.error('获取设置失败')
  }
}

const saveSetting = async (key: string, value: string, options: { silent?: boolean } = {}) => {
  try {
    await post(`/settings/${key}`, { value })
    if (!options.silent) {
      message.success('保存成功')
    }
  } catch (e: any) {
    message.error(e.message || '保存请求失败')
  }
}

const handleSaveWikiRoot = async () => {
  await saveSetting('wiki_root', wikiRoot.value)
}

const resetWikiRoot = () => {
  wikiRoot.value = wikiDefault.value
}

const rebuildRagIndex = async () => {
  ragRebuilding.value = true
  try {
    const data = await post<{ indexed_files: number; indexed_chunks: number }>('/rag/index/rebuild')
    message.success(`问答索引已重建：${data.indexed_files} 个文档，${data.indexed_chunks} 个片段`)
  } catch (e: any) {
    message.error(e.message || '重建问答索引失败')
  } finally {
    ragRebuilding.value = false
  }
}

const saveRagBackendSettings = async () => {
  await saveSetting('rag_retrieval_backend', ragBackend.value, { silent: true })
  await saveSetting('lightrag_base_url', lightragBaseUrl.value, { silent: true })
  await saveSetting('lightrag_api_key', lightragApiKey.value, { silent: true })
  await saveSetting('lightrag_timeout_seconds', lightragTimeoutSeconds.value, { silent: true })
  await saveSetting('lightrag_enable_remote_rebuild', lightragEnableRemoteRebuild.value ? 'true' : 'false', { silent: true })
  await saveSetting('lightrag_enable_remote_ask', lightragEnableRemoteAsk.value ? 'true' : 'false', { silent: true })
  message.success('RAG 后端配置已保存')
}

const resetRagBackendSettings = () => {
  ragBackend.value = ragBackendDefault.value
  lightragBaseUrl.value = lightragBaseUrlDefault.value
  lightragApiKey.value = lightragApiKeyDefault.value
  lightragTimeoutSeconds.value = lightragTimeoutDefault.value
  lightragEnableRemoteRebuild.value = lightragEnableRemoteRebuildDefault.value
  lightragEnableRemoteAsk.value = lightragEnableRemoteAskDefault.value
}

const runLightRagTest = async () => {
  lightragStatus.value = 'testing'
  lightragMessage.value = '正在测试 LightRAG 连通性...'
  try {
    const data = await post('/settings/test/lightrag')
    lightragStatus.value = data.status === 'success' ? 'success' : 'error'
    lightragMessage.value = data.message
  } catch (e: any) {
    lightragStatus.value = 'error'
    lightragMessage.value = e.message || '测试请求失败'
  }
}

const testLightRag = async () => {
  await saveRagBackendSettings()
  await runLightRagTest()
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

const testHermes = async () => {
  await saveSetting('hermes_cli_path', hermesPath.value)
  await runHermesTest()
}

const resetHermes = () => {
  hermesPath.value = hermesDefault.value
}

onMounted(async () => {
  await fetchSettings()
  // 页面加载时自动执行一次静默检查
  if (hermesPath.value) runHermesTest()
})
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
            <n-input v-model:value="wikiRoot" placeholder="例如: /Users/yolanda/Documents/Wiki" />
            <template #feedback>
              生成的 Markdown 文件将存放在此目录下。修改后即时生效。
            </template>
          </n-form-item>
          
          <n-space style="margin-top: 16px;">
            <n-button type="primary" @click="handleSaveWikiRoot">
              <template #icon><n-icon><FolderOpenOutline /></n-icon></template>
              保存路径
            </n-button>
            <n-button @click="resetWikiRoot">
              <template #icon><n-icon><RefreshOutline /></n-icon></template>
              恢复默认值
            </n-button>
          </n-space>
        </n-form>
      </n-card>

      <n-card title="问答索引维护" class="setting-card">
        <n-form label-placement="top">
          <n-form-item label="重建问答索引">
            <template #feedback>
              首次启用知识问答、批量外部修改 Wiki 文档或怀疑索引异常时，手动执行一次全量重建。
            </template>
            <n-space>
              <n-button type="primary" secondary :loading="ragRebuilding" @click="rebuildRagIndex">
                <template #icon><n-icon><FlashOutline /></n-icon></template>
                重建问答索引
              </n-button>
            </n-space>
          </n-form-item>
        </n-form>
      </n-card>

      <n-card title="RAG 检索后端" class="setting-card">
        <template #header-extra>
          <n-tag :type="lightragStatus === 'success' ? 'success' : (lightragStatus === 'error' ? 'error' : 'default')" round>
            <template #icon>
              <n-icon v-if="lightragStatus === 'success'"><CheckmarkCircleOutline /></n-icon>
              <n-icon v-else-if="lightragStatus === 'error'"><CloseCircleOutline /></n-icon>
            </template>
            {{ lightragStatus === 'success' ? 'LightRAG 可用' : (lightragStatus === 'error' ? 'LightRAG 异常' : '未测试') }}
          </n-tag>
        </template>

        <n-form label-placement="top">
          <n-form-item label="当前检索后端">
            <n-select v-model:value="ragBackend" :options="ragBackendOptions" />
            <template #feedback>
              业务接口保持不变，后端可在本地兼容实现与真实 LightRAG 之间切换。
            </template>
          </n-form-item>

          <n-form-item label="LightRAG 服务地址">
            <n-input v-model:value="lightragBaseUrl" placeholder="例如: http://127.0.0.1:9621" />
          </n-form-item>

          <n-form-item label="LightRAG API Key（可选）">
            <n-input v-model:value="lightragApiKey" type="password" show-password-on="click" placeholder="Bearer Token" />
          </n-form-item>

          <n-form-item label="请求超时（秒）">
            <n-input v-model:value="lightragTimeoutSeconds" placeholder="20" />
          </n-form-item>

          <n-form-item label="索引操作同步到远端">
            <n-switch v-model:value="lightragEnableRemoteRebuild" />
            <template #feedback>
              开启后，重建索引、单文件更新和删除会同时尝试调用 LightRAG 远端索引接口。
            </template>
          </n-form-item>

          <n-form-item label="问答优先走远端 LightRAG">
            <n-switch v-model:value="lightragEnableRemoteAsk" />
            <template #feedback>
              开启后，`/rag/ask` 会优先调用远端 LightRAG `/ask`，失败时再回落到本地检索 + Hermes。
            </template>
          </n-form-item>

          <div v-if="lightragMessage" class="test-message" :class="lightragStatus">
            {{ lightragMessage }}
          </div>

          <n-space style="margin-top: 16px;">
            <n-button type="primary" @click="saveRagBackendSettings">
              <template #icon><n-icon><BuildOutline /></n-icon></template>
              保存配置
            </n-button>
            <n-button secondary @click="testLightRag">
              <template #icon><n-icon><FlashOutline /></n-icon></template>
              测试 LightRAG
            </n-button>
            <n-button @click="resetRagBackendSettings">
              <template #icon><n-icon><RefreshOutline /></n-icon></template>
              恢复默认值
            </n-button>
          </n-space>
        </n-form>
      </n-card>

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
            <n-button @click="resetHermes">
              <template #icon><n-icon><RefreshOutline /></n-icon></template>
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

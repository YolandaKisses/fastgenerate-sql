<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NSpace, NText, NButton, NIcon, NLayout, NLayoutSider, NLayoutContent, useMessage } from 'naive-ui'
import DataSourceList from './components/DataSourceList.vue'
import DataSourceForm from './components/DataSourceForm.vue'

const message = useMessage()
const sources = ref<any[]>([])
const selectedSource = ref<any | null>(null)

const fetchSources = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/datasources/')
    if (res.ok) {
      sources.value = await res.json()
      // 如果当前没有选中的项，且列表不为空，则默认选中第一项
      if (sources.value.length > 0 && !selectedSource.value) {
        selectedSource.value = { ...sources.value[0] }
      }
    }
  } catch (error) {
    message.error('无法连接到后端服务')
  }
}

onMounted(() => {
  fetchSources()
})

const handleSelect = (source: any) => {
  selectedSource.value = { ...source }
}

const handleCreateNew = () => {
  selectedSource.value = {
    name: 'New_Connection',
    db_type: 'mysql',
    host: '127.0.0.1',
    port: 3306,
    database: '',
    username: 'root',
    password: ''
  }
}

const handleSave = async (data: any) => {
  try {
    const url = data.id ? `http://127.0.0.1:8000/api/v1/datasources/${data.id}` : 'http://127.0.0.1:8000/api/v1/datasources/'
    const method = data.id ? 'PATCH' : 'POST'
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    
    if (res.ok) {
      message.success('保存成功')
      await fetchSources()
      if (!data.id) {
        const newSource = await res.json()
        selectedSource.value = newSource
      }
    } else {
      const errorData = await res.json()
      message.error(`保存失败: ${errorData.detail || '未知错误'}`)
    }
  } catch (error) {
    message.error('请求失败')
  }
}

const handleTest = async (id: number | null) => {
  if (!id) {
    message.warning('请先保存后再测试连接')
    return
  }
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/datasources/${id}/test`, { method: 'POST' })
    const data = await res.json()
    if (data.success) {
      message.success(data.message || '连接测试成功')
    } else {
      message.error(data.message || '连接测试失败')
    }
    await fetchSources()
  } catch (error) {
    message.error('请求失败')
  }
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header" style="margin-bottom: 24px;">
      <div>
        <h1 class="page-title">数据源配置</h1>
        <p class="page-subtitle">配置您的数据库连接。连接成功不等于可问答，只有同步成功后才允许进入工作台问答流程。</p>
      </div>
    </div>

    <n-layout has-sider class="ds-layout" style="background: transparent;">
      <n-layout-sider width="320" style="background: transparent; margin-right: 24px;">
        <n-card class="list-card" content-style="padding: 0;">
          <template #header>
            <n-space justify="space-between" align="center" style="width: 100%;">
              <n-text depth="3" style="font-size: 12px; text-transform: uppercase; font-weight: 600;">连接列表</n-text>
              <n-button text type="primary" size="small" @click="handleCreateNew">
                <template #icon>
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                </template>
                新建连接
              </n-button>
            </n-space>
          </template>
          <div class="list-container">
            <DataSourceList :sources="sources" :selected-source="selectedSource" @select="handleSelect" />
          </div>
        </n-card>
      </n-layout-sider>

      <n-layout-content style="background: transparent;">
        <n-card class="form-card">
          <DataSourceForm :source-data="selectedSource" @save="handleSave" @test="handleTest" />
        </n-card>
      </n-layout-content>
    </n-layout>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 28px;
  margin: 0 0 8px 0;
  color: #181c22;
}

.page-subtitle {
  font-size: 14px;
  line-height: 22px;
  color: #717785;
  margin: 0;
}

.ds-layout {
  flex: 1;
}

::v-deep(.n-layout-scroll-container) {
  display: flex;
  flex-direction: column;
}

.list-card, .form-card {
  border-radius: 8px;
  border: 1px solid #efeff5;
  box-shadow: none;
  background: #ffffff;
  height: 100%;
}

.list-container {
  padding: 8px;
}
</style>

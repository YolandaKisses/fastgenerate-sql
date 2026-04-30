<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NText, NButton, NIcon, useDialog, useMessage } from 'naive-ui'
import DataSourceList from './components/DataSourceList.vue'
import DataSourceForm from './components/DataSourceForm.vue'
import { del, get, patch, post } from '../../services/request'

const message = useMessage()
const dialog = useDialog()
const sources = ref<any[]>([])
const selectedSource = ref<any | null>({
  name: 'New_Connection',
  db_type: 'mysql',
  host: '127.0.0.1',
  port: 3306,
  database: '',
  username: 'root',
  password: ''
})

const fetchSources = async () => {
  try {
    sources.value = await get('/datasources/')
    if (sources.value.length > 0 && !selectedSource.value) {
      selectedSource.value = { ...sources.value[0] }
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
    const saved = data.id
      ? await patch(`/datasources/${data.id}`, data)
      : await post('/datasources/', data)
    message.success('保存成功')
    await fetchSources()
    if (!data.id) {
      selectedSource.value = saved
    }
  } catch (error: any) {
    message.error(`保存失败: ${error.message || '请求失败'}`)
  }
}

const handleTest = async (id: number | null) => {
  if (!id) {
    message.warning('请先保存后再测试连接')
    return
  }
  try {
    const data = await post(`/datasources/${id}/test`)
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

const handleDelete = async (id: number | null) => {
  if (!id) return
  dialog.warning({
    title: '确认删除数据源',
    content: '删除后，相关 Schema 和补充备注会一起清理，历史审计日志会保留。确定继续吗？',
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const data = await del(`/datasources/${id}`)
        if (data.success) {
          message.success('数据源已删除')
          selectedSource.value = null
          await fetchSources()
        } else {
          message.error(data.message || '删除失败')
        }
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div class="header-content">
        <div>
          <h1 class="page-title">数据源配置</h1>
          <p class="page-subtitle">配置您的数据库连接。连接测试通过后即可进入工作台问答流程。</p>
        </div>
      </div>
    </div>

    <div class="ds-container">
      <div class="sider-panel">
        <div class="panel-header">
          <n-text depth="3" class="panel-tag">连接列表</n-text>
          <n-button quaternary size="small" type="primary" @click="handleCreateNew">
            <template #icon>
              <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg></n-icon>
            </template>
            新建连接
          </n-button>
        </div>
        <div class="list-wrapper">
          <DataSourceList :sources="sources" :selected-source="selectedSource" @select="handleSelect" />
        </div>
      </div>

      <div class="main-panel">
        <n-card class="form-card" :bordered="true">
          <DataSourceForm :source-data="selectedSource" @save="handleSave" @test="handleTest" @delete="handleDelete" />
        </n-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
  overflow: hidden;
}

.header-content {
  margin-bottom: 24px;
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

.ds-container {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 24px;
}

.sider-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #efeff5;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid #efeff5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f9fafb;
}

.panel-tag {
  font-size: 11px;
  font-weight: 600;
  color: #8c92a0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.list-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.form-card {
  border-radius: 12px;
  border-color: #efeff5;
  box-shadow: none;
  height: 100%;
}
</style>

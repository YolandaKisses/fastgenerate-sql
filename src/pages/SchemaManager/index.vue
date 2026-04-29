<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NLayout, NLayoutSider, NLayoutContent, NSelect, NSpace, NText, useMessage } from 'naive-ui'
import TableList from './components/TableList.vue'
import SchemaEditor from './components/SchemaEditor.vue'

const message = useMessage()
const currentSource = ref<number | null>(null)
const sourceOptions = ref<{label: string, value: number}[]>([])
const tables = ref<any[]>([])
const selectedTable = ref<any | null>(null)

const fetchSources = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/datasources/')
    if (res.ok) {
      const data = await res.json()
      sourceOptions.value = data.map((ds: any) => ({
        label: `${ds.name} (${ds.db_type})`,
        value: ds.id
      }))
      if (data.length > 0 && !currentSource.value) {
        currentSource.value = data[0].id
      }
    }
  } catch (error) {
    message.error('无法加载数据源')
  }
}

const fetchTables = async (dsId: number) => {
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/tables/${dsId}`)
    if (res.ok) {
      tables.value = await res.json()
      if (tables.value.length > 0) {
        selectedTable.value = tables.value[0]
      } else {
        selectedTable.value = null
      }
    }
  } catch (error) {
    message.error('无法加载表结构')
  }
}

watch(currentSource, (newVal) => {
  if (newVal) {
    fetchTables(newVal)
  }
})

onMounted(() => {
  fetchSources()
})

const handleSelectTable = (table: any) => {
  selectedTable.value = table
}

const handleSync = async () => {
  if (!currentSource.value) return
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/schema/sync/${currentSource.value}`, { method: 'POST' })
    const data = await res.json()
    if (data.success) {
      message.success(data.message)
      fetchTables(currentSource.value)
    } else {
      message.error(data.message)
    }
  } catch (error) {
    message.error('同步请求失败')
  }
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header" style="margin-bottom: 24px;">
      <n-space justify="space-between" align="start">
        <div>
          <h1 class="page-title">Schema 与备注管理</h1>
          <p class="page-subtitle">管理同步回来的数据库元数据，并添加本地补充备注以提升 AI 问答的准确性。</p>
        </div>
        <n-select :options="sourceOptions" v-model:value="currentSource" style="width: 280px;" placeholder="选择数据源" />
      </n-space>
    </div>

    <n-layout has-sider class="schema-layout" style="background: transparent;">
      <n-layout-sider :width="280" style="background: transparent; margin-right: 24px;">
        <TableList :tables="tables" :selected-table="selectedTable" @select="handleSelectTable" />
      </n-layout-sider>

      <n-layout-content style="background: transparent;">
        <SchemaEditor :table="selectedTable" @sync="handleSync" />
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

.schema-layout {
  flex: 1;
}

::v-deep(.n-layout-scroll-container) {
  display: flex;
  flex-direction: column;
}
</style>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from "vue";
import {
  NEmpty,
  NSpin,
  NCard,
  NTag,
  NSpace,
  NIcon,
  NButton,
  NTooltip,
  NScrollbar,
  NBreadcrumb,
  NBreadcrumbItem,
} from "naive-ui";
import {
  GitNetworkOutline,
  ArrowForwardOutline,
  CubeOutline,
  CodeSlashOutline,
  EyeOutline,
  GridOutline,
  ChevronForwardOutline,
} from "@vicons/ionicons5";
import { get } from "../../../services/request";

const props = defineProps({
  datasourceId: { type: Number, required: true },
  initialObject: { type: Object, default: null }, // { type: 'table' | 'view' | 'routine', name: string }
});

const emit = defineEmits(["select-object"]);

const loading = ref(false);
const lineageData = ref<any>(null);
const history = ref<any[]>([]);

const currentObject = ref<{ type: string; name: string } | null>(
  props.initialObject
    ? { type: props.initialObject.type, name: props.initialObject.name }
    : null,
);

const fetchLineage = async (type: string, name: string) => {
  if (!props.datasourceId) return;
  loading.value = true;
  try {
    let endpoint = "";
    if (type === "table") {
      endpoint = `/lineage/table/${props.datasourceId}/${name}`;
    } else if (type === "view") {
      endpoint = `/lineage/view/${props.datasourceId}/${name}`;
    } else if (type === "routine") {
      endpoint = `/lineage/routine/${props.datasourceId}/${name}`;
    }

    const data = await get(endpoint);
    lineageData.value = data;
  } catch (error) {
    console.error("Failed to fetch lineage:", error);
    lineageData.value = null;
  } finally {
    loading.value = false;
  }
};

const handleNavigate = (type: string, name: string) => {
  if (currentObject.value) {
    history.value.push({ ...currentObject.value });
  }
  currentObject.value = { type, name };
};

const goBack = () => {
  if (history.value.length > 0) {
    const prev = history.value.pop();
    currentObject.value = prev;
  }
};

const resetLineage = (obj: { type: string; name: string }) => {
  history.value = [];
  currentObject.value = { ...obj };
};

watch(
  () => currentObject.value,
  (newVal) => {
    if (newVal) {
      fetchLineage(newVal.type, newVal.name);
    }
  },
  { deep: true },
);

watch(
  () => props.initialObject,
  (newVal) => {
    if (newVal) {
      resetLineage(newVal);
    }
  },
);

onMounted(() => {
  if (currentObject.value) {
    fetchLineage(currentObject.value.type, currentObject.value.name);
  }
});

const getIcon = (type: string) => {
  if (type === "table") return GridOutline;
  if (type === "view") return EyeOutline;
  if (type === "routine") return CodeSlashOutline;
  return CubeOutline;
};

const getTypeLabel = (type: string) => {
  if (type === "table") return "表";
  if (type === "view") return "视图";
  if (type === "routine") return "存储过程";
  return "对象";
};

defineExpose({ resetLineage });
</script>

<template>
  <div class="lineage-explorer">
    <div class="explorer-header">
      <div class="header-left">
        <n-button v-if="history.length > 0" size="small" quaternary @click="goBack">
          <template #icon><n-icon><ChevronForwardOutline style="transform: rotate(180deg)" /></n-icon></template>
          返回
        </n-button>
        <n-breadcrumb separator=">">
          <n-breadcrumb-item>
            <n-space align="center" :size="4">
              <n-icon><GitNetworkOutline /></n-icon>
              <span>血缘追踪</span>
            </n-space>
          </n-breadcrumb-item>
          <n-breadcrumb-item v-if="currentObject">
            <n-space align="center" :size="4">
              <n-icon :component="getIcon(currentObject.type)" />
              <span>{{ currentObject.name }}</span>
            </n-space>
          </n-breadcrumb-item>
        </n-breadcrumb>
      </div>
      <div class="header-right">
        <n-tag v-if="lineageData?.lineage_status" :type="(lineageData.lineage_status === 'success' || lineageData.lineage_status === 'parsed') ? 'success' : 'warning'" size="small">
          解析状态: {{ (lineageData.lineage_status === 'success' || lineageData.lineage_status === 'parsed') ? '正常' : '异常' }}
        </n-tag>
      </div>
    </div>

    <div class="explorer-body">
      <n-spin :show="loading">
        <div v-if="lineageData" class="lineage-visual">
          <!-- Horizontal Layout: Upstream -> Current -> Downstream -->
          <div class="lineage-stage upstream">
            <div class="stage-label">上游依赖</div>
            <n-scrollbar style="max-height: 100%">
              <div class="node-column">
                <template v-if="currentObject?.type === 'table'">
                   <n-card
                    v-for="item in lineageData.upstream_tables"
                    :key="item"
                    class="node-card clickable"
                    size="small"
                    @click="handleNavigate('table', item)"
                  >
                    <div class="node-content">
                      <n-icon :component="GridOutline" />
                      <span class="node-name">{{ item }}</span>
                    </div>
                  </n-card>
                  <div v-if="!lineageData.upstream_tables?.length" class="empty-node">无上游表</div>
                </template>
                <template v-else>
                   <n-card
                    v-for="item in lineageData.reads"
                    :key="item"
                    class="node-card clickable"
                    size="small"
                    @click="handleNavigate('table', item)"
                  >
                    <div class="node-content">
                      <n-icon :component="GridOutline" />
                      <span class="node-name">{{ item }}</span>
                    </div>
                  </n-card>
                  <div v-if="!lineageData.reads?.length" class="empty-node">无读取对象</div>
                </template>
              </div>
            </n-scrollbar>
          </div>

          <div class="lineage-arrow">
            <n-icon size="24" color="#d1d5db"><ArrowForwardOutline /></n-icon>
          </div>

          <div class="lineage-stage current">
            <div class="stage-label">当前对象</div>
            <div class="node-column">
              <n-card class="node-card active" size="medium">
                <div class="node-content-main">
                  <div class="node-type-tag">{{ getTypeLabel(currentObject?.type || '') }}</div>
                  <n-icon :component="getIcon(currentObject?.type || '')" size="32" class="node-main-icon" />
                  <div class="node-name-main">{{ currentObject?.name }}</div>
                  <div v-if="lineageData.lineage_message" class="node-status-msg">
                    {{ lineageData.lineage_message }}
                  </div>
                </div>
              </n-card>

              <!-- Related Side Objects for Tables -->
              <template v-if="currentObject?.type === 'table'">
                <div class="side-objects" v-if="lineageData.related_views?.length || lineageData.related_routines?.length">
                   <div class="side-label">关联视图 / 过程</div>
                   <div class="side-grid">
                      <n-tooltip v-for="v in lineageData.related_views" :key="v.name" trigger="hover">
                        <template #trigger>
                          <div class="side-item view" @click="handleNavigate('view', v.name)">
                            <n-icon :component="EyeOutline" />
                          </div>
                        </template>
                        视图: {{ v.name }}
                      </n-tooltip>
                      <n-tooltip v-for="r in lineageData.related_routines" :key="r.name" trigger="hover">
                        <template #trigger>
                          <div class="side-item routine" @click="handleNavigate('routine', r.name)">
                            <n-icon :component="CodeSlashOutline" />
                          </div>
                        </template>
                        {{ r.routine_type }}: {{ r.name }}
                      </n-tooltip>
                   </div>
                </div>
              </template>
            </div>
          </div>

          <div class="lineage-arrow">
            <n-icon size="24" color="#d1d5db"><ArrowForwardOutline /></n-icon>
          </div>

          <div class="lineage-stage downstream">
            <div class="stage-label">下游影响</div>
            <n-scrollbar style="max-height: 100%">
              <div class="node-column">
                <template v-if="currentObject?.type === 'table'">
                   <n-card
                    v-for="item in lineageData.downstream_tables"
                    :key="item"
                    class="node-card clickable"
                    size="small"
                    @click="handleNavigate('table', item)"
                  >
                    <div class="node-content">
                      <n-icon :component="GridOutline" />
                      <span class="node-name">{{ item }}</span>
                    </div>
                  </n-card>
                  <div v-if="!lineageData.downstream_tables?.length" class="empty-node">无下游影响</div>
                </template>
                <template v-else-if="currentObject?.type === 'routine'">
                   <n-card
                    v-for="item in lineageData.writes"
                    :key="item"
                    class="node-card clickable"
                    size="small"
                    @click="handleNavigate('table', item)"
                  >
                    <div class="node-content">
                      <n-icon :component="GridOutline" />
                      <span class="node-name">{{ item }}</span>
                    </div>
                  </n-card>
                  <div v-if="!lineageData.writes?.length" class="empty-node">无写入对象</div>
                </template>
                <template v-else>
                   <div class="empty-node">视图暂无下游追踪</div>
                </template>
              </div>
            </n-scrollbar>
          </div>
        </div>
        <div v-else-if="!loading" class="empty-state">
           <n-empty description="暂未选择追踪对象或未发现血缘信息">
            <template #extra>
              <div class="empty-tip">请在“表结构”、“视图”或“存储过程”页选择对象并点击“查看血缘”</div>
            </template>
           </n-empty>
        </div>
      </n-spin>
    </div>
  </div>
</template>

<style scoped>
.lineage-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f9fafb;
}

.explorer-header {
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.explorer-body {
  flex: 1;
  min-height: 0;
  padding: 24px;
  overflow: hidden;
}

.lineage-visual {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
}

.lineage-stage {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 200px;
  max-width: 320px;
}

.stage-label {
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.node-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px;
}

.node-card {
  border-radius: 12px;
  transition: all 0.2s;
  border: 1px solid #e5e7eb;
}

.node-card.clickable:hover {
  cursor: pointer;
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
  transform: translateY(-2px);
}

.node-card.active {
  border-color: #3b82f6;
  background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
}

.node-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.node-name {
  font-family: "JetBrains Mono", monospace;
  font-size: 13px;
  color: #374151;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-content-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  text-align: center;
}

.node-type-tag {
  font-size: 10px;
  font-weight: 700;
  background: #3b82f6;
  color: #fff;
  padding: 2px 8px;
  border-radius: 10px;
  margin-bottom: 12px;
  text-transform: uppercase;
}

.node-main-icon {
  color: #3b82f6;
  margin-bottom: 12px;
}

.node-name-main {
  font-family: "JetBrains Mono", monospace;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  word-break: break-all;
}

.node-status-msg {
  margin-top: 12px;
  font-size: 11px;
  color: #9ca3af;
  font-style: italic;
}

.empty-node {
  text-align: center;
  padding: 20px;
  color: #9ca3af;
  font-size: 12px;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
}

.lineage-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
}

.side-objects {
  margin-top: 12px;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}

.side-label {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 8px;
  text-align: center;
}

.side-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.side-item {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: #f3f4f6;
}

.side-item:hover {
  transform: scale(1.1);
}

.side-item.view {
  color: #10b981;
  background: #ecfdf5;
}

.side-item.routine {
  color: #8b5cf6;
  background: #f5f3ff;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-tip {
  color: #9ca3af;
  font-size: 13px;
}
</style>

<script setup lang="ts">
import { ref, watch, onMounted, computed, type PropType } from "vue";
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
  NText,
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
  initialObject: {
    type: Object as PropType<{ type: string; name: string } | null>,
    default: null,
  },
});

const emit = defineEmits(["select-object"]);

const loading = ref(false);
const lineageData = ref<any>(null);
const history = ref<any[]>([]);

// Canvas Dragging State
const isDragging = ref(false);
const startPos = ref({ x: 0, y: 0 });
const offset = ref({ x: 0, y: 0 });

const visualStyle = computed(() => ({
  transform: `translate(${offset.value.x}px, ${offset.value.y}px)`,
}));

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

// Canvas Dragging Handlers
const handleMouseDown = (e: MouseEvent) => {
  // Ignore clicks on interactive elements
  if ((e.target as HTMLElement).closest(".node-card, .n-button, .n-scrollbar")) return;
  
  isDragging.value = true;
  startPos.value = { x: e.clientX - offset.value.x, y: e.clientY - offset.value.y };
};

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging.value) return;
  offset.value = {
    x: e.clientX - startPos.value.x,
    y: e.clientY - startPos.value.y,
  };
};

const stopDragging = () => {
  isDragging.value = false;
};

const resetCanvas = () => {
  offset.value = { x: 0, y: 0 };
};

watch(
  () => currentObject.value,
  (newVal) => {
    if (newVal) {
      fetchLineage(newVal.type, newVal.name);
      resetCanvas();
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
      <n-spin :show="loading" content-style="height: 100%">
        <div 
          v-if="lineageData" 
          class="lineage-canvas"
          :class="{ dragging: isDragging }"
          @mousedown="handleMouseDown"
          @mousemove="handleMouseMove"
          @mouseup="stopDragging"
          @mouseleave="stopDragging"
        >
          <div class="lineage-visual" :style="visualStyle">
            <!-- Horizontal Layout: Upstream -> Current -> Downstream -->
            <div class="lineage-stage upstream">
              <div class="stage-label">上游依赖</div>
              <n-scrollbar class="stage-scrollbar">
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
                  <n-card class="related-card" size="small">
                    <div class="stage-label">关联视图 / 过程</div>
                    <n-scrollbar style="max-height: 200px">
                      <div class="related-list-vertical">
                        <template v-if="lineageData.related_views?.length || lineageData.related_routines?.length">
                          <div
                            v-for="v in lineageData.related_views"
                            :key="v.name"
                            class="related-item clickable"
                            @click="handleNavigate('view', v.name)"
                            :title="'视图: ' + v.name"
                          >
                            <n-icon :component="EyeOutline" class="related-icon view" />
                            <span class="related-name">{{ v.name }}</span>
                          </div>
                          <div
                            v-for="r in lineageData.related_routines"
                            :key="r.name"
                            class="related-item clickable"
                            @click="handleNavigate('routine', r.name)"
                            :title="r.routine_type + ': ' + r.name"
                          >
                            <n-icon :component="CodeSlashOutline" class="related-icon routine" />
                            <span class="related-name">{{ r.name }}</span>
                          </div>
                        </template>
                        <n-text v-else depth="3" class="related-empty">暂无关联</n-text>
                      </div>
                    </n-scrollbar>
                  </n-card>
                </template>
              </div>
            </div>

            <div class="lineage-arrow">
              <n-icon size="24" color="#d1d5db"><ArrowForwardOutline /></n-icon>
            </div>

            <div class="lineage-stage downstream">
              <div class="stage-label">下游影响</div>
              <n-scrollbar class="stage-scrollbar">
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

.lineage-canvas {
  height: 100%;
  width: 100%;
  overflow: hidden;
  cursor: grab;
  user-select: none;
}

.lineage-canvas.dragging {
  cursor: grabbing;
}

.lineage-visual {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 100%;
  min-height: 100%;
  padding: 40px;
  gap: 32px;
  transition: transform 0.05s linear;
}

.lineage-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 280px;
  max-width: 360px;
}

.stage-scrollbar {
  flex: 1;
  min-height: 0;
}

.stage-label {
  text-align: center;
  font-size: 13px;
  font-weight: 700;
  color: #374151;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.node-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px 4px;
}

.node-card {
  border-radius: 12px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid #e5e7eb;
  background: #fff;
}

.node-card.clickable:hover {
  cursor: pointer;
  border-color: #3b82f6;
  background-color: #f0f9ff;
  transform: translateX(4px);
}

.node-card.active {
  border-color: #3b82f6;
  background: #eff6ff;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.node-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.node-name {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  color: #4b5563;
  word-break: break-all;
}

.node-content-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0;
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
}

.node-main-icon {
  color: #3b82f6;
  margin-bottom: 8px;
}

.node-name-main {
  font-family: "JetBrains Mono", monospace;
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  word-break: break-all;
}

.node-status-msg {
  margin-top: 12px;
  font-size: 11px;
  color: #9ca3af;
}

.empty-node {
  text-align: center;
  padding: 20px;
  color: #9ca3af;
  font-size: 12px;
  border: 1px dashed #e5e7eb;
  border-radius: 8px;
}

.lineage-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.5;
}

.related-card {
  margin-top: 16px;
  background: #f9fafb;
}

.related-list-vertical {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px;
}

.related-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e5e7eb;
  transition: all 0.2s;
}

.related-item.clickable:hover {
  cursor: pointer;
  border-color: #3b82f6;
  background: #eff6ff;
}

.related-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.related-icon.view {
  color: #10b981;
}

.related-icon.routine {
  color: #8b5cf6;
}

.related-name {
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  color: #4b5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.related-empty {
  font-size: 12px;
  text-align: center;
  display: block;
  padding: 12px 0;
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

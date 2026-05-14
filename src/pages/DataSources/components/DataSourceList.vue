<script setup lang="ts">
import { NList, NListItem, NTag, NText, NEmpty } from "naive-ui";
import { ServerOutline } from "@vicons/ionicons5";
import { NIcon } from "naive-ui";

const props = defineProps<{
  sources: Array<{
    id: number;
    name: string;
    db_type: string;
    status: string;
    host?: string | null;
    sync_status?: string;
    source_mode?: string;
    source_status?: string;
    source_message?: string | null;
  }>;
  selectedSource?: any | null;
}>();

const emit = defineEmits(["select"]);

const getStatusType = (status: string) => {
  switch (status) {
    case "connection_ok":
      return "success";
    case "draft":
      return "default";
    case "stale":
      return "warning";
    case "connection_failed":
    case "sync_failed":
      return "error";
    default:
      return "default";
  }
};

const getSyncStatusType = (status?: string) => {
  switch (status) {
    case "sync_success":
      return "success";
    case "sync_partial_success":
      return "warning";
    case "sync_failed":
      return "error";
    case "syncing":
      return "info";
    default:
      return "default";
  }
};

const getStatusLabel = (status: string) => {
  switch (status) {
    case "connection_ok":
      return "连接正常";
    case "connection_failed":
      return "连接失败";
    case "draft":
      return "草稿";
    case "stale":
      return "已过期";
    default:
      return status;
  }
};

const getSyncStatusLabel = (status?: string) => {
  switch (status) {
    case "sync_success":
      return "同步成功";
    case "sync_partial_success":
      return "部分成功";
    case "sync_failed":
      return "同步失败";
    case "syncing":
      return "同步中";
    case "never_synced":
      return "未同步";
    default:
      return status || "未同步";
  }
};

const getSourceModeLabel = (mode?: string) =>
  mode === "sql_file" ? "文件型" : "连接型";

const getSourceStatusLabel = (status?: string) => {
  switch (status) {
    case "connection_ok":
      return "连接正常";
    case "file_uploaded":
      return "已上传";
    case "parse_success":
      return "已解析";
    case "parse_failed":
      return "解析失败";
    case "syncing":
      return "同步中";
    case "sync_failed":
      return "失败";
    default:
      return "草稿";
  }
};

const getSourceStatusType = (status?: string) => {
  switch (status) {
    case "connection_ok":
    case "parse_success":
      return "success";
    case "file_uploaded":
    case "syncing":
      return "info";
    case "parse_failed":
    case "sync_failed":
      return "error";
    default:
      return "default";
  }
};

</script>

<template>
  <div v-if="sources.length === 0" class="empty-list-container">
    <n-empty
      :description="selectedSource ? '正在配置新连接' : '暂无数据源连接'"
      size="large"
    >
      <template #icon>
        <n-icon>
          <ServerOutline />
        </n-icon>
      </template>
      <template #extra v-if="!selectedSource">
        <n-text depth="3" class="empty-tip">
          点击右上角“新建连接”开始配置
        </n-text>
      </template>
    </n-empty>
  </div>
  <n-list v-else hoverable clickable class="source-list">
    <n-list-item
      v-for="source in sources"
      :key="source.id"
      :class="{ 'selected-item': selectedSource?.id === source.id }"
      @click="emit('select', source)"
    >
      <div class="source-row">
        <div class="icon-box" :class="`type-${source.db_type.toLowerCase()}`">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
          </svg>
        </div>
        <div class="meta-content">
          <n-text strong class="source-name">{{ source.name }}</n-text>
          <div class="status-tags">
            <n-tag size="small" round :bordered="false" class="status-tag">
              {{ getSourceModeLabel(source.source_mode) }}
            </n-tag>

            <!-- 仅在非草稿时，或两者皆为草稿时显示配置状态 -->
            <n-tag
              v-if="
                source.source_status !== 'draft' || source.status === 'draft'
              "
              :type="getSourceStatusType(source.source_status)"
              size="small"
              round
              :bordered="false"
              class="status-tag"
            >
              {{ getSourceStatusLabel(source.source_status) }}
            </n-tag>

            <!-- 仅在非草稿时显示连接状态（避免在文件模式下出现冗余草稿） -->
            <n-tag
              v-if="source.status !== 'draft'"
              :type="getStatusType(source.status)"
              size="small"
              round
              :bordered="false"
              class="status-tag"
            >
              {{ getStatusLabel(source.status) }}
            </n-tag>

            <n-tag
              v-if="source.sync_status"
              :type="getSyncStatusType(source.sync_status)"
              size="small"
              round
              :bordered="false"
              class="status-tag"
            >
              {{ getSyncStatusLabel(source.sync_status) }}
            </n-tag>
          </div>
          <n-text
            v-if="
              source.source_message &&
              source.source_status !== 'parse_success'
            "
            depth="3"
            class="source-message"
          >
            {{ source.source_message }}
          </n-text>
        </div>
      </div>
    </n-list-item>
  </n-list>
</template>

<style scoped>
.empty-list-container {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.empty-tip {
  font-size: 13px;
}

.source-list {
  background: transparent;
}

.n-list-item {
  margin: 0 0 10px 0;
  border-radius: 18px !important;
  transition: all 0.2s ease;
  padding: 18px 20px !important;
  border: 1px solid #e8edf5 !important;
  background: #ffffff !important;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.source-row {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-width: 0;
  min-height: 88px;
}

.n-list-item:hover {
  border-color: #d7deea !important;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  transform: translateY(-1px);
}

.selected-item {
  border-color: #bfd4fb !important;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%) !important;
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.1);
}

.icon-box {
  width: 46px;
  height: 46px;
  background-color: #f8fafc;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4b5563;
  flex-shrink: 0;
  transition: all 0.2s ease;
  border: 1px solid #edf1f6;
}

.selected-item .icon-box {
  background-color: #eff6ff;
  color: #2563eb;
  border-color: #dbeafe;
}

.type-mysql {
  color: #0f766e;
  background-color: #f0fdfa;
}
.type-postgresql {
  color: #1d4ed8;
  background-color: #eff6ff;
}
.type-oracle {
  color: #dc2626;
  background-color: #fff4f4;
}

.meta-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  justify-content: center;
  flex: 1;
}

.source-name {
  font-size: 16px;
  line-height: 22px;
  color: #273244;
  transition: color 0.2s ease;
}

.selected-item .source-name {
  color: #1d4ed8;
}

.status-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.status-tag {
  font-size: 11px;
  font-weight: 600;
  height: 24px;
  line-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
}

.source-message {
  font-size: 12px;
  line-height: 18px;
  color: #748092;
}
</style>

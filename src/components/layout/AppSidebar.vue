<script setup lang="ts">
import { computed, h, Component, ref } from "vue";
import { NLayoutSider, NMenu, NAvatar, NIcon, useDialog } from "naive-ui";
import { useRoute, useRouter } from "vue-router";
import {
  HomeOutline,
  CloudOutline,
  LayersOutline,
  ListOutline,
  SettingsOutline,
  LogOutOutline,
} from "@vicons/ionicons5";
import appLogo from "../../assets/fastgenerate-sql-logo.png";
import { clearAuth, getCurrentUser } from "../../services/auth";

const route = useRoute();
const router = useRouter();
const dialog = useDialog();
const isCollapsed = ref(false);
const currentUser = computed(() => getCurrentUser());

const activeKey = computed(() => route.path);

function renderIcon(icon: Component) {
  return () => h(NIcon, null, { default: () => h(icon) });
}

const menuOptions = [
  {
    label: "工作台",
    key: "/workspace",
    icon: renderIcon(HomeOutline),
  },
  {
    label: "数据源配置",
    key: "/data-sources",
    icon: renderIcon(CloudOutline),
  },
  {
    label: "Schema 管理",
    key: "/schema",
    icon: renderIcon(LayersOutline),
  },
  {
    label: "审计日志",
    key: "/audit-logs",
    icon: renderIcon(ListOutline),
  },
  {
    label: "本地设置",
    key: "/settings",
    icon: renderIcon(SettingsOutline),
  },
];

const handleUpdateValue = (key: string) => {
  router.push(key);
};

const handleLogout = () => {
  dialog.warning({
    title: "确认退出",
    content: "您确定要退出当前账号吗？",
    positiveText: "确定退出",
    negativeText: "取消",
    onPositiveClick: () => {
      clearAuth();
      router.replace("/login");
    },
  });
};
</script>

<template>
  <n-layout-sider
    bordered
    :width="240"
    collapse-mode="width"
    :collapsed-width="64"
    show-trigger
    v-model:collapsed="isCollapsed"
    class="app-sider"
  >
    <div class="brand">
      <div class="brand-logo">
        <img :src="appLogo" alt="FastGenerate SQL logo" />
      </div>
      <div class="brand-info" v-if="!isCollapsed">
        <h1 class="brand-title">FastGenerate SQL</h1>
        <span class="version">v1.0.0</span>
      </div>
    </div>
    <n-menu
      :value="activeKey"
      :options="menuOptions"
      @update:value="handleUpdateValue"
      class="nav-menu"
      :indent="20"
      :collapsed-width="64"
      :collapsed-icon-size="22"
    />
    <div class="sidebar-footer">
      <div class="user-info" :class="{ 'is-collapsed': isCollapsed }">
        <n-avatar
          round
          size="medium"
          class="user-avatar"
        >
          {{ currentUser?.name?.slice(0, 1) || "管" }}
        </n-avatar>
        <div class="user-meta" v-if="!isCollapsed">
          <strong>{{ currentUser?.name || "系统管理员" }}</strong>
          <span>{{ currentUser?.account || "admin" }}</span>
        </div>
      </div>
      <button
        class="logout-button"
        :class="{ 'is-collapsed': isCollapsed }"
        type="button"
        :title="isCollapsed ? '退出登录' : ''"
        @click="handleLogout"
      >
        <n-icon :component="LogOutOutline" />
        <span class="logout-text" v-if="!isCollapsed">退出系统</span>
      </button>
    </div>
  </n-layout-sider>
</template>

<style scoped>
.app-sider {
  display: flex;
  flex-direction: column;
  background-color: #fbfcfd;
  height: 100vh;
  box-shadow: 1px 0 10px rgba(0, 0, 0, 0.02);
}

.brand {
  padding: 24px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
  transition: all 0.3s;
}

.brand-logo {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 8px rgba(32, 128, 240, 0.2);
  overflow: hidden;
}

.brand-logo img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.brand-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  white-space: nowrap;
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  color: #181c22;
  margin: 0;
  line-height: 1.2;
}

.version {
  color: #717785;
  font-size: 11px;
  font-weight: 500;
}

.nav-menu {
  flex: 1;
  padding-top: 8px;
}

.sidebar-footer {
  margin-top: auto;
  padding: 16px 12px;
  border-top: 1px solid #efeff5;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(251, 252, 253, 0.8);
}

.user-info {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.3s;
}

.user-info:hover {
  background: rgba(0, 0, 0, 0.03);
}

.user-info.is-collapsed {
  padding: 8px 4px;
  justify-content: center;
}

.user-avatar {
  background-color: #eef0fa;
  color: #2080f0;
  font-weight: bold;
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  white-space: nowrap;
}

.user-meta strong {
  font-size: 13px;
  color: #181c22;
  text-overflow: ellipsis;
  overflow: hidden;
}

.user-meta span {
  font-size: 11px;
  color: #717785;
  text-overflow: ellipsis;
  overflow: hidden;
}

.logout-button {
  width: 100%;
  height: 36px;
  border: 1px solid #efeff5;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #ffffff;
  color: #717785;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
  white-space: nowrap;
  overflow: hidden;
}

.logout-button.is-collapsed {
  width: 36px;
  margin: 0 auto;
  padding: 0;
}

.logout-text {
  font-weight: 500;
}

.logout-button:hover {
  color: #d03050;
  border-color: #f5c2c7;
  background: #fffafa;
}

/* Adjusting the border line to look cleaner */
:deep(.n-layout-sider--bordered) {
  border-right: 1px solid #efeff5 !important;
}
</style>

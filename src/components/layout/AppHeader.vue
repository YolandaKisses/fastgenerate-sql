<script setup lang="ts">
import { computed, h, Component } from "vue";
import { NLayoutHeader, NMenu, NAvatar, NIcon, useDialog } from "naive-ui";
import { useRoute, useRouter } from "vue-router";
import {
  CloudOutline,
  LayersOutline,
  SettingsOutline,
  LogOutOutline,
  BookOutline,
} from "@vicons/ionicons5";
import appLogo from "../../assets/fastgenerate-sql-logo.png";
import { clearAuth, getCurrentUser } from "../../services/auth";

const route = useRoute();
const router = useRouter();
const dialog = useDialog();
const currentUser = computed(() => getCurrentUser());

const activeKey = computed(() => route.path);

function renderIcon(icon: Component) {
  return () => h(NIcon, null, { default: () => h(icon) });
}

const menuOptions = [
  {
    label: "知识库 (Wiki)",
    key: "/wiki",
    icon: renderIcon(BookOutline),
  },
  {
    label: "元数据管理",
    key: "/schema",
    icon: renderIcon(LayersOutline),
  },
  {
    label: "数据源配置",
    key: "/data-sources",
    icon: renderIcon(CloudOutline),
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
  <n-layout-header bordered class="app-header">
    <div class="header-content">
      <div class="brand" @click="router.push('/')">
        <div class="brand-logo">
          <img :src="appLogo" alt="FastGenerate SQL logo" />
        </div>
        <div class="brand-info">
          <h1 class="brand-title">FastGenerate SQL</h1>
        </div>
      </div>

      <div class="nav-container">
        <n-menu
          mode="horizontal"
          :value="activeKey"
          :options="menuOptions"
          @update:value="handleUpdateValue"
          class="nav-menu"
        />
      </div>

      <div class="header-right">
        <div class="user-info">
          <n-avatar round size="small" class="user-avatar">
            {{ currentUser?.name?.slice(0, 1) || "管" }}
          </n-avatar>
          <div class="user-meta">
            <strong>{{ currentUser?.name || "管理员" }}</strong>
          </div>
        </div>

        <div class="divider"></div>

        <button
          class="logout-button"
          type="button"
          title="退出登录"
          @click="handleLogout"
        >
          <n-icon :component="LogOutOutline" />
          <span class="logout-text">退出</span>
        </button>
      </div>
    </div>
  </n-layout-header>
</template>

<style scoped>
.app-header {
  height: 64px;
  background-color: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  z-index: 1000;
  display: flex;
  align-items: center;
}

.header-content {
  width: 100%;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  flex-shrink: 0;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(32, 128, 240, 0.15);
  overflow: hidden;
}

.brand-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  color: #181c22;
  margin: 0;
  white-space: nowrap;
}

.nav-container {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 0 40px;
}

.nav-menu {
  width: auto;
}

:deep(.n-menu-item-content) {
  padding: 0 20px !important;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.2s;
}

.user-avatar {
  background-color: #eef0fa;
  color: #2080f0;
  font-weight: bold;
}

.user-meta strong {
  font-size: 13px;
  color: #181c22;
}

.divider {
  width: 1px;
  height: 20px;
  background-color: #efeff5;
}

.logout-button {
  height: 32px;
  padding: 0 12px;
  border: 1px solid #efeff5;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: #ffffff;
  color: #717785;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.logout-button:hover {
  color: #d03050;
  border-color: #f5c2c7;
  background: #fffafa;
}

.logout-text {
  font-weight: 500;
}
</style>

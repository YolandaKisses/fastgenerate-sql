<script setup lang="ts">
import { NDialogProvider, NLayout, NMessageProvider } from 'naive-ui'
import { RouterView } from 'vue-router'
import AppSidebar from './components/layout/AppSidebar.vue'
</script>

<template>
  <n-message-provider>
    <n-dialog-provider>
      <n-layout has-sider class="app-layout">
        <AppSidebar />
        
        <n-layout class="main-content">
          <div class="page-container">
            <RouterView />
          </div>
        </n-layout>
      </n-layout>
    </n-dialog-provider>
  </n-message-provider>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  background-color: #fbfcfd;
}

::v-deep(.n-layout-scroll-container) {
  display: flex;
  flex-direction: column;
}

.main-content {
  background-color: #fbfcfd;
}

.page-container {
  padding: 32px 40px;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}
</style>

<script setup lang="ts">
import { NDialogProvider, NLayout, NMessageProvider } from 'naive-ui'
import { RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'
import AppSidebar from './components/layout/AppSidebar.vue'

const route = useRoute()
const isLoginPage = computed(() => route.path === '/login')
</script>

<template>
  <n-message-provider>
    <n-dialog-provider>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in" appear>
          <component :is="Component" v-if="isLoginPage" />
        </transition>
      </router-view>

      <n-layout v-if="!isLoginPage" has-sider class="app-layout">
        <AppSidebar />
        
        <n-layout class="main-content">
          <div class="page-container">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in" appear>
                <component :is="Component" />
              </transition>
            </router-view>
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

<script setup lang="ts">
import { NDialogProvider, NLayout, NMessageProvider } from 'naive-ui'
import { RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'
import AppHeader from './components/layout/AppHeader.vue'

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

      <div v-if="!isLoginPage" class="app-layout">
        <AppHeader />
        
        <main class="main-content">
          <div class="page-container">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in" appear>
                <div class="route-wrapper">
                  <component :is="Component" />
                </div>
              </transition>
            </router-view>
          </div>
        </main>
      </div>
    </n-dialog-provider>
  </n-message-provider>
</template>

<style scoped>
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #fbfcfd;
}

.main-content {
  flex: 1;
  background-color: #fbfcfd;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.page-container {
  padding: 24px 40px;
  height: 100%;
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.route-wrapper {
  height: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

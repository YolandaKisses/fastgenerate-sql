<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NIcon, NInput, useMessage } from "naive-ui";
import {
  EyeOffOutline,
  EyeOutline,
  LockClosedOutline,
  PersonOutline,
} from "@vicons/ionicons5";
import appLogo from "../../assets/fastgenerate-sql-logo.png";
import { login } from "../../services/auth";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const account = ref("admin");
const password = ref("888888");
const loading = ref(false);
const showPassword = ref(false);

const passwordType = computed(() => (showPassword.value ? "text" : "password"));
const visibilityIcon = computed(() =>
  showPassword.value ? EyeOffOutline : EyeOutline,
);

const handleLogin = async () => {
  if (!account.value.trim()) {
    message.warning("请输入账号");
    return;
  }
  if (!password.value) {
    message.warning("请输入密码");
    return;
  }

  loading.value = true;
  try {
    await login(account.value.trim(), password.value);
    message.success("登录成功");
    const redirect =
      typeof route.query.redirect === "string"
        ? route.query.redirect
        : "/data-sources";
    router.replace(redirect);
  } catch (error: any) {
    message.error(error?.message || "登录失败");
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <main class="login-page">
    <div class="background-image" />
    <div class="background-wash" />

    <section class="login-panel">
      <div class="brand-block">
        <div class="brand-icon">
          <img :src="appLogo" alt="FastGenerate SQL logo" />
        </div>
        <h1>FastGenerate SQL</h1>
        <p>专业级 SQL 开发与自动化平台</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <n-input
          v-model:value="account"
          size="large"
          placeholder="请输入您的用户名"
          :disabled="loading"
          class="premium-input"
        >
          <template #prefix>
            <n-icon :component="PersonOutline" />
          </template>
        </n-input>

        <n-input
          v-model:value="password"
          size="large"
          :type="passwordType"
          placeholder="请输入您的密码"
          :disabled="loading"
          @keydown.enter="handleLogin"
          class="premium-input"
        >
          <template #prefix>
            <n-icon :component="LockClosedOutline" />
          </template>
          <template #suffix>
            <button
              class="visibility-button"
              type="button"
              @click="showPassword = !showPassword"
              tabindex="-1"
            >
              <n-icon :component="visibilityIcon" />
            </button>
          </template>
        </n-input>

        <n-button
          type="primary"
          size="large"
          block
          attr-type="submit"
          :loading="loading"
          class="login-submit-btn"
        >
          登录
        </n-button>
      </form>
    </section>

    <footer>© 2026 FastGenerate SQL. 保留所有权利</footer>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
  color: #181c22;
  background: #f9f9ff;
}

.background-image {
  position: absolute;
  inset: 0;
  background-image: url("../../assets/login-bg.png");
  background-size: cover;
  background-position: center;
}

.background-wash {
  position: absolute;
  inset: 0;
  background: rgba(249, 249, 255, 0.12);
}

.login-panel {
  position: relative;
  z-index: 1;
  width: min(100%, 420px);
  padding: 40px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(24px) saturate(180%);
  box-shadow: 
    0 10px 15px -3px rgba(0, 0, 0, 0.1), 
    0 25px 50px -12px rgba(0, 0, 0, 0.15),
    inset 0 0 0 1px rgba(255, 255, 255, 0.5);
  animation: slide-up 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slide-up {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.brand-block {
  text-align: center;
  margin-bottom: 32px;
}

.brand-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 20px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  box-shadow: 0 8px 16px rgba(32, 128, 240, 0.25);
  animation: icon-float 3s ease-in-out infinite;
  overflow: hidden;
}

.brand-icon img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

@keyframes icon-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

.brand-block h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: -0.5px;
  background: linear-gradient(to bottom, #181c22, #414753);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-block p {
  margin: 8px 0 0;
  color: #717785;
  font-size: 14px;
  font-weight: 400;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.premium-input :deep(.n-input-wrapper) {
  padding-left: 12px;
  padding-right: 12px;
}

.visibility-button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: #717785;
  cursor: pointer;
  transition: all 0.2s;
}

.visibility-button:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #2080f0;
}

.login-submit-btn {
  height: 48px;
  font-size: 16px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2080f0 0%, #3070d0 100%);
  border: none;
  box-shadow: 0 4px 12px rgba(32, 128, 240, 0.2);
}

.login-submit-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(32, 128, 240, 0.3);
}

footer {
  position: absolute;
  z-index: 1;
  left: 0;
  right: 0;
  bottom: 24px;
  text-align: center;
  color: rgba(65, 71, 83, 0.5);
  font-size: 12px;
  letter-spacing: 0.5px;
}

@media (max-width: 560px) {
  .login-page {
    padding: 16px;
  }

  .login-panel {
    padding: 32px 24px;
  }

  .brand-block h1 {
    font-size: 24px;
  }
}
</style>

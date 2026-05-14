<script setup lang="ts">
import appLogo from "../../assets/fastgenerate-sql-logo.png";
</script>

<template>
  <aside class="app-sidebar">
    <div class="sidebar-brand">
      <img :src="appLogo" alt="FastGenerate SQL logo" />
      <span>FastGenerate SQL</span>
    </div>
  </aside>
</template>

<style scoped>
.app-sidebar {
  width: 240px;
  min-height: 100%;
  background: #ffffff;
  border-right: 1px solid #eef1f6;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px 16px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #1f2937;
  font-size: 16px;
  font-weight: 700;
}

.sidebar-brand img {
  width: 40px;
  height: 40px;
  object-fit: contain;
}
</style>

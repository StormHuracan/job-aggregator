<template>
  <div class="app-shell">
    <AppNavigation />
    <main class="app-content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from "vue-router";

import AppNavigation from "./components/AppNavigation.vue";
</script>

<style>
@import "./styles/global.css";
</style>

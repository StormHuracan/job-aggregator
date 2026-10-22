<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">К содержимому</a>
    <AppNavigation />
    <main id="main-content" class="app-content" tabindex="-1">
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

<script setup lang="ts">
import UiAlert from "./ui/UiAlert.vue";
defineProps<{ loading: boolean; error: string | null }>();
</script>
<template>
  <div v-if="loading" class="loading" aria-busy="true" role="status">
    <span class="loading-dot" aria-hidden="true"></span>Загрузка…
  </div>
  <UiAlert v-else-if="error" tone="error"
    ><p>{{ error }}</p>
    <template #actions><slot name="error-actions" /></template
  ></UiAlert>
  <slot v-else
    ><div class="empty"><slot name="empty">Данных пока нет.</slot></div></slot
  >
</template>
<style scoped>
.loading {
  align-items: center;
  color: var(--color-muted);
  display: flex;
  gap: 12px;
  justify-content: center;
  min-height: 160px;
}
.loading-dot {
  animation: pulse 1s ease-in-out infinite alternate;
  background: var(--color-link);
  border-radius: 50%;
  height: 8px;
  width: 8px;
}
.empty {
  color: var(--color-muted);
}
@keyframes pulse {
  to {
    opacity: 0.25;
  }
}
</style>

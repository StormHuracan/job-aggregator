<script setup lang="ts">
defineProps<{
  loading: boolean;
  error: string | null;
}>();
</script>

<template>
  <p v-if="loading" aria-busy="true" role="status">Загрузка…</p>
  <section v-else-if="error" aria-live="polite" class="error" role="alert">
    <p>{{ error }}</p>
    <slot name="error-actions" />
  </section>
  <slot v-else name="default">
    <section class="empty">
      <slot name="empty">Данных пока нет.</slot>
    </section>
  </slot>
</template>

<style scoped>
.error {
  border-inline-start: 0.25rem solid var(--color-danger);
  padding-inline-start: var(--space-3);
}

.empty {
  color: var(--color-muted);
}
</style>

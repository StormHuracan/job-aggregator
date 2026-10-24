<script setup lang="ts">
withDefaults(
  defineProps<{ tone?: "error" | "success" | "info" | "warning" }>(),
  {
    tone: "info",
  },
);
</script>
<template>
  <div
    class="alert"
    :class="`alert-${tone}`"
    :role="tone === 'error' ? 'alert' : 'status'"
  >
    <div><slot /></div>
    <slot name="actions" />
  </div>
</template>
<style scoped>
.alert {
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  margin-bottom: 20px;
  padding: 14px 16px;
}
.alert-info {
  background: var(--color-surface);
  color: var(--color-muted);
}
.alert-error {
  background: var(--color-danger-bg);
  border-color: #edc4c9;
  color: var(--color-danger);
}
.alert-success {
  background: var(--color-success-bg);
  border-color: #bbdcc9;
  color: var(--color-success);
}
.alert-warning {
  background: var(--color-warning-bg);
  border-color: #d4ba7e;
  color: var(--color-warning);
}
.alert :deep(p) {
  margin: 0;
}
</style>

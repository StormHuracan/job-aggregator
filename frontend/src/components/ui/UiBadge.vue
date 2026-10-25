<script setup lang="ts">
withDefaults(
  defineProps<{ tone?: "neutral" | "accent" | "success" | "warning" }>(),
  { tone: "neutral" },
);
</script>
<template>
  <span class="badge" :class="tone"><slot /></span>
</template>
<style scoped>
.badge {
  display: inline-flex;
  border-radius: 20px;
  padding: 3px 10px;
  font-size: 13px;
  font-weight: 600;
  background: var(--color-surface-subtle);
  color: var(--color-muted);
}
.accent {
  background: var(--color-accent-soft);
  color: var(--color-link-hover);
}
.success {
  background: var(--color-success-bg);
  color: var(--color-success);
}
.warning {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}
</style>

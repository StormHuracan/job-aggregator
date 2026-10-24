<script setup lang="ts">
defineProps<{ title: string; description: string }>();
</script>
<template>
  <div class="empty-state">
    <div class="empty-symbol" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 4 4M7.5 10.5h6" />
      </svg>
    </div>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <slot />
  </div>
</template>
<style scoped>
.empty-state {
  padding: 40px 20px;
  text-align: center;
}
.empty-state p {
  color: var(--color-muted);
  margin: 0 auto 16px;
  max-width: 42ch;
}
.empty-symbol {
  align-items: center;
  background: var(--color-surface-subtle);
  border-radius: 14px;
  color: var(--color-muted);
  display: flex;
  height: 48px;
  justify-content: center;
  margin: 0 auto 16px;
  width: 48px;
}
svg {
  height: 24px;
  width: 24px;
}
</style>

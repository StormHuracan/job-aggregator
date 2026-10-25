<script setup lang="ts">
withDefaults(
  defineProps<{ variant?: "text" | "vacancy" | "profile"; rows?: number }>(),
  { variant: "text", rows: 3 },
);
</script>
<template>
  <div aria-hidden="true" class="skeleton" :class="variant">
    <div v-for="row in rows" :key="row" class="skeleton-row">
      <span></span><span></span><span></span>
    </div>
  </div>
</template>
<style scoped>
.skeleton {
  width: 100%;
  text-align: left;
}
.skeleton-row {
  display: grid;
  gap: 12px;
  padding: 24px;
  border-bottom: 1px solid var(--color-border);
}
span {
  height: 14px;
  border-radius: 4px;
  background: var(--color-border);
}
span:first-child {
  width: 55%;
  height: 22px;
}
span:nth-child(2) {
  width: 35%;
}
span:last-child {
  width: 80%;
}
.vacancy {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
</style>

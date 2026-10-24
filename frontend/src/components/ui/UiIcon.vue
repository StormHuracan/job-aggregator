<script setup lang="ts">
withDefaults(defineProps<{ name: keyof typeof paths; size?: number }>(), {
  size: 20,
});
const paths = {
  search: "M21 21l-5-5 M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0",
  refresh: "M20 7v5h-5 M4 17v-5h5 M6 6a8 8 0 0 1 13 2 M18 18a8 8 0 0 1-13-2",
  bookmark: "M6 3h12v18l-6-4-6 4Z",
  plus: "M12 5v14 M5 12h14",
  close: "M6 6l12 12 M6 18 18 6",
  user: "M20 21a8 8 0 0 0-16 0 M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  external: "M14 3h7v7 M21 3 10 14 M10 3H3v18h18v-7",
  check: "m5 12 4 4L19 6",
  link: "m10 13 4-4 M8 16l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0 M16 8l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0",
  logout: "M9 3H3v18h6 M9 12h12 m-5-5 5 5-5 5",
  warning: "m12 3 10 18H2Z M12 9v4 M12 17h.01",
  filters: "M4 7h16 M7 12h10 M10 17h4",
  "chevron-down": "m6 9 6 6 6-6",
  "chevron-left": "m15 6-6 6 6 6",
  "chevron-right": "m9 6 6 6-6 6",
};
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path :d="paths[name]" />
  </svg>
</template>
<style scoped>
svg {
  flex-shrink: 0;
  vertical-align: middle;
}
</style>

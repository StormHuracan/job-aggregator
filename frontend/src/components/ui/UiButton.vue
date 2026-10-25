<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "ghost";
    type?: "button" | "submit";
    busy?: boolean;
  }>(),
  { variant: "primary", type: "button", busy: false },
);
</script>
<template>
  <button
    :type="type"
    :class="`button-${variant}`"
    :aria-busy="busy || undefined"
    :disabled="busy || undefined"
  >
    <slot />
  </button>
</template>

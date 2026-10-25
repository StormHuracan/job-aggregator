<script setup lang="ts">
const props = defineProps<{
  modelValue: boolean;
  label: string;
  disabled?: boolean;
  describedBy?: string;
}>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();
function change(event: Event) {
  (event.target as HTMLInputElement).checked = props.modelValue;
  if (!props.disabled) emit("update:modelValue", !props.modelValue);
}
</script>
<template>
  <label class="switch"
    ><input
      type="checkbox"
      role="switch"
      :checked="modelValue"
      :aria-label="label"
      :disabled="disabled"
      :aria-describedby="describedBy"
      @change="change"
    /><span
      class="switch-track"
      :data-checked="modelValue"
      aria-hidden="true"
    ></span
    ><span class="switch-label"
      ><slot>{{ modelValue ? "Включён" : "Выключен" }}</slot></span
    ></label
  >
</template>
<style scoped>
.switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
input {
  position: absolute;
  inset-inline-start: 0;
  opacity: 0;
  width: 42px;
  height: 44px;
  margin: 0;
  cursor: pointer;
}
.switch-track {
  appearance: none;
  flex: none;
  width: 42px;
  height: 26px;
  min-height: 26px;
  padding: 3px;
  border: 1px solid var(--color-muted);
  border-radius: 20px;
  background: var(--color-muted);
  cursor: pointer;
  transition: background-color 180ms;
}
.switch-track::before {
  content: "";
  display: block;
  background: white;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  transition: transform 180ms;
}
.switch-track[data-checked="true"] {
  background: var(--color-link);
  border-color: var(--color-link);
}
.switch-track[data-checked="true"]::before {
  transform: translateX(16px);
}
input:disabled {
  cursor: wait;
}
input:focus-visible + .switch-track {
  outline: 3px solid var(--color-link);
  outline-offset: 3px;
}
.switch-label {
  min-width: 86px;
}
</style>

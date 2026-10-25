<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import UiButton from "./UiButton.vue";
import UiIcon from "./UiIcon.vue";
const props = defineProps<{
  open: boolean;
  title: string;
  description?: string;
}>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement>();
const id = useId();
function keepFocusInside(event: KeyboardEvent) {
  if (event.key !== "Tab") return;
  const controls = Array.from(
    dialog.value?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]',
    ) ?? [],
  );
  const first = controls[0];
  const last = controls.at(-1);
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
let previousFocus: HTMLElement | null = null;
let previousOverflow = "";
function restore() {
  if (!previousFocus) return;
  document.body.style.overflow = previousOverflow;
  const target =
    previousFocus?.isConnected && !previousFocus.matches(":disabled")
      ? previousFocus
      : document.querySelector<HTMLElement>("#main-content");
  target?.focus();
  previousFocus = null;
}
watch(
  () => props.open,
  async (open) => {
    await nextTick();
    if (!dialog.value) return;
    if (open) {
      previousFocus =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      previousOverflow = document.body.style.overflow;
      dialog.value.showModal?.();
      document.body.style.overflow = "hidden";
      (
        dialog.value.querySelector<HTMLElement>("input:not(:disabled)") ??
        dialog.value.querySelector<HTMLElement>("button:not(:disabled)")
      )?.focus();
    } else {
      dialog.value.close?.();
      restore();
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  if (props.open) restore();
});
</script>
<template>
  <dialog
    ref="dialog"
    :aria-labelledby="`${id}-title`"
    :aria-describedby="description ? `${id}-description` : undefined"
    @cancel.prevent="emit('close')"
    @keydown="keepFocusInside"
    @close="open && emit('close')"
  >
    <header>
      <h2 :id="`${id}-title`">{{ title }}</h2>
      <UiButton
        variant="ghost"
        aria-label="Закрыть диалог"
        @click="emit('close')"
        ><UiIcon name="close"
      /></UiButton>
    </header>
    <p v-if="description" :id="`${id}-description`" class="muted">
      {{ description }}
    </p>
    <slot />
  </dialog>
</template>
<style scoped>
dialog {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  box-shadow: var(--shadow-overlay);
  padding: 28px;
  width: min(560px, calc(100% - 32px));
  max-height: calc(100dvh - 32px);
  overscroll-behavior: contain;
}
dialog::backdrop {
  background: rgb(23 43 58 / 46%);
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
h2 {
  font-size: 22px;
  margin: 0;
}
header button {
  flex: none;
  padding: 8px;
}
@media (max-width: 640px) {
  dialog {
    padding: 20px;
  }
}
</style>

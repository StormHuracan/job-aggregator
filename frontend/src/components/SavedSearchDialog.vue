<script setup lang="ts">
import type { SavedSearchCreate } from "../api/saved-searches";
import SavedSearchForm from "./SavedSearchForm.vue";
import UiDialog from "./ui/UiDialog.vue";
import UiAlert from "./ui/UiAlert.vue";
defineProps<{
  open: boolean;
  initialValues?: Partial<SavedSearchCreate>;
  submitting?: boolean;
  fieldErrors?: Readonly<Record<string, string>>;
  error?: string | null;
  notice?: string;
}>();
const emit = defineEmits<{
  create: [input: SavedSearchCreate];
  close: [];
  "clear-errors": [];
}>();
</script>
<template>
  <UiDialog
    :open="open"
    title="Сохранить поиск"
    description="Назовите поиск и проверьте условия. К ним можно будет вернуться в любой момент."
    @close="emit('close')"
  >
    <template v-if="open">
      <UiAlert v-if="notice" tone="warning">{{ notice }}</UiAlert>
      <UiAlert v-if="error" tone="error">{{ error }}</UiAlert>
      <SavedSearchForm
        :initial-values="initialValues"
        :submitting="submitting"
        :field-errors="fieldErrors"
        @create="emit('create', $event)"
        @clear-errors="emit('clear-errors')"
      />
      <p v-if="submitting" class="field-hint">
        Сохранение продолжится, даже если закрыть диалог.
      </p>
    </template>
  </UiDialog>
</template>

<template>
  <form ref="form" novalidate :aria-busy="submitting" @submit.prevent="submit">
    <div v-for="field in fields" :key="field.key" class="field">
      <label :for="`${prefix}-${field.key}`">{{ field.label }}</label>
      <input :id="`${prefix}-${field.key}`" v-model="values[field.key]" :name="field.key"
        :inputmode="field.salary ? 'numeric' : undefined" :required="field.required"
        :disabled="disabled || submitting" :aria-invalid="error(field.key) ? 'true' : undefined"
        :aria-describedby="error(field.key) ? `${prefix}-${field.key}-error` : undefined"
        @input="clearError(field.key)" />
      <p v-if="error(field.key)" :id="`${prefix}-${field.key}-error`" role="alert">{{ error(field.key) }}</p>
    </div>
    <button :disabled="disabled || submitting" type="submit">{{ submitting ? "Сохраняем…" : "Сохранить поиск" }}</button>
  </form>
</template>
<script setup lang="ts">
import { nextTick, reactive, ref, useId, watch } from "vue";
import type { SavedSearchCreate } from "../api/saved-searches";

const props = withDefaults(defineProps<{
  disabled?: boolean;
  submitting?: boolean;
  fieldErrors?: Readonly<Record<string, string>>;
  resetKey?: number;
}>(), { disabled: false, submitting: false, fieldErrors: () => ({}), resetKey: 0 });
const emit = defineEmits<{ create: [input: SavedSearchCreate]; "clear-errors": [] }>();
const fields = [
  { key: "name", label: "Название", required: true, salary: false },
  { key: "text", label: "Текст поиска", required: true, salary: false },
  { key: "area", label: "Регион (необязательно)", required: false, salary: false },
  { key: "min_salary", label: "Зарплата от (необязательно)", required: false, salary: true },
  { key: "max_salary", label: "Зарплата до (необязательно)", required: false, salary: true },
] as const;
type Field = typeof fields[number]["key"];
const prefix = useId();
const form = ref<HTMLFormElement | null>(null);
const values = reactive<Record<Field, string>>({ name: "", text: "", area: "", min_salary: "", max_salary: "" });
const errors = reactive<Partial<Record<Field, string>>>({});
const error = (field: Field) => errors[field] ?? props.fieldErrors[field];
function clearError(field: Field): void { delete errors[field]; emit("clear-errors"); }
watch(() => props.resetKey, () => {
  for (const field of fields) { values[field.key] = ""; delete errors[field.key]; }
});

async function submit(): Promise<void> {
  if (props.disabled || props.submitting) return;
  emit("clear-errors");
  for (const field of fields) {
    delete errors[field.key];
    const value = values[field.key].trim();
    if (field.required && !value) errors[field.key] = field.key === "name" ? "Укажите название" : "Укажите текст поиска";
    else if (!field.salary && Array.from(value).length > 255) errors[field.key] = "Не более 255 символов";
    else if (field.salary && value && (!Number.isSafeInteger(Number(value)) || Number(value) < 0)) {
      errors[field.key] = "Введите целое неотрицательное число";
    }
  }
  const min = values.min_salary.trim() ? Number(values.min_salary) : null;
  const max = values.max_salary.trim() ? Number(values.max_salary) : null;
  if (min !== null && max !== null && min > max) errors.max_salary = "Максимум не может быть меньше минимума";
  if (Object.keys(errors).length) {
    await nextTick();
    form.value?.querySelector<HTMLInputElement>('[aria-invalid="true"]')?.focus();
    return;
  }
  emit("create", { name: values.name.trim(), text: values.text.trim(), area: values.area.trim() || null,
    min_salary: min, max_salary: max });
}
</script>
<style scoped>
.field { display: grid; gap: var(--space-2); min-width: 0; }
input { min-width: 0; width: 100%; }
input[aria-invalid="true"] { border-color: var(--color-danger); }
p[role="alert"] { color: var(--color-danger); font-size: 0.9rem; margin: 0; }
</style>

<template>
  <form @submit.prevent="submit">
    <label>Название<input v-model.trim="name" /></label>
    <p v-if="nameError" role="alert">{{ nameError }}</p>
    <label>Текст поиска<input v-model.trim="text" /></label>
    <p v-if="textError" role="alert">{{ textError }}</p>
    <label>Регион<input v-model.trim="area" /></label>
    <button type="submit">Сохранить поиск</button>
  </form>
</template>
<script setup lang="ts">
import { ref } from "vue";

const emit = defineEmits<{ create: [{ name: string; text: string; area: string | null }] }>();
const name = ref("");
const text = ref("");
const area = ref("");
const nameError = ref("");
const textError = ref("");

function submit(): void {
  nameError.value = name.value ? "" : "Укажите название";
  textError.value = text.value ? "" : "Укажите текст поиска";
  if (!nameError.value && !textError.value) emit("create", { name: name.value, text: text.value, area: area.value || null });
}
</script>
<style scoped>
label { display: grid; gap: var(--space-2); }
input { min-width: 0; width: 100%; }
p[role="alert"] { color: var(--color-danger); font-size: 0.9rem; margin: calc(var(--space-2) * -1) 0 0; }
</style>

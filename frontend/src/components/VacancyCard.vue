<template>
  <article class="card">
    <h2>{{ vacancy.title }}</h2>
    <p class="meta">{{ vacancy.company_name ?? "Компания не указана" }} · {{ vacancy.area_name ?? "Город не указан" }}</p>
    <p class="salary">{{ salary }}</p>
    <p v-if="vacancy.description" class="description">{{ vacancy.description }}</p>
    <a :href="vacancy.source_url" rel="noopener noreferrer" target="_blank">Открыть вакансию в источнике</a>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { VacancyResponse } from "../api/vacancies";

const props = defineProps<{ vacancy: VacancyResponse }>();
const salary = computed(() => {
  const amount = props.vacancy.salary_from ?? props.vacancy.salary_to;
  return amount === null ? "Зарплата не указана" : `Зарплата от ${amount.toLocaleString("ru-RU")} ${props.vacancy.salary_currency ?? ""}`.trim();
});
</script>
<style scoped>
.card { border-top: 1px solid var(--color-border); padding: 1.25rem 0; }
.card:first-of-type { border-top: 0; }
.card h2 { font-size: 1.3rem; margin: 0 0 0.3rem; }
.meta { color: var(--color-muted); margin: 0; }
.salary { color: var(--color-ink); font-weight: 750; margin: 0.7rem 0; }
.description { max-width: 65ch; }
</style>

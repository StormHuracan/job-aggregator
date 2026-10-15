<template>
  <article class="card">
    <h2>{{ vacancy.title }}</h2>
    <p>{{ vacancy.company_name ?? "Компания не указана" }} · {{ vacancy.area_name ?? "Город не указан" }}</p>
    <p>{{ salary }}</p>
    <p v-if="vacancy.description">{{ vacancy.description }}</p>
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

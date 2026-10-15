<template>
  <article class="card">
    <div class="vacancy-main">
      <h3>{{ vacancy.title }}</h3>
      <p class="meta">{{ vacancy.company_name ?? "Компания не указана" }} <span aria-hidden="true">/</span> {{ vacancy.area_name ?? "Город не указан" }}</p>
      <p v-if="vacancy.description" class="description">{{ vacancy.description }}</p>
    </div>
    <div class="vacancy-aside"><p class="salary">{{ salary }}</p><a :href="vacancy.source_url" rel="noopener noreferrer" target="_blank">В источник</a></div>
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
.card { border-top: 1px solid var(--color-border); display: grid; gap: var(--space-6); grid-template-columns: minmax(0, 1fr) minmax(11rem, 0.36fr); padding: 1.35rem 0; }
.card:first-of-type { border-top: 0; }
.card h3 { color: var(--color-ink); font-size: 1.25rem; margin: 0 0 0.3rem; }
.meta { color: var(--color-muted); margin: 0; }
.meta span { color: var(--color-amber); font-weight: 800; padding-inline: var(--space-1); }
.salary { color: var(--color-success); font-feature-settings: "tnum"; font-variant-numeric: tabular-nums; font-weight: 750; margin: 0.7rem 0; }
.description { color: var(--color-text); margin: var(--space-3) 0 0; max-width: 65ch; }
.vacancy-aside { align-self: start; text-align: right; }
.vacancy-aside .salary { margin: 0 0 var(--space-3); }
@media (max-width: 42rem) { .card { grid-template-columns: 1fr; } .vacancy-aside { text-align: left; } }
</style>

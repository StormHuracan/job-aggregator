<template>
  <section class="vacancies-page">
    <div class="page-heading">
      <div>
        <h1>Вакансии</h1>
        <p class="page-intro">Соберите подходящие роли в одном месте и возвращайтесь к поиску в удобном темпе.</p>
      </div>
      <button :disabled="collectionRunning" type="button" @click="runCollection">{{ collectionRunning ? "Обновляем витрину…" : "Обновить вакансии" }}</button>
    </div>
    <p v-if="collectionMessage" class="collection-status" role="status">{{ collectionMessage }}</p>
    <form class="filters" @submit.prevent="applyFilters">
      <div class="filters-heading"><h2>Уточнить выдачу</h2><p>Параметры сохраняются в ссылке.</p></div>
      <label class="wide-field">Текст <input v-model="text" placeholder="Например, Python developer" /></label>
      <label>Компания <input v-model="company" /></label>
      <label>Город <input v-model="area" /></label>
      <label>Зарплата от <input v-model.number="salaryFrom" min="0" type="number" /></label>
      <label>Зарплата до <input v-model.number="salaryTo" min="0" type="number" /></label>
      <button type="submit">Найти</button>
    </form>
    <div class="results-heading"><h2>Результаты</h2><p>{{ filteredVacancies.length }} в текущей выдаче</p></div>
    <div class="vacancy-list"><VacancyCard v-for="vacancy in filteredVacancies" :key="vacancy.id" :vacancy="vacancy" /></div>
    <p v-if="filteredVacancies.length === 0" class="empty-result">Вакансии не найдены. Измените параметры поиска.</p>
    <nav aria-label="Пагинация" class="pagination"><button :disabled="offset === 0" type="button" @click="changePage(-1)">Предыдущая</button><button :disabled="filteredVacancies.length < limit" type="button" @click="changePage(1)">Следующая</button></nav>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { VacancyResponse } from "../api/vacancies";
import VacancyCard from "../components/VacancyCard.vue";

const vacancies: VacancyResponse[] = [{ id: 1, title: "Python developer", company_name: "Демо-компания", area_name: "Москва", salary_from: 180000, salary_to: null, salary_currency: "RUR", description: "Тестовая вакансия. Данные будут заменены публичным API.", source_url: "https://hh.ru" }];
const route = useRoute();
const router = useRouter();
const text = ref(String(route.query.text ?? ""));
const company = ref(String(route.query.company ?? ""));
const area = ref(String(route.query.area ?? ""));
const salaryFrom = ref(Number(route.query.salary_from) || undefined);
const salaryTo = ref(Number(route.query.salary_to) || undefined);
const limit = Number(route.query.limit) || 20;
const offset = computed(() => Number(route.query.offset) || 0);
const collectionRunning = ref(false);
const collectionMessage = ref("");
const filteredVacancies = computed(() => vacancies.filter((vacancy) => {
  const matchesText = [vacancy.title, vacancy.company_name, vacancy.area_name].filter(Boolean).join(" ").toLowerCase().includes(`${text.value} ${company.value} ${area.value}`.trim().toLowerCase());
  const salary = vacancy.salary_from ?? vacancy.salary_to ?? 0;
  return matchesText && (!salaryFrom.value || salary >= salaryFrom.value) && (!salaryTo.value || salary <= salaryTo.value);
}).slice(offset.value, offset.value + limit));

async function applyFilters(): Promise<void> {
  await router.replace({ query: { text: text.value || undefined, company: company.value || undefined, area: area.value || undefined, salary_from: salaryFrom.value, salary_to: salaryTo.value, limit, offset: undefined } });
}

async function changePage(direction: number): Promise<void> {
  await router.replace({ query: { ...route.query, offset: Math.max(0, offset.value + direction * limit) } });
}

async function runCollection(): Promise<void> {
  collectionRunning.value = true;
  collectionMessage.value = "";
  await Promise.resolve();
  collectionRunning.value = false;
  collectionMessage.value = "Сбор вакансий завершён. Данные будут обновлены после подключения API.";
}
</script>
<style scoped>
.page-heading { align-items: end; display: flex; gap: var(--space-6); justify-content: space-between; margin-bottom: var(--space-8); }
.page-heading h1 { margin-bottom: var(--space-3); }
.page-intro { color: var(--color-muted); margin: 0; max-width: 48ch; }
.page-heading button { flex: none; }
.collection-status { background: #fff7e5; border: 1px solid #ead6a7; color: #76540f; margin: -1rem 0 var(--space-6); padding: var(--space-3) var(--space-4); }
.filters { border-block: 1px solid var(--color-border); display: grid; gap: 0.9rem; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 1.5rem 0; padding: 1.25rem 0; }
.filters-heading { grid-column: 1 / -1; }
.filters-heading h2, .results-heading h2 { font-size: 1.1rem; margin: 0; }
.filters-heading p, .results-heading p { color: var(--color-muted); font-size: 0.9rem; margin: 0.2rem 0 0; }
.wide-field { grid-column: span 2; }
.filters label { display: grid; gap: 0.35rem; }
.results-heading { align-items: baseline; display: flex; justify-content: space-between; margin: var(--space-8) 0 var(--space-2); }
.vacancy-list { border-bottom: 1px solid var(--color-border); }
.empty-result { color: var(--color-muted); padding: var(--space-8) 0; }
.pagination { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1rem; }
@media (max-width: 42rem) { .page-heading { align-items: start; flex-direction: column; } .filters { grid-template-columns: 1fr; } .wide-field { grid-column: auto; } }
</style>

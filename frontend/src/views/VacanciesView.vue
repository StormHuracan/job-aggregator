<template>
  <section>
    <h1>Вакансии</h1>
    <div class="page-intro"><p>Общая витрина для спокойного поиска следующей роли.</p><button :disabled="collectionRunning" type="button" @click="runCollection">{{ collectionRunning ? "Сбор выполняется…" : "Обновить витрину" }}</button></div>
    <p v-if="collectionMessage" role="status">{{ collectionMessage }}</p>
    <form class="filters" @submit.prevent="applyFilters">
      <label>Текст <input v-model="text" /></label>
      <label>Компания <input v-model="company" /></label>
      <label>Город <input v-model="area" /></label>
      <label>Зарплата от <input v-model.number="salaryFrom" min="0" type="number" /></label>
      <label>Зарплата до <input v-model.number="salaryTo" min="0" type="number" /></label>
      <button type="submit">Найти</button>
    </form>
    <VacancyCard v-for="vacancy in filteredVacancies" :key="vacancy.id" :vacancy="vacancy" />
    <p v-if="filteredVacancies.length === 0">Вакансии не найдены.</p>
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
.page-intro { align-items: start; display: flex; gap: 1rem; justify-content: space-between; margin-bottom: 1.5rem; }
.page-intro p { color: var(--color-muted); margin: 0; max-width: 38ch; }
.filters { display: grid; gap: 0.9rem; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 1.5rem 0; padding: 1.25rem; background: #f4f7fa; border-radius: var(--radius-sm); }
.filters label { display: grid; gap: 0.35rem; }
.pagination { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1rem; }
@media (max-width: 42rem) { .page-intro { flex-direction: column; } .filters { grid-template-columns: 1fr; } }
</style>

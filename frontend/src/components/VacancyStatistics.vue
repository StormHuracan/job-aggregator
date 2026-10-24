<script setup lang="ts">
import { onMounted, onScopeDispose, ref } from "vue";
import { ApiError } from "../api/client";
import {
  getVacancyStatistics,
  type VacancyStatisticsResponse,
} from "../api/vacancies";
import AsyncState from "./AsyncState.vue";
import UiButton from "./ui/UiButton.vue";

const loading = ref(false);
const error = ref<string | null>(null);
const stats = ref<VacancyStatisticsResponse | null>(null);
let requestId = 0;
let active = true;
onScopeDispose(() => {
  active = false;
});

const rubles = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});
const count = new Intl.NumberFormat("ru-RU");

async function load(): Promise<void> {
  const id = ++requestId;
  loading.value = true;
  error.value = null;
  try {
    const data = await getVacancyStatistics();
    if (active && id === requestId) stats.value = data;
  } catch (caught) {
    if (active && id === requestId)
      error.value =
        caught instanceof ApiError
          ? caught.message
          : "Не удалось загрузить статистику. Попробуйте ещё раз.";
  } finally {
    if (active && id === requestId) loading.value = false;
  }
}

onMounted(load);
defineExpose({ reload: load });
</script>

<template>
  <section class="panel statistics" aria-labelledby="statistics-heading">
    <h2 id="statistics-heading">Статистика по сохранённым вакансиям</h2>
    <AsyncState :loading="loading" :error="error"
      ><template #error-actions
        ><UiButton variant="secondary" @click="load"
          >Повторить</UiButton
        ></template
      >
      <template v-if="stats">
        <p v-if="stats.total_vacancies === 0" class="muted">
          Сохранённых вакансий пока нет. Получите свежие вакансии с HH.ru —
          статистика появится здесь.
        </p>
        <div v-else class="statistics-body">
          <dl class="metrics">
            <div>
              <dt>Всего вакансий</dt>
              <dd data-test="total">{{ count.format(stats.total_vacancies) }}</dd>
            </div>
            <div>
              <dt>Средняя зарплата</dt>
              <dd data-test="average">
                {{
                  stats.average_salary === null
                    ? "Недостаточно данных"
                    : rubles.format(stats.average_salary)
                }}
              </dd>
            </div>
            <div>
              <dt>Вакансий в расчёте средней</dt>
              <dd data-test="sample">{{ count.format(stats.salary_sample_size) }}</dd>
            </div>
          </dl>
          <div v-if="stats.top_areas.length" class="areas">
            <h3>Топ городов</h3>
            <ol>
              <li v-for="area in stats.top_areas" :key="area.area_name">
                {{ area.area_name }} —
                <span class="muted">{{ count.format(area.vacancies_count) }}</span>
              </li>
            </ol>
          </div>
          <p class="note muted">
            Средняя рассчитана только по вакансиям в рублях с указанной вилкой
            «от» и «до». Это не оценка всего рынка и не сумма после вычета
            налогов.
          </p>
        </div>
      </template>
    </AsyncState>
  </section>
</template>

<style scoped>
.statistics {
  display: grid;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
  padding: var(--space-4) var(--space-6);
}
.statistics h2 {
  font-size: 1.125rem;
  margin: 0;
}
.statistics-body {
  display: grid;
  gap: var(--space-4);
}
.metrics {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  margin: 0;
}
.metrics dt {
  color: var(--color-muted);
  font-size: 0.875rem;
}
.metrics dd {
  color: var(--color-ink);
  font-size: 1.25rem;
  font-weight: 600;
  margin: var(--space-1) 0 0;
}
.areas h3 {
  font-size: 0.875rem;
  margin: 0 0 var(--space-2);
}
.areas ol {
  display: grid;
  gap: var(--space-1);
  margin: 0;
  padding-left: var(--space-6);
}
.note {
  font-size: 0.875rem;
  margin: 0;
}
</style>

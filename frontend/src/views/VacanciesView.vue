<template>
  <section v-if="!sessionExpired" aria-labelledby="vacancies-heading">
    <div class="page-heading">
      <div>
        <h1 id="vacancies-heading">Работа для разработчиков</h1>
        <p>
          Ищите вакансии для разработчиков по технологиям, компании и городу.
        </p>
      </div>
    </div>
    <form class="filters panel" @submit.prevent="applyFilters">
      <div class="search-row">
        <label class="field query-field" for="vacancy-query"
          >Должность или технология<input
            id="vacancy-query"
            v-model="text"
            type="search"
            placeholder="Например, Python developer" /></label
        ><UiButton type="submit" :disabled="loading">Найти вакансии</UiButton>
      </div>
      <div class="filter-toolbar">
        <details
          ref="filterDetails"
          class="advanced-filters"
          :open="hasAdvanced"
        >
          <summary>
            Фильтры<span v-if="filterCount" class="filter-count">{{
              filterCount
            }}</span>
          </summary>
          <div class="advanced-fields">
            <label class="field"
              >Компания<input v-model="company" placeholder="Название компании"
            /></label>
            <label class="field"
              >Город<input v-model="area" placeholder="Например, Москва"
            /></label>
            <label class="field"
              >Зарплата от<input
                v-model="salaryFrom"
                type="number"
                min="0"
                step="1"
                inputmode="numeric"
                placeholder="Не указана"
            /></label>
            <label class="field"
              >Зарплата до<input
                v-model="salaryTo"
                type="number"
                min="0"
                step="1"
                inputmode="numeric"
                placeholder="Не указана"
                ref="salaryToInput"
                :aria-invalid="salaryError ? true : undefined"
                :aria-describedby="salaryError ? 'salary-error' : undefined"
              /><span
                v-if="salaryError"
                id="salary-error"
                class="error-text"
                role="alert"
                >{{ salaryError }}</span
              ></label
            >
          </div>
        </details>
        <UiButton
          v-if="hasFilters"
          variant="ghost"
          class="reset-filters"
          @click="resetFilters"
          >Сбросить</UiButton
        >
      </div>
    </form>
    <div class="source-toolbar">
      <p>Поиск по уже собранным вакансиям</p>
      <button
        class="source-toggle"
        :aria-expanded="showCollection"
        aria-controls="collection-panel"
        @click="showCollection = !showCollection"
      >
        Получить свежие с HH.ru <span aria-hidden="true">↗</span>
      </button>
    </div>
    <div
      v-if="showCollection"
      id="collection-panel"
      class="collection-panel panel"
    >
      <h2>Получить вакансии с HH.ru</h2>
      <p class="muted">
        Загрузим вакансии по отдельному запросу и добавим их в общую базу.
        Требуется подключённый аккаунт HH.ru.
      </p>
      <form class="collection-form" @submit.prevent="collect">
        <label class="field"
          >Поисковый запрос<input
            v-model.trim="collectionText"
            required
            maxlength="255"
            placeholder="Python developer"
            :disabled="collectionRunning" /></label
        ><label class="field"
          >ID региона HH.ru<input
            v-model.trim="collectionArea"
            placeholder="Например, 1 — Москва"
            :disabled="collectionRunning" /></label
        ><label class="field"
          >Количество страниц<input
            v-model.number="collectionPages"
            type="number"
            min="1"
            step="1"
            required
            :disabled="collectionRunning" /></label
        ><UiButton
          type="submit"
          :busy="collectionRunning"
          :disabled="collectionRunning"
          >{{ collectionRunning ? "Получаем…" : "Получить вакансии" }}</UiButton
        >
      </form>
    </div>
    <UiAlert
      v-if="collectionMessage"
      :tone="collectionError ? 'error' : 'success'"
      >{{ collectionMessage }}</UiAlert
    >
    <div class="section-heading">
      <h2>
        Вакансии
        <span v-if="result && !loading && !loadError" class="result-count">{{
          result.total.toLocaleString("ru-RU")
        }}</span>
      </h2>
      <p>Сначала новые</p>
    </div>
    <AsyncState
      :loading="loading"
      :error="
        loadError
          ? `Не удалось загрузить вакансии. ${loadError}. Попробуйте ещё раз.`
          : null
      "
      ><template #error-actions
        ><UiButton variant="secondary" @click="load"
          >Повторить загрузку</UiButton
        ></template
      >
      <div class="panel vacancy-list">
        <VacancyCard
          v-for="vacancy in result?.items"
          :key="vacancy.id"
          :vacancy="vacancy"
        /><EmptyState
          v-if="!result?.items.length"
          :title="
            offset > 0 ? 'На этой странице вакансий нет' : 'Вакансии не найдены'
          "
          :description="
            offset > 0
              ? 'Вернитесь на первую страницу, чтобы увидеть актуальные результаты.'
              : 'Попробуйте другой запрос или уберите часть фильтров.'
          "
          ><UiButton
            v-if="offset > 0"
            variant="secondary"
            @click="router.push({ query: { ...route.query, offset: 0 } })"
            >На первую страницу</UiButton
          ><UiButton
            v-else-if="hasFilters"
            variant="secondary"
            @click="resetFilters"
            >Сбросить фильтры</UiButton
          ></EmptyState
        >
      </div>
      <nav
        v-if="result && result.items.length > 0"
        aria-label="Пагинация"
        class="pagination"
      >
        <p>
          {{ offset + 1 }}–{{
            Math.min(offset + result.items.length, result.total)
          }}
          из {{ result.total }}
        </p>
        <div>
          <UiButton
            variant="secondary"
            :disabled="offset === 0"
            @click="changePage(-1)"
            >Назад</UiButton
          ><UiButton
            variant="secondary"
            :disabled="offset + limit >= result.total"
            @click="changePage(1)"
            >Далее</UiButton
          >
        </div>
      </nav>
    </AsyncState>
  </section>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiError } from "../api/client";
import { listVacancies, type VacancyListResponse } from "../api/vacancies";
import { runCollection } from "../api/collection";
import AsyncState from "../components/AsyncState.vue";
import VacancyCard from "../components/VacancyCard.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import UiButton from "../components/ui/UiButton.vue";
import UiAlert from "../components/ui/UiAlert.vue";
const route = useRoute();
const router = useRouter();
const text = ref("");
const company = ref("");
const area = ref("");
const salaryFrom = ref<string | number>("");
const salaryTo = ref<string | number>("");
const salaryError = ref("");
const filterDetails = ref<HTMLDetailsElement>();
const salaryToInput = ref<HTMLInputElement>();
const integer = (
  value: unknown,
  fallback: number,
  max = Number.MAX_SAFE_INTEGER,
) => {
  const n = Number(value);
  return Number.isSafeInteger(n) && n >= 0 && n <= max ? n : fallback;
};
const limit = computed(() => Math.max(1, integer(route.query.limit, 20, 100)));
const offset = computed(() => integer(route.query.offset, 0));
const filterCount = computed(
  () =>
    [company.value, area.value, salaryFrom.value, salaryTo.value].filter(
      (v) => v !== "",
    ).length,
);
const hasAdvanced = computed(() => filterCount.value > 0);
const hasFilters = computed(() => Boolean(text.value || hasAdvanced.value));
const loading = ref(false);
const loadError = ref<string | null>(null);
const result = ref<VacancyListResponse | null>(null);
let requestId = 0;
let active = true;
const sessionExpired = ref(false);
onScopeDispose(() => {
  active = false;
  requestId++;
});
async function message(error: unknown): Promise<string> {
  if (active && error instanceof ApiError && error.status === 401) {
    sessionExpired.value = true;
    result.value = null;
    await router.replace({
      path: "/login",
      query: { redirect: route.fullPath, reason: "session-expired" },
    });
  }
  return error instanceof ApiError
    ? error.message
    : "Не удалось загрузить вакансии. Попробуйте ещё раз.";
}
async function load(): Promise<void> {
  const id = ++requestId;
  loading.value = true;
  loadError.value = null;
  result.value = null;
  try {
    const data = await listVacancies({
      text: text.value || undefined,
      company: company.value || undefined,
      area: area.value || undefined,
      salary_from:
        salaryFrom.value === "" ? undefined : Number(salaryFrom.value),
      salary_to: salaryTo.value === "" ? undefined : Number(salaryTo.value),
      limit: limit.value,
      offset: offset.value,
    });
    if (active && !sessionExpired.value && id === requestId)
      result.value = data;
  } catch (error) {
    if (active && id === requestId) loadError.value = await message(error);
  } finally {
    if (active && id === requestId) loading.value = false;
  }
}
watch(
  () => route.fullPath,
  () => {
    if (route.path !== "/vacancies" || sessionExpired.value) return;
    text.value = String(route.query.text ?? "");
    company.value = String(route.query.company ?? "");
    area.value = String(route.query.area ?? "");
    salaryFrom.value =
      route.query.salary_from === undefined
        ? ""
        : String(route.query.salary_from);
    salaryTo.value =
      route.query.salary_to === undefined ? "" : String(route.query.salary_to);
    salaryError.value = "";
    void load();
  },
  { immediate: true },
);
async function applyFilters(): Promise<void> {
  salaryError.value = "";
  if (
    salaryFrom.value !== "" &&
    salaryTo.value !== "" &&
    Number(salaryFrom.value) > Number(salaryTo.value)
  ) {
    salaryError.value = "Максимум не может быть меньше минимума";
    if (filterDetails.value) filterDetails.value.open = true;
    salaryToInput.value?.focus();
    return;
  }
  const target = {
    text: text.value.trim() || undefined,
    company: company.value.trim() || undefined,
    area: area.value.trim() || undefined,
    salary_from: salaryFrom.value === "" ? undefined : salaryFrom.value,
    salary_to: salaryTo.value === "" ? undefined : salaryTo.value,
    limit: limit.value,
  };
  const before = route.fullPath;
  await router.push({ query: target });
  if (before === route.fullPath) await load();
}
async function resetFilters(): Promise<void> {
  text.value = "";
  company.value = "";
  area.value = "";
  salaryFrom.value = "";
  salaryTo.value = "";
  salaryError.value = "";
  await applyFilters();
}
async function changePage(direction: number): Promise<void> {
  await router.push({
    query: {
      ...route.query,
      offset: Math.max(0, offset.value + direction * limit.value),
    },
  });
}
const showCollection = ref(false);
const collectionText = ref("");
const collectionArea = ref("");
const collectionPages = ref(1);
const collectionRunning = ref(false);
const collectionMessage = ref("");
const collectionError = ref(false);
async function collect(): Promise<void> {
  if (
    collectionRunning.value ||
    !collectionText.value ||
    !Number.isSafeInteger(collectionPages.value) ||
    collectionPages.value < 1
  )
    return;
  collectionRunning.value = true;
  collectionMessage.value = "";
  collectionError.value = false;
  try {
    const data = await runCollection({
      text: collectionText.value,
      area: collectionArea.value || null,
      pages_limit: collectionPages.value,
    });
    if (!active) return;
    collectionMessage.value = `Сбор завершён. Добавлено: ${data.created}, обновлено: ${data.updated}, пропущено: ${data.skipped}, ошибок: ${data.failed}.`;
    await load();
  } catch (error) {
    if (!active) return;
    collectionError.value = true;
    collectionMessage.value =
      error instanceof ApiError && error.status === 409
        ? "Подключите HH.ru повторно, чтобы запустить сбор вакансий."
        : await message(error);
  } finally {
    collectionRunning.value = false;
  }
}
</script>
<style scoped>
.filters {
  padding: 24px;
}
.search-row {
  align-items: end;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
}
.search-row input {
  margin-top: 4px;
}
.filter-toolbar {
  position: relative;
}
.advanced-filters summary {
  color: var(--color-muted);
  font-size: 14px;
  margin-top: 8px;
  width: fit-content;
}
.filter-count {
  background: var(--color-surface-subtle);
  border-radius: 4px;
  font-size: 12px;
  margin-left: 8px;
  padding: 2px 6px;
}
.advanced-fields {
  border-top: 1px solid var(--color-border);
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 8px;
  padding-top: 20px;
}
.reset-filters {
  position: absolute;
  right: 0;
  top: 8px;
}
.source-toolbar {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0 16px;
  justify-content: space-between;
  margin: 4px 0 24px;
}
.source-toolbar p {
  color: var(--color-muted);
  font-size: 12px;
  margin: 0;
}
.source-toggle {
  background: transparent;
  color: var(--color-link);
  font-size: 13px;
  padding-inline: 0;
}
.source-toggle:hover {
  background: transparent !important;
  color: var(--color-link-hover) !important;
}
.collection-panel {
  margin-bottom: 20px;
  padding: 24px;
}
.collection-form {
  align-items: end;
  display: grid;
  gap: 12px;
  grid-template-columns: 2fr 1.3fr 1fr auto;
}
.result-count {
  background: var(--color-surface-subtle);
  border-radius: 6px;
  color: var(--color-muted);
  display: inline-block;
  font-size: 13px;
  margin-left: 8px;
  padding: 3px 8px;
  vertical-align: middle;
}
.vacancy-list {
  overflow: hidden;
}
.pagination {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  margin-top: 24px;
}
.pagination p {
  color: var(--color-muted);
  font-size: 13px;
  margin: 0;
}
.pagination > div {
  display: flex;
  gap: 8px;
}
@media (max-width: 900px) {
  .advanced-fields,
  .collection-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .filters,
  .collection-panel {
    padding: 16px;
  }
  .search-row {
    grid-template-columns: 1fr;
  }
  .advanced-fields,
  .collection-form {
    grid-template-columns: 1fr;
  }
  .source-toolbar {
    margin-bottom: 8px;
  }
  .source-toolbar p {
    display: none;
  }
  .section-heading {
    margin-top: 20px;
  }
  .pagination {
    align-items: stretch;
    flex-direction: column;
  }
  .pagination > div > * {
    flex: 1;
  }
}
</style>

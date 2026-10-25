<template>
  <section v-if="!sessionExpired" aria-labelledby="vacancies-heading">
    <div class="page-heading">
      <div>
        <h1 id="vacancies-heading">Работа для разработчиков</h1>
        <p>
          Ищите вакансии для разработчиков по технологиям, компании и городу.
        </p>
      </div>
      <div class="save-action">
        <UiButton
          data-action="save-search"
          variant="secondary"
          :disabled="!applied.text.trim() || saving"
          :aria-describedby="
            !applied.text.trim() ? 'save-search-hint' : undefined
          "
          @click="openSave"
          ><UiIcon name="bookmark" />Сохранить поиск</UiButton
        ><span
          v-if="!applied.text.trim()"
          id="save-search-hint"
          class="field-hint"
          >Сначала примените текст поиска</span
        >
      </div>
    </div>
    <UiAlert v-if="saveSuccess" tone="success"
      >Поиск сохранён. Он доступен в разделе «Сохранённые поиски».</UiAlert
    >
    <SavedSearchDialog
      :open="saveOpen"
      :initial-values="saveValues"
      :submitting="saving"
      :error="saveError"
      :field-errors="saveFieldErrors"
      :notice="saveNotice"
      @close="saveOpen = false"
      @create="saveSearch"
      @clear-errors="
        saveError = null;
        saveFieldErrors = {};
      "
    />
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
          v-if="hasFilters || draftChanged"
          variant="ghost"
          class="reset-filters"
          @click="resetFilters"
          >Сбросить</UiButton
        >
      </div>
      <p v-if="draftChanged" class="draft-hint" role="status">
        Условия изменены. Нажмите «Найти вакансии», чтобы обновить результаты.
      </p>
    </form>
    <div
      v-if="chips.length"
      class="applied-filters"
      role="group"
      aria-label="Применённые условия"
    >
      <span class="field-hint">Применено:</span>
      <button
        v-for="chip in chips"
        :key="chip.key"
        type="button"
        class="filter-chip"
        :aria-label="`Убрать фильтр: ${chip.label}`"
        @click="removeFilter(chip.key)"
      >
        {{ chip.label }} <span aria-hidden="true">×</span>
      </button>
    </div>
    <div class="source-toolbar">
      <p v-if="collectionRunning" role="status">
        Загрузка с HH.ru продолжается…
      </p>
      <p v-else>Поиск по сохранённым вакансиям</p>
      <button
        class="source-toggle"
        :aria-expanded="showCollection"
        aria-controls="collection-panel"
        @click="showCollection = !showCollection"
      >
        {{ collectionRunning ? "Загрузка с HH.ru…" : "Загрузить с HH.ru" }}
        <UiIcon name="download" :size="18" />
      </button>
    </div>
    <div
      v-show="showCollection"
      id="collection-panel"
      class="collection-panel panel"
    >
      <h2>Получить вакансии с HH.ru</h2>
      <p class="muted">
        Это отдельный поиск на HH.ru: загрузим вакансии и добавим их в список.
        При повторном поиске продолжим с того места, где остановились. Для этого
        войдите через HH.ru.
      </p>
      <form
        ref="collectionForm"
        class="collection-form"
        @submit.prevent="collect()"
      >
        <div class="collection-fields">
          <div class="field collection-query">
            <label for="collection-query">Должность или технология</label>
            <input
              id="collection-query"
              v-model.trim="collectionText"
              required
              maxlength="255"
              placeholder="Например, Python developer"
              :disabled="collectionRunning"
            />
          </div>
          <RegionPicker
            v-model="collectionArea"
            :disabled="collectionRunning"
            @unauthorized="expireAreaSession"
          />
          <div class="field">
            <label for="collection-pages">Страниц за поиск</label>
            <input
              id="collection-pages"
              v-model.number="collectionPages"
              type="number"
              min="1"
              step="1"
              required
              :disabled="collectionRunning"
              aria-describedby="collection-pages-hint"
            />
            <span id="collection-pages-hint" class="field-hint"
              >До 20 вакансий на странице.</span
            >
          </div>
        </div>
        <div class="collection-actions">
          <UiButton
            type="submit"
            :busy="collectionRunning"
            :disabled="collectionRunning || collectionAtEnd"
            >{{
              collectionRunning
                ? "Получаем…"
                : hasCollectionProgress
                  ? "Продолжить поиск"
                  : "Получить вакансии"
            }}</UiButton
          >
          <UiButton
            variant="secondary"
            :disabled="collectionRunning"
            @click="collect(true)"
            >Проверить новые вакансии</UiButton
          >
        </div>
      </form>
      <p class="field-hint">
        «Проверить новые вакансии» начнёт поиск сначала и обновит уже найденные.
      </p>
      <p v-if="collectionAtEnd" role="status">
        Все доступные вакансии по этому запросу просмотрены. Проверьте новые
        вакансии позже или измените запрос.
      </p>
    </div>
    <UiAlert
      v-if="collectionMessage"
      :tone="
        collectionError ? 'error' : collectionPartial ? 'warning' : 'success'
      "
      >{{ collectionMessage }}</UiAlert
    >
    <VacancyStatistics ref="statistics" />
    <div class="section-heading">
      <h2>
        Вакансии
        <span v-if="result && !loading && !loadError" class="result-count">{{
          result.total.toLocaleString("ru-RU")
        }}</span>
      </h2>
      <p>По дате публикации: сначала новые</p>
    </div>
    <AsyncState :loading="loading" :error="loadError"
      ><template #loading><UiSkeleton variant="vacancy" :rows="3" /></template
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
        aria-label="Страницы вакансий"
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
import { useRoute, useRouter, type LocationQueryRaw } from "vue-router";
import { ApiError } from "../api/client";
import { listVacancies, type VacancyListResponse } from "../api/vacancies";
import { runCollection } from "../api/collection";
import type { HHAreaSuggestion } from "../api/hh-areas";
import RegionPicker from "../components/RegionPicker.vue";
import AsyncState from "../components/AsyncState.vue";
import VacancyCard from "../components/VacancyCard.vue";
import VacancyStatistics from "../components/VacancyStatistics.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import UiButton from "../components/ui/UiButton.vue";
import UiAlert from "../components/ui/UiAlert.vue";
import UiIcon from "../components/ui/UiIcon.vue";
import UiSkeleton from "../components/ui/UiSkeleton.vue";
import SavedSearchDialog from "../components/SavedSearchDialog.vue";
import {
  createSavedSearch,
  type SavedSearchCreate,
} from "../api/saved-searches";
const route = useRoute();
const router = useRouter();
const statistics = ref<InstanceType<typeof VacancyStatistics>>();
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
const applied = computed(() => ({
  text: String(route.query.text ?? ""),
  company: String(route.query.company ?? ""),
  area: String(route.query.area ?? ""),
  salary_from:
    route.query.salary_from == null ? "" : String(route.query.salary_from),
  salary_to: route.query.salary_to == null ? "" : String(route.query.salary_to),
}));
const chips = computed(() =>
  Object.entries(applied.value)
    .filter(([, value]) => value !== "")
    .map(([key, value]) => ({
      key,
      label: `${({ text: "Запрос", company: "Компания", area: "Город", salary_from: "Зарплата от", salary_to: "Зарплата до" } as Record<string, string>)[key]}: ${value}`,
    })),
);
const draftChanged = computed(() =>
  [
    text.value.trim(),
    company.value.trim(),
    area.value.trim(),
    String(salaryFrom.value),
    String(salaryTo.value),
  ].some((value, index) => value !== Object.values(applied.value)[index]),
);
async function removeFilter(key: string) {
  const query: LocationQueryRaw = { ...route.query, offset: 0 };
  delete query[key];
  await router.push({ query });
}
const filterCount = computed(
  () => chips.value.filter((chip) => chip.key !== "text").length,
);
const hasAdvanced = computed(() => filterCount.value > 0);
const hasFilters = computed(() => chips.value.length > 0);
const saveOpen = ref(false);
const saving = ref(false);
const saveSuccess = ref(false);
const saveError = ref<string | null>(null);
const saveFieldErrors = ref<Readonly<Record<string, string>>>({});
const saveValues = ref<Partial<SavedSearchCreate>>({});
const saveNotice = ref("");
function openSave() {
  if (saving.value || !applied.value.text.trim()) return;
  saveError.value = null;
  saveFieldErrors.value = {};
  saveSuccess.value = false;
  saveValues.value = {
    name: applied.value.text,
    text: applied.value.text,
    area: applied.value.area || null,
    min_salary:
      applied.value.salary_from === ""
        ? null
        : Number(applied.value.salary_from),
    max_salary:
      applied.value.salary_to === "" ? null : Number(applied.value.salary_to),
  };
  saveNotice.value = applied.value.company
    ? `Компания «${applied.value.company}» не сохранится: сохранённые поиски поддерживают только запрос, регион и зарплату. Вы можете сохранить эти условия без компании.`
    : "";
  saveOpen.value = true;
}
async function saveSearch(input: SavedSearchCreate) {
  if (saving.value || sessionExpired.value) return;
  saving.value = true;
  try {
    await createSavedSearch(input);
    if (!active || sessionExpired.value) return;
    saveOpen.value = false;
    saveSuccess.value = true;
  } catch (error) {
    if (!active || sessionExpired.value) return;
    saveError.value = await message(error);
    saveFieldErrors.value = error instanceof ApiError ? error.fieldErrors : {};
  } finally {
    saving.value = false;
  }
}
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
      text: applied.value.text || undefined,
      company: applied.value.company || undefined,
      area: applied.value.area || undefined,
      salary_from:
        applied.value.salary_from === ""
          ? undefined
          : Number(applied.value.salary_from),
      salary_to:
        applied.value.salary_to === ""
          ? undefined
          : Number(applied.value.salary_to),
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
const collectionArea = ref<HHAreaSuggestion | null>(null);
const collectionPages = ref(1);
const collectionRunning = ref(false);
const collectionForm = ref<HTMLFormElement>();
const collectionMessage = ref("");
const collectionError = ref(false);
const collectionPartial = ref(false);
const collectionKey = computed(() =>
  JSON.stringify([
    collectionText.value.trim(),
    collectionArea.value?.id ?? null,
  ]),
);
const lastCollection = ref<{ key: string; exhausted: boolean } | null>(null);
const hasCollectionProgress = computed(
  () => lastCollection.value?.key === collectionKey.value,
);
const collectionAtEnd = computed(
  () => hasCollectionProgress.value && lastCollection.value!.exhausted,
);
watch(collectionKey, () => {
  collectionMessage.value = "";
});
async function expireAreaSession(): Promise<void> {
  await message(new ApiError(401, "Войдите снова, чтобы продолжить."));
}
async function collect(restart = false): Promise<void> {
  if (!collectionForm.value?.reportValidity()) return;
  if (
    collectionRunning.value ||
    sessionExpired.value ||
    (!restart && collectionAtEnd.value) ||
    !collectionText.value ||
    !Number.isSafeInteger(collectionPages.value) ||
    collectionPages.value < 1
  )
    return;
  collectionRunning.value = true;
  collectionMessage.value = "";
  collectionError.value = false;
  collectionPartial.value = false;
  const key = collectionKey.value;
  try {
    const data = await runCollection({
      text: collectionText.value,
      area: collectionArea.value?.id ?? null,
      pages_limit: collectionPages.value,
      restart,
    });
    if (!active || sessionExpired.value) return;
    lastCollection.value = { key, exhausted: data.exhausted };
    collectionPartial.value = data.failed > 0;
    collectionMessage.value = `Найдено новых: ${data.created}. Обновлено: ${data.updated}. Уже есть в списке: ${data.skipped}.`;
    if (data.failed)
      collectionMessage.value += ` Не удалось загрузить: ${data.failed}. Попробуйте проверить новые вакансии ещё раз.`;
    void statistics.value?.reload();
    await load();
  } catch (error) {
    if (!active) return;
    collectionError.value = true;
    collectionMessage.value =
      error instanceof ApiError && error.status === 409
        ? "Подключите HH.ru повторно, чтобы получить вакансии."
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
.draft-hint {
  color: var(--color-link-hover);
  background: var(--color-accent-soft);
  font-size: 14px;
  padding: 10px 12px;
  border-radius: 8px;
  margin: 12px 0 0;
}
.save-action {
  display: grid;
  justify-items: end;
  gap: 4px;
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
  font-size: 14px;
  margin: 0;
}
.source-toggle {
  background: transparent;
  border-color: transparent;
  color: var(--color-link);
  font-size: 14px;
}
.source-toggle:hover {
  background: transparent !important;
  color: var(--color-link-hover) !important;
}
.collection-panel {
  margin-bottom: 20px;
  padding: 24px;
}
.collection-fields {
  align-items: start;
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1.5fr) minmax(140px, 0.8fr);
}
.collection-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-block: 20px 12px;
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
  overflow: clip;
}
.applied-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0;
}
.filter-chip {
  background: var(--color-accent-soft);
  color: var(--color-link-hover);
  border: 1px solid #becbf0;
  padding: 6px 12px;
  font-weight: 500;
  border-radius: 24px;
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
  .collection-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .collection-query {
    grid-column: 1 / -1;
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
  .collection-fields {
    grid-template-columns: 1fr;
  }
  .collection-actions > button {
    width: 100%;
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

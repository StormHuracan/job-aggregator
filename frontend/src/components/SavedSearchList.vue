<template>
  <section aria-label="Сохранённые поиски">
    <EmptyState
      v-if="searches.length === 0"
      title="Сохранённых поисков пока нет"
      description="Создайте первый поиск, чтобы не вводить одни и те же параметры заново."
    />
    <ul v-else>
      <li
        v-for="search in searches"
        :key="search.id"
        :aria-busy="pendingIds.includes(search.id)"
      >
        <div class="criteria">
          <h3>{{ search.name }}</h3>
          <p>
            {{ search.text
            }}<span v-if="search.area"> · {{ search.area }}</span>
          </p>
          <p v-if="search.min_salary !== null || search.max_salary !== null">
            Зарплата:
            <span v-if="search.min_salary !== null"
              >от {{ format(search.min_salary) }}</span
            >
            <span v-if="search.max_salary !== null">
              до {{ format(search.max_salary) }}</span
            >
          </p>
          <p
            v-if="toggleErrors[search.id]"
            :id="'toggle-error-' + search.id"
            class="error"
            role="alert"
          >
            {{ toggleErrors[search.id] }}
          </p>
        </div>
        <div class="search-actions">
          <UiButton
            variant="ghost"
            :disabled="pendingIds.includes(search.id)"
            :aria-label="`Удалить поиск «${search.name}»`"
            @click="emit('delete', search)"
            >Удалить</UiButton
          >
          <UiSwitch
            :model-value="search.is_enabled"
            :label="`Активность поиска «${search.name}»`"
            :disabled="pendingIds.includes(search.id)"
            :aria-busy="pendingIds.includes(search.id) || undefined"
            :described-by="
              toggleErrors[search.id] ? 'toggle-error-' + search.id : undefined
            "
            @update:model-value="emit('toggle', search.id, $event)"
          >
            {{ search.is_enabled ? "Включён" : "Выключен" }}
          </UiSwitch>
          <RouterLink
            class="results-link"
            :to="{
              path: '/vacancies',
              query: {
                text: search.text,
                area: search.area || undefined,
                salary_from: search.min_salary ?? undefined,
                salary_to: search.max_salary ?? undefined,
                limit: 20,
                offset: 0,
              },
            }"
            >Показать вакансии <UiIcon name="chevron-right" :size="16"
          /></RouterLink>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "./ui/EmptyState.vue";
import UiSwitch from "./ui/UiSwitch.vue";
import UiButton from "./ui/UiButton.vue";
import UiIcon from "./ui/UiIcon.vue";
import { RouterLink } from "vue-router";
import type { SavedSearch } from "../api/saved-searches";
withDefaults(
  defineProps<{
    searches: SavedSearch[];
    pendingIds?: number[];
    toggleErrors?: Record<number, string>;
  }>(),
  { pendingIds: () => [], toggleErrors: () => ({}) },
);
const emit = defineEmits<{
  toggle: [id: number, enabled: boolean];
  delete: [search: SavedSearch];
}>();
const format = (value: number) => new Intl.NumberFormat("ru-RU").format(value);
</script>

<style scoped>
ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
li {
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: var(--space-4);
  justify-content: space-between;
  padding: 16px 22px;
}
li:last-child {
  border-bottom: 0;
}
.criteria {
  min-width: 0;
  overflow-wrap: anywhere;
}
h3 {
  font-size: 18px;
  color: var(--color-ink);
}
p {
  font-size: 14px;
  color: var(--color-muted);
  margin: var(--space-1) 0 0;
}
.empty-state {
  color: var(--color-muted);
  margin: var(--space-4) 0;
}
.error {
  color: var(--color-danger);
}
.search-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 24px;
}
.results-link {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  gap: 4px;
  font-size: 14px;
  font-weight: 600;
}
@media (max-width: 640px) {
  li {
    padding: 16px;
    flex-direction: column;
    align-items: stretch;
  }
  .search-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
}
@media (max-width: 28rem) {
  li {
    align-items: start;
    flex-direction: column;
  }
}
</style>

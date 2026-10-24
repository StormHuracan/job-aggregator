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
          <strong>{{ search.name }}</strong>
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
        <label class="switch">
          <input
            :checked="search.is_enabled"
            :disabled="pendingIds.includes(search.id)"
            type="checkbox"
            :aria-label="'Поиск «' + search.name + '»: включён'"
            :aria-describedby="
              toggleErrors[search.id] ? 'toggle-error-' + search.id : undefined
            "
            @change="toggle($event, search)"
          />
          <span>{{
            pendingIds.includes(search.id)
              ? "Сохраняем…"
              : search.is_enabled
                ? "Включён"
                : "Выключен"
          }}</span>
        </label>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "./ui/EmptyState.vue";
import type { SavedSearch } from "../api/saved-searches";
withDefaults(
  defineProps<{
    searches: SavedSearch[];
    pendingIds?: number[];
    toggleErrors?: Record<number, string>;
  }>(),
  { pendingIds: () => [], toggleErrors: () => ({}) },
);
const emit = defineEmits<{ toggle: [id: number, enabled: boolean] }>();
const format = (value: number) => new Intl.NumberFormat("ru-RU").format(value);
function toggle(event: Event, search: SavedSearch): void {
  // До ответа сервера сохраняем прежнее состояние checkbox, в том числе при ошибке.
  (event.target as HTMLInputElement).checked = search.is_enabled;
  emit("toggle", search.id, !search.is_enabled);
}
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
  padding: 20px 24px;
}
li:last-child {
  border-bottom: 0;
}
.criteria {
  min-width: 0;
  overflow-wrap: anywhere;
}
strong {
  font-size: 16px;
  color: var(--color-ink);
}
p {
  font-size: 14px;
  color: var(--color-muted);
  margin: var(--space-1) 0 0;
}
.switch {
  align-items: center;
  display: inline-flex;
  flex: none;
  gap: var(--space-2);
  white-space: nowrap;
}
.switch input {
  appearance: none;
  background: #a2aab7;
  border: 0;
  border-radius: 20px;
  cursor: pointer;
  height: 24px;
  min-height: 24px;
  padding: 3px;
  position: relative;
  width: 40px;
}
.switch input::before {
  background: white;
  border-radius: 50%;
  content: "";
  display: block;
  height: 18px;
  width: 18px;
}
.switch input:checked {
  background: var(--color-link);
}
.switch input:checked::before {
  transform: translateX(16px);
}
.switch {
  min-height: 44px;
  font-size: 13px;
  font-weight: 500;
}
.switch input:disabled {
  opacity: 0.6;
  cursor: wait;
}
.empty-state {
  color: var(--color-muted);
  margin: var(--space-4) 0;
}
.error {
  color: var(--color-danger);
}
@media (max-width: 28rem) {
  li {
    align-items: start;
    flex-direction: column;
  }
}
</style>

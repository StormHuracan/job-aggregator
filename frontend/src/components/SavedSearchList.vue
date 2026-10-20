<template>
  <section aria-label="Сохранённые поиски">
    <p v-if="searches.length === 0" class="empty-state">Сохранённых поисков пока нет. Создайте первый поиск.</p>
    <ul v-else>
      <li v-for="search in searches" :key="search.id" :aria-busy="pendingIds.includes(search.id)">
        <div class="criteria">
          <strong>{{ search.name }}</strong>
          <p>{{ search.text }}<span v-if="search.area"> · {{ search.area }}</span></p>
          <p v-if="search.min_salary !== null || search.max_salary !== null">
            Зарплата: <span v-if="search.min_salary !== null">от {{ format(search.min_salary) }}</span>
            <span v-if="search.max_salary !== null"> до {{ format(search.max_salary) }}</span>
          </p>
          <p v-if="toggleErrors[search.id]" :id="'toggle-error-' + search.id" class="error" role="alert">{{ toggleErrors[search.id] }}</p>
        </div>
        <label class="switch">
          <input :checked="search.is_enabled" :disabled="pendingIds.includes(search.id)" type="checkbox"
            :aria-label="'Поиск «' + search.name + '»: включён'"
            :aria-describedby="toggleErrors[search.id] ? 'toggle-error-' + search.id : undefined"
            @change="toggle($event, search)" />
          <span>{{ pendingIds.includes(search.id) ? "Сохраняем…" : search.is_enabled ? "Включён" : "Выключен" }}</span>
        </label>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { SavedSearch } from "../api/saved-searches";
withDefaults(defineProps<{
  searches: SavedSearch[];
  pendingIds?: number[];
  toggleErrors?: Record<number, string>;
}>(), { pendingIds: () => [], toggleErrors: () => ({}) });
const emit = defineEmits<{ toggle: [id: number, enabled: boolean] }>();
const format = (value: number) => new Intl.NumberFormat("ru-RU").format(value);
function toggle(event: Event, search: SavedSearch): void {
  // До ответа сервера сохраняем прежнее состояние checkbox, в том числе при ошибке.
  (event.target as HTMLInputElement).checked = search.is_enabled;
  emit("toggle", search.id, !search.is_enabled);
}
</script>

<style scoped>
ul { list-style: none; margin: 0; padding: 0; }
li { align-items: center; border-bottom: 1px solid var(--color-border); display: flex; gap: var(--space-4); justify-content: space-between; padding: var(--space-4) 0; }
.criteria { min-width: 0; overflow-wrap: anywhere; }
strong { color: var(--color-ink); }
p { color: var(--color-muted); margin: var(--space-1) 0 0; }
.switch { align-items: center; display: inline-flex; flex: none; gap: var(--space-2); white-space: nowrap; }
.switch input { accent-color: var(--color-link); }
.empty-state { color: var(--color-muted); margin: var(--space-4) 0; }
.error { color: var(--color-danger); }
@media (max-width: 28rem) { li { align-items: start; flex-direction: column; } }
</style>

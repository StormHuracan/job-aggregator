<template>
  <section class="saved-searches">
    <div class="saved-heading"><div><h1>Сохранённые поиски</h1><p>Настройте направления, которые стоит проверять регулярно.</p></div></div>
    <div class="saved-layout"><div class="new-search"><h2>Новый поиск</h2><SavedSearchForm @create="created" /></div><div class="searches-list"><div class="list-heading"><h2>Ваши направления</h2><p>{{ searches.length }} активных или сохранённых</p></div><SavedSearchList :searches="searches" @toggle="toggled" /></div></div>
  </section>
</template>
<script setup lang="ts">
import type { SavedSearchCreate } from "../api/saved-searches";
import SavedSearchForm from "../components/SavedSearchForm.vue";
import SavedSearchList from "../components/SavedSearchList.vue";
import { useSavedSearches } from "../composables/useSavedSearches";

const { createSearch, searches, setEnabled } = useSavedSearches();
function created(search: SavedSearchCreate): void { createSearch(search); }
function toggled(id: number, enabled: boolean): void { setEnabled(id, enabled); }
</script>
<style scoped>
.saved-heading { margin-bottom: var(--space-8); }.saved-heading h1 { margin-bottom: var(--space-3); }.saved-heading p { color: var(--color-muted); margin: 0; max-width: 52ch; }
.saved-layout { align-items: start; display: grid; gap: var(--space-8); grid-template-columns: minmax(16rem, 0.7fr) minmax(0, 1.3fr); }.new-search { background: #f4f7fa; border: 1px solid var(--color-border); padding: var(--space-6); }.new-search h2, .list-heading h2 { font-size: 1.1rem; margin: 0 0 var(--space-4); }.saved-searches :deep(form) { display: grid; gap: 1rem; }.saved-searches :deep(form button) { justify-self: start; }.list-heading { border-bottom: 1px solid var(--color-border); margin-bottom: var(--space-2); padding-bottom: var(--space-4); }.list-heading h2 { margin-bottom: var(--space-1); }.list-heading p { color: var(--color-muted); font-size: 0.9rem; margin: 0; }
@media (max-width: 42rem) { .saved-layout { grid-template-columns: 1fr; } }
</style>

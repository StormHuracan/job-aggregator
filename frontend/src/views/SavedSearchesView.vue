<template>
  <section class="saved-searches">
    <div class="saved-heading"><div><h1>Сохранённые поиски</h1><p>Настройте направления, которые стоит проверять регулярно.</p></div></div>
    <div class="saved-layout">
      <div class="new-search">
        <h2>Новый поиск</h2>
        <SavedSearchForm :disabled="loading || loadError !== null" :submitting="creating"
          :field-errors="fieldErrors" :reset-key="resetKey" @create="createSearch" @clear-errors="clearCreateErrors" />
        <p v-if="createError" class="error" role="alert">{{ createError }}</p>
      </div>
      <div class="searches-list">
        <div class="list-heading"><h2>Ваши направления</h2><p>{{ searches.length }} активных или сохранённых</p></div>
        <AsyncState :loading="loading" :error="loadError">
          <SavedSearchList :searches="searches" :pending-ids="pendingIds" :toggle-errors="toggleErrors" @toggle="setEnabled" />
          <template #error-actions><button data-action="reload" type="button" @click="reload">Повторить</button></template>
        </AsyncState>
      </div>
    </div>
  </section>
</template>
<script setup lang="ts">
import AsyncState from "../components/AsyncState.vue";
import SavedSearchForm from "../components/SavedSearchForm.vue";
import SavedSearchList from "../components/SavedSearchList.vue";
import { useSavedSearches } from "../composables/useSavedSearches";

const { createSearch, searches, setEnabled, loading, loadError, creating, createError,
  fieldErrors, pendingIds, toggleErrors, resetKey, reload, clearCreateErrors } = useSavedSearches();
</script>
<style scoped>
.saved-heading { margin-bottom: var(--space-8); }.saved-heading h1 { margin-bottom: var(--space-3); }.saved-heading p { color: var(--color-muted); margin: 0; max-width: 52ch; }
.saved-layout { align-items: start; display: grid; gap: var(--space-8); grid-template-columns: minmax(16rem, 0.7fr) minmax(0, 1.3fr); }.new-search { background: #f4f7fa; border: 1px solid var(--color-border); padding: var(--space-6); }.new-search h2, .list-heading h2 { font-size: 1.1rem; margin: 0 0 var(--space-4); }.saved-searches :deep(form) { display: grid; gap: 1rem; }.saved-searches :deep(form button) { justify-self: start; }.list-heading { border-bottom: 1px solid var(--color-border); margin-bottom: var(--space-2); padding-bottom: var(--space-4); }.list-heading h2 { margin-bottom: var(--space-1); }.list-heading p { color: var(--color-muted); font-size: 0.9rem; margin: 0; }
@media (max-width: 42rem) { .saved-layout { grid-template-columns: 1fr; } }
.error { color: var(--color-danger); }
</style>

<template>
  <section>
    <h1>Сохранённые поиски</h1>
    <SavedSearchForm @create="created" />
    <SavedSearchList :searches="searches" @toggle="toggled" />
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

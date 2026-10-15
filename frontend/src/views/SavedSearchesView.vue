<template>
  <section>
    <h1>Сохранённые поиски</h1>
    <SavedSearchForm @create="created" />
    <p>Сохранённые поиски появятся после подключения публичного API.</p>
  </section>
</template>
<script setup lang="ts">import type { SavedSearchCreate } from "../api/saved-searches";import SavedSearchForm from "../components/SavedSearchForm.vue";function created(_search: SavedSearchCreate):void {}</script>

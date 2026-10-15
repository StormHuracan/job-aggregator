<template>
  <section>
    <h1>Сохранённые поиски</h1>
    <SavedSearchForm @create="created" />
    <SavedSearchList :searches="searches" @toggle="toggled" />
  </section>
</template>
<script setup lang="ts">import { ref } from "vue";import type { SavedSearch, SavedSearchCreate } from "../api/saved-searches";import SavedSearchForm from "../components/SavedSearchForm.vue";import SavedSearchList from "../components/SavedSearchList.vue";const searches=ref<SavedSearch[]>([]);function created(_search: SavedSearchCreate):void {} function toggled(_id:number,_enabled:boolean):void {}</script>

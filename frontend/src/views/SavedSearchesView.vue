<template>
  <section v-if="!sessionExpired" aria-labelledby="saved-heading">
    <div class="page-heading">
      <div>
        <h1 id="saved-heading">Сохранённые поиски</h1>
        <p>
          Сохраните подходящие параметры и возвращайтесь к ним в удобный момент.
        </p>
      </div>
      <UiButton
        data-action="new-search"
        :disabled="loading || !!loadError || creating"
        @click="openForm"
        ><UiIcon name="plus" />Новый поиск</UiButton
      >
    </div>
    <UiAlert v-if="showSuccess" tone="success"
      >Поиск сохранён. Его параметры появились в списке.</UiAlert
    >
    <UiAlert v-if="deleteSuccess" tone="success">Поиск удалён.</UiAlert>
    <AsyncState :loading="loading" :error="loadError"
      ><template #loading><UiSkeleton variant="vacancy" /></template
      ><template #error-actions
        ><UiButton data-action="reload" variant="secondary" @click="reload"
          >Повторить</UiButton
        ></template
      >
      <div>
        <div class="searches-list">
          <div class="section-heading">
            <h2>Ваши поиски</h2>
            <p>{{ searches.length }} сохранено</p>
          </div>
          <div class="panel">
            <SavedSearchList
              :searches="searches"
              :pending-ids="pendingIds"
              :toggle-errors="toggleErrors"
              @toggle="setEnabled"
              @delete="deleteTarget = $event"
            />
          </div>
          <p id="activity-hint" class="field-hint activity-hint">
            Активность определяет участие поиска в плановом сборе. Переключение
            не запускает загрузку; автоматическое расписание пока не подключено.
            Просмотр вакансий открывает уже собранные результаты.
          </p>
        </div>
      </div>
    </AsyncState>
    <SavedSearchDialog
      :open="formOpen"
      :submitting="creating"
      :field-errors="fieldErrors"
      :error="createError"
      @create="createSearch"
      @clear-errors="clearCreateErrors"
      @close="formOpen = false"
    />
    <UiDialog
      :open="deleteTarget !== null"
      title="Удалить сохранённый поиск?"
      @close="deleteTarget = null"
    >
      <UiAlert
        v-if="deleteTarget && toggleErrors[deleteTarget.id]"
        tone="error"
        >{{ toggleErrors[deleteTarget.id] }}</UiAlert
      >
      <p>
        Поиск «{{ deleteTarget?.name }}» и его совпадения будут удалены. Сами
        вакансии останутся. Отменить удаление нельзя.
      </p>
      <UiButton :busy="deleting" @click="confirmDelete">{{
        deleting ? "Удаляем…" : "Удалить поиск"
      }}</UiButton>
      <UiButton variant="ghost" @click="deleteTarget = null">Отмена</UiButton>
    </UiDialog>
  </section>
</template>
<script setup lang="ts">
import { ref, watch } from "vue";
import type { SavedSearch } from "../api/saved-searches";
import UiDialog from "../components/ui/UiDialog.vue";
import AsyncState from "../components/AsyncState.vue";
import SavedSearchDialog from "../components/SavedSearchDialog.vue";
import UiSkeleton from "../components/ui/UiSkeleton.vue";
import UiIcon from "../components/ui/UiIcon.vue";
import SavedSearchList from "../components/SavedSearchList.vue";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
import { useSavedSearches } from "../composables/useSavedSearches";
const {
  sessionExpired,
  createSearch,
  searches,
  setEnabled,
  removeSearch,
  loading,
  loadError,
  creating,
  createError,
  fieldErrors,
  pendingIds,
  toggleErrors,
  resetKey,
  reload,
  clearCreateErrors,
} = useSavedSearches();
const formOpen = ref(false);
const deleteTarget = ref<SavedSearch | null>(null);
const deleting = ref(false);
const deleteSuccess = ref(false);
async function confirmDelete() {
  if (!deleteTarget.value || deleting.value) return;
  const id = deleteTarget.value.id;
  deleteSuccess.value = false;
  deleting.value = true;
  const removed = await removeSearch(id);
  deleting.value = false;
  if (removed) deleteSuccess.value = true;
  if ((removed && deleteTarget.value?.id === id) || sessionExpired.value)
    deleteTarget.value = null;
}
const showSuccess = ref(false);
watch(resetKey, () => {
  formOpen.value = false;
  showSuccess.value = true;
});
function openForm(): void {
  if (creating.value) return;
  clearCreateErrors();
  showSuccess.value = false;
  formOpen.value = true;
}
</script>
<style scoped>
.activity-hint {
  max-width: 100ch;
  margin: 16px 0 0;
  font-size: 13px;
}
.section-heading {
  margin: 0 0 8px;
  min-height: 32px;
}
@media (max-width: 640px) {
  .page-heading {
    flex-direction: column;
  }
  .page-heading > button {
    width: 100%;
  }
}
</style>

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
        :disabled="loading || !!loadError"
        :aria-expanded="formOpen"
        aria-controls="new-search"
        @click="openForm"
        >Новый поиск <span aria-hidden="true">+</span></UiButton
      >
    </div>
    <UiAlert v-if="resetKey > 0" tone="success"
      >Поиск сохранён. Его параметры появились в списке.</UiAlert
    >
    <AsyncState
      :loading="loading"
      :error="
        loadError
          ? `Не удалось загрузить сохранённые поиски. ${loadError}. Попробуйте ещё раз.`
          : null
      "
      ><template #error-actions
        ><UiButton data-action="reload" variant="secondary" @click="reload"
          >Повторить</UiButton
        ></template
      >
      <div class="saved-layout">
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
            />
          </div>
        </div>
        <details
          id="new-search"
          ref="formPanel"
          class="new-search panel"
          :open="formOpen"
          @toggle="formOpen = ($event.target as HTMLDetailsElement).open"
        >
          <summary>
            Создать новый поиск<span aria-hidden="true">+</span>
          </summary>
          <div class="form-content">
            <p class="field-hint form-intro">
              Укажите запрос. Регион и зарплату можно оставить пустыми.
            </p>
            <SavedSearchForm
              :disabled="loading || loadError !== null"
              :submitting="creating"
              :field-errors="fieldErrors"
              :reset-key="resetKey"
              @create="createSearch"
              @clear-errors="clearCreateErrors"
            /><UiAlert v-if="createError" tone="error" class="create-error">{{
              createError
            }}</UiAlert>
          </div>
        </details>
      </div>
    </AsyncState>
  </section>
</template>
<script setup lang="ts">
import { nextTick, ref } from "vue";
import AsyncState from "../components/AsyncState.vue";
import SavedSearchForm from "../components/SavedSearchForm.vue";
import SavedSearchList from "../components/SavedSearchList.vue";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
import { useSavedSearches } from "../composables/useSavedSearches";
const {
  sessionExpired,
  createSearch,
  searches,
  setEnabled,
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
const formPanel = ref<HTMLDetailsElement>();
async function openForm(): Promise<void> {
  formOpen.value = true;
  await nextTick();
  formPanel.value
    ?.querySelector<HTMLInputElement>('input[name="name"]')
    ?.focus();
}
</script>
<style scoped>
.saved-layout {
  align-items: start;
  display: grid;
  gap: 32px;
  grid-template-columns: minmax(0, 1fr) 360px;
}
.section-heading {
  margin: 0 0 16px;
  min-height: 32px;
}
.new-search {
  margin-top: 48px;
}
.new-search summary {
  align-items: center;
  display: flex;
  font-size: 15px;
  font-weight: 700;
  justify-content: space-between;
  list-style: none;
  padding: 18px 20px;
}
.new-search summary::-webkit-details-marker {
  display: none;
}
.new-search[open] summary {
  border-bottom: 1px solid var(--color-border);
}
.new-search[open] summary span {
  transform: rotate(45deg);
}
.form-content {
  padding: 20px;
}
.form-intro {
  margin-bottom: 20px;
}
.create-error {
  margin: 20px 0 0;
}
@media (max-width: 800px) {
  .saved-layout {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  .new-search {
    margin-top: 0;
  }
}
@media (max-width: 640px) {
  .page-heading {
    flex-direction: column;
  }
  .page-heading > button {
    width: 100%;
  }
  .form-content {
    padding: 16px;
  }
}
</style>

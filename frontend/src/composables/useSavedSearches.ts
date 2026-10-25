import { onMounted, onScopeDispose, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "../api/client";
import {
  createSavedSearch,
  deleteSavedSearch,
  listSavedSearches,
  setSavedSearchEnabled,
  type SavedSearch,
  type SavedSearchCreate,
} from "../api/saved-searches";

export function useSavedSearches() {
  const router = useRouter();
  const returnTo = useRoute().fullPath;
  let active = true;
  const sessionExpired = ref(false);
  const isActive = () => active && !sessionExpired.value;
  onScopeDispose(() => {
    active = false;
  });
  const searches = ref<SavedSearch[]>([]);
  const loading = ref(false);
  const loadError = ref<string | null>(null);
  const creating = ref(false);
  const createError = ref<string | null>(null);
  const fieldErrors = ref<Readonly<Record<string, string>>>({});
  const pendingIds = ref<number[]>([]);
  const toggleErrors = ref<Record<number, string>>({});
  const resetKey = ref(0);

  async function handleError(error: unknown): Promise<string> {
    if (isActive() && error instanceof ApiError && error.status === 401) {
      sessionExpired.value = true;
      searches.value = [];
      fieldErrors.value = {};
      createError.value = null;
      toggleErrors.value = {};
      await router.replace({
        path: "/login",
        query: { redirect: returnTo, reason: "session-expired" },
      });
    }
    return error instanceof ApiError
      ? error.message
      : "Не удалось выполнить запрос";
  }

  async function reload(): Promise<void> {
    if (
      !isActive() ||
      loading.value ||
      creating.value ||
      pendingIds.value.length > 0
    )
      return;
    loading.value = true;
    loadError.value = null;
    try {
      const result = await listSavedSearches();
      if (isActive()) searches.value = result;
    } catch (error) {
      const message = await handleError(error);
      if (isActive()) {
        searches.value = [];
        loadError.value = message;
      }
    } finally {
      loading.value = false;
    }
  }

  function clearCreateErrors(): void {
    createError.value = null;
    fieldErrors.value = {};
  }

  async function createSearch(input: SavedSearchCreate): Promise<void> {
    if (!isActive() || creating.value || loading.value || loadError.value)
      return;
    creating.value = true;
    clearCreateErrors();
    try {
      const saved = await createSavedSearch(input);
      if (!isActive()) return;
      searches.value = [...searches.value, saved].sort((a, b) => a.id - b.id);
      resetKey.value++;
    } catch (error) {
      const message = await handleError(error);
      if (isActive()) {
        fieldErrors.value = error instanceof ApiError ? error.fieldErrors : {};
        createError.value = message;
      }
    } finally {
      creating.value = false;
    }
  }

  async function setEnabled(id: number, enabled: boolean): Promise<void> {
    if (!isActive() || loading.value || pendingIds.value.includes(id)) return;
    pendingIds.value = [...pendingIds.value, id];
    delete toggleErrors.value[id];
    try {
      const saved = await setSavedSearchEnabled(id, enabled);
      if (isActive())
        searches.value = searches.value.map((search) =>
          search.id === id ? saved : search,
        );
    } catch (error) {
      const message = await handleError(error);
      if (isActive()) toggleErrors.value[id] = message;
    } finally {
      pendingIds.value = pendingIds.value.filter((pending) => pending !== id);
    }
  }

  async function removeSearch(id: number): Promise<boolean> {
    if (!isActive() || loading.value || pendingIds.value.includes(id))
      return false;
    pendingIds.value = [...pendingIds.value, id];
    delete toggleErrors.value[id];
    try {
      await deleteSavedSearch(id);
      if (!isActive()) return false;
      searches.value = searches.value.filter((search) => search.id !== id);
      return true;
    } catch (error) {
      const message = await handleError(error);
      if (isActive()) toggleErrors.value[id] = message;
      return false;
    } finally {
      pendingIds.value = pendingIds.value.filter((pending) => pending !== id);
    }
  }

  onMounted(reload);
  return {
    searches,
    sessionExpired,
    loading,
    loadError,
    creating,
    createError,
    fieldErrors,
    pendingIds,
    toggleErrors,
    resetKey,
    reload,
    createSearch,
    setEnabled,
    removeSearch,
    clearCreateErrors,
  };
}

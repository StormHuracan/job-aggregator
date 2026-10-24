import { onMounted, onScopeDispose, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "../api/client";
import {
  getCurrentUser,
  logout,
  markMatchesSeen,
  updateSettings,
  type CurrentUser,
} from "../api/user";

/** Состояние кабинета принадлежит странице; поздние ответы после ухода игнорируются. */
export function useAccount() {
  const router = useRouter();
  const returnTo = useRoute().fullPath;
  const user = ref<CurrentUser | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const defaultArea = ref("");
  const pagesLimit = ref(1);
  const pending = ref<string | null>(null);
  const feedback = ref("");
  const actionError = ref(false);
  const fieldErrors = ref<Readonly<Record<string, string>>>({});
  let active = true;
  const sessionExpired = ref(false);
  const isActive = () => active && !sessionExpired.value;
  onScopeDispose(() => {
    active = false;
  });

  async function failure(cause: unknown): Promise<string> {
    if (isActive() && cause instanceof ApiError && cause.status === 401) {
      sessionExpired.value = true;
      user.value = null;
      feedback.value = "";
      fieldErrors.value = {};
      await router.replace({
        path: "/login",
        query: { redirect: returnTo, reason: "session-expired" },
      });
    }
    return cause instanceof ApiError
      ? cause.message
      : "Не удалось выполнить действие. Попробуйте ещё раз.";
  }

  async function load(): Promise<void> {
    if (!isActive() || loading.value || pending.value) return;
    loading.value = true;
    user.value = null;
    error.value = null;
    feedback.value = "";
    try {
      const response = await getCurrentUser();
      if (!isActive()) return;
      user.value = response;
      defaultArea.value = response.settings.default_area ?? "";
      pagesLimit.value = response.settings.default_pages_limit;
    } catch (cause) {
      const message = await failure(cause);
      if (isActive()) error.value = message;
    } finally {
      loading.value = false;
    }
  }

  async function action(
    name: string,
    operation: () => Promise<void>,
    success: string,
  ): Promise<void> {
    if (!isActive() || !user.value || pending.value || loading.value) return;
    pending.value = name;
    feedback.value = "";
    fieldErrors.value = {};
    actionError.value = false;
    try {
      await operation();
      if (isActive()) feedback.value = success;
    } catch (cause) {
      const message = await failure(cause);
      if (isActive()) {
        feedback.value =
          cause instanceof ApiError && cause.status === 422
            ? "Проверьте отмеченные поля настроек."
            : message;
        actionError.value = true;
        if (cause instanceof ApiError) fieldErrors.value = cause.fieldErrors;
      }
    } finally {
      pending.value = null;
    }
  }

  async function save(): Promise<void> {
    if (!Number.isSafeInteger(pagesLimit.value) || pagesLimit.value < 1) {
      fieldErrors.value = { default_pages_limit: "Введите целое число от 1" };
      return;
    }
    await action(
      "save",
      async () => {
        const settings = await updateSettings({
          default_area: defaultArea.value.trim() || null,
          default_pages_limit: pagesLimit.value,
        });
        if (!isActive() || !user.value) return;
        user.value.settings = settings;
        defaultArea.value = settings.default_area ?? "";
        pagesLimit.value = settings.default_pages_limit;
      },
      "Настройки сохранены.",
    );
  }

  async function markSeen(): Promise<void> {
    await action(
      "seen",
      async () => {
        await markMatchesSeen();
        if (isActive() && user.value) user.value.new_matches_count = 0;
      },
      "Совпадения отмечены прочитанными.",
    );
  }

  async function signOut(): Promise<void> {
    await action(
      "logout",
      async () => {
        await logout();
        if (!isActive()) return;
        sessionExpired.value = true;
        user.value = null;
        await router.replace("/login");
      },
      "",
    );
  }
  function clearFieldError(field: string): void {
    const next = { ...fieldErrors.value };
    delete next[field];
    fieldErrors.value = next;
    feedback.value = "";
  }
  onMounted(load);
  return {
    user,
    sessionExpired,
    loading,
    error,
    defaultArea,
    pagesLimit,
    pending,
    feedback,
    actionError,
    fieldErrors,
    load,
    save,
    markSeen,
    signOut,
    clearFieldError,
  };
}

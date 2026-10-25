<script setup lang="ts">
import { onMounted, onScopeDispose, ref } from "vue";
import { useRouter } from "vue-router";
import { request, ApiError } from "../api/client";
import UiButton from "./ui/UiButton.vue";
import UiAlert from "./ui/UiAlert.vue";

const router = useRouter();
const emit = defineEmits<{ sessionExpired: [] }>();
const busy = ref(false);
const link = ref<string | null>(null);
const expires = ref<number | null>(null);
const feedback = ref("");
const failed = ref(false);
const status = ref<{ enabled: boolean; connected: boolean } | null>(null);
const checking = ref(false);
let active = true;
let expiryTimer: ReturnType<typeof setTimeout> | undefined;
onScopeDispose(() => {
  active = false;
  clearTimeout(expiryTimer);
});

async function refreshStatus() {
  if (checking.value || busy.value) return;
  checking.value = true;
  try {
    const result = await request<{ enabled: boolean; connected: boolean }>("/me/telegram");
    if (!active) return;
    status.value = typeof result.enabled === "boolean" && typeof result.connected === "boolean" ? result : null;
    if (status.value?.connected) {
      link.value = null;
      feedback.value = "";
      clearTimeout(expiryTimer);
    }
  } catch (error) {
    if (active) {
      status.value = null;
      if (error instanceof ApiError && error.status === 401) {
        emit("sessionExpired");
        await router.replace({ path: "/login", query: { redirect: "/account", reason: "session-expired" } });
      }
    }
  } finally {
    if (active) checking.value = false;
  }
}
onMounted(refreshStatus);

async function perform(disconnect: boolean) {
  if (busy.value) return;
  busy.value = true;
  feedback.value = "";
  failed.value = false;
  link.value = null;
  clearTimeout(expiryTimer);
  try {
    if (disconnect) {
      await request<void>("/me/telegram", { method: "DELETE" });
      if (active) {
        if (status.value) status.value.connected = false;
        feedback.value = "Telegram отключён. Уведомления больше не отправляются.";
      }
    } else {
      const result = await request<{ url: string; expires_at: string }>(
        "/me/telegram/link", { method: "POST" },
      );
      if (!active) return;
      const url = new URL(result.url);
      const deadline = Date.parse(result.expires_at);
      if (url.protocol !== "https:" || url.hostname !== "t.me" || url.port ||
          url.username || url.password || !Number.isFinite(deadline) || deadline <= Date.now()) {
        throw new Error("Invalid Telegram link");
      }
      link.value = url.href;
      expires.value = deadline;
      expiryTimer = setTimeout(() => {
        link.value = null;
        feedback.value = "Ссылка истекла. Создайте новую ссылку для подключения.";
      }, Math.min(deadline - Date.now(), 2_147_483_647));
      feedback.value = "Откройте бота и нажмите Start. Создание ссылки ещё не подтверждает привязку.";
    }
  } catch (error) {
    if (!active) return;
    failed.value = true;
    if (error instanceof ApiError && error.status === 401) {
      emit("sessionExpired");
      await router.replace({ path: "/login", query: { redirect: "/account", reason: "session-expired" } });
      return;
    }
    feedback.value = error instanceof ApiError && error.status === 409
      ? "Telegram уже привязан. Для смены чата сначала отключите текущую привязку."
      : error instanceof ApiError && error.status === 503
        ? "Telegram-уведомления пока не настроены на сервере."
        : "Не удалось выполнить действие. Попробуйте ещё раз.";
  } finally {
    if (active) busy.value = false;
  }
}
</script>

<template>
  <section class="telegram-block" aria-labelledby="telegram-heading">
    <h2 id="telegram-heading">Telegram-уведомления</h2>
    <p>Подключите бота, чтобы получать новые совпадения по сохранённым поискам. Привязку подтверждает сам бот.</p>
    <p role="status">{{ checking ? "Проверяем подключение…" : status?.connected ? "Telegram подключён" : status ? "Telegram не подключён" : "Статус подключения недоступен" }}{{ status && !status.enabled ? ". Отправка уведомлений на сервере отключена." : "" }}</p>
    <div class="telegram-actions">
      <UiButton :busy="busy" :disabled="checking || status?.connected || (status !== null && !status.enabled)" @click="perform(false)">Подключить Telegram</UiButton>
      <UiButton variant="secondary" :disabled="busy || checking" @click="perform(true)">Отключить Telegram</UiButton>
      <UiButton variant="ghost" :disabled="busy || checking" @click="refreshStatus">Обновить статус</UiButton>
    </div>
    <UiAlert v-if="feedback" :tone="failed ? 'error' : 'success'">{{ feedback }}</UiAlert>
    <a v-if="link" :href="link" target="_blank" rel="noopener noreferrer">Открыть бота в Telegram ↗</a>
    <p v-if="link && expires" class="field-hint">Ссылка действует до {{ new Date(expires).toLocaleTimeString("ru-RU") }}. После подключения новые совпадения отправляются автоматически; старые не рассылаются.</p>
  </section>
</template>

<style scoped>
.telegram-block { margin-top: 24px; padding: 24px; border: 1px solid var(--color-border); border-radius: 16px; }
.telegram-actions { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
.telegram-block p { max-width: 65ch; }
.telegram-block a { display: inline-block; margin-top: 12px; }
</style>

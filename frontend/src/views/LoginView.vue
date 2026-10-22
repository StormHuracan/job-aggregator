<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { request } from "../api/client";
import HHCodeLogin from "../components/HHCodeLogin.vue";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
const route = useRoute();
const router = useRouter();
const method = ref<"otp" | "oauth" | null>(null);
const error = ref("");
const loading = ref(false);
const retrying = ref(false);
let active = true;
onScopeDispose(() => { active = false; });
const oauthUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "") + "/auth/hh/login";
const authMessage = computed(() => {
  if (route.query.reason === "session-check-failed")
    return "Не удалось проверить вход. Защищённые данные не загружены. Попробуйте ещё раз.";
  if (route.query.reason === "auth-required")
    return "Для просмотра этого раздела войдите через HH.ru.";
  if (route.query.reason === "session-expired")
    return "Сессия истекла. Войдите снова, чтобы продолжить.";
  return route.query.error ? "Не удалось завершить вход. Попробуйте подключиться ещё раз." : "";
});
async function loadOptions(): Promise<void> {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const options = await request<{ method: string }>("/auth/hh/options");
    if (options.method !== "otp" && options.method !== "oauth") throw new Error("Invalid login mode");
    if (active) method.value = options.method;
  } catch {
    if (active) error.value = "Не удалось начать вход. Проверьте подключение и попробуйте ещё раз.";
  } finally { loading.value = false; }
}
async function retrySession(): Promise<void> {
  if (retrying.value) return;
  retrying.value = true;
  const target = route.query.redirect;
  const internal = typeof target === "string" && target.startsWith("/") && !target.startsWith("//");
  try {
    await router.replace(internal && router.resolve(target).meta.requiresAuth ? target : "/account");
  } finally { retrying.value = false; }
}
onMounted(loadOptions);
</script>
<template>
  <section class="login-layout" aria-labelledby="login-heading">
    <div class="login-story">
      <span class="story-logo" aria-hidden="true">JA</span>
      <h2>Меньше повторяющихся запросов.<br />Больше подходящих вакансий.</h2>
      <p>Ищите вакансии для разработчиков и сохраняйте параметры, к которым хочется вернуться.</p>
      <span class="story-caption">Job Aggregator</span>
    </div>
    <div class="login-card panel">
      <span class="login-mark" aria-hidden="true">JA</span>
      <h1 id="login-heading">Войти через HH.ru</h1>
      <p class="login-copy">Войдите, чтобы работать со своими сохранёнными поисками.</p>
      <UiAlert v-if="authMessage" :tone="route.query.reason === 'auth-required' ? 'info' : 'error'">{{ authMessage }}</UiAlert>
      <UiButton v-if="route.query.reason === 'session-check-failed'" class="retry-session"
        variant="secondary" :disabled="retrying" @click="retrySession">
        {{ retrying ? "Проверяем вход…" : "Повторить проверку" }}
      </UiButton>
      <p v-if="loading" role="status">Проверяем способ входа…</p>
      <template v-else-if="error">
        <UiAlert tone="error">{{ error }}</UiAlert>
        <UiButton class="retry-session" @click="loadOptions">Повторить</UiButton>
      </template>
      <HHCodeLogin v-else-if="method === 'otp'" @authenticated="retrySession" />
      <a v-else-if="method === 'oauth'" data-test="oauth-login" class="oauth-link" :href="oauthUrl">Продолжить с HH.ru ↗</a>
      <p class="login-note">Код нужен только для входа. Не сообщайте его другим людям.</p>
    </div>
  </section>
</template>
<style scoped>
.login-layout { align-items: center; display: grid; gap: 80px; grid-template-columns: 1fr 440px; margin: 48px auto; max-width: 1000px; }
.login-story h2 { font-size: 28px; font-weight: 650; letter-spacing: -0.04em; line-height: 1.45; margin: 28px 0 0; }
.login-story > p { color: var(--color-muted); max-width: 38ch; }
.story-logo { display: grid; place-items: center; width: 80px; height: 80px; background: var(--color-amber); color: var(--color-ink); border-radius: 20px; font-size: 28px; font-weight: 700; }
.story-caption { color: var(--color-muted); display: block; font-size: 13px; margin-top: 48px; }
.login-card { padding: 36px; min-width: 0; }
.login-mark { align-items: center; background: var(--color-ink); color: var(--color-amber); display: flex; font-size: 16px; font-weight: 700; height: 44px; width: 44px; justify-content: center; border-radius: 12px; margin-bottom: 24px; }
.login-card h1 { font-size: 26px; }
.login-copy { color: var(--color-muted); margin: 12px 0 28px; }
.retry-session { width: 100%; margin-top: 12px; }
.login-note { color: var(--color-muted); font-size: 12px; margin: 24px 0 0; }
.oauth-link { display: block; background: var(--color-ink); color: var(--color-paper, #fff); border-radius: 10px; padding: 14px; margin-top: 20px; text-align: center; text-decoration: none; }
@media (max-width: 900px) { .login-layout { gap: 32px; grid-template-columns: 1fr 1fr; } .login-card { padding: 28px; } .login-story h2 { font-size: 24px; } }
@media (max-width: 700px) { .login-layout { display: block; margin: 12px auto; max-width: 440px; } .login-story { display: none; } .login-card { padding: 24px; } .login-card h1 { font-size: 24px; } }
</style>

<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { request } from "../api/client";
import HHCodeLogin from "../components/HHCodeLogin.vue";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
const route = useRoute();
const router = useRouter();
const method = ref<"otp" | "oauth" | null>(null);
const optionsUnavailable = ref(false);
const loading = ref(false);
const retrying = ref(false);
let active = true;
let optionsVersion = 0;
onScopeDispose(() => {
  active = false;
  optionsVersion++;
});
const sessionCheckFailed = computed(
  () => route.query.reason === "session-check-failed",
);
const serviceUnavailable = computed(
  () => sessionCheckFailed.value || optionsUnavailable.value,
);
const oauthUrl =
  (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "") +
  "/auth/hh/login";
const authMessage = computed(() => {
  if (route.query.reason === "auth-required")
    return "Для просмотра этого раздела войдите через HH.ru.";
  if (route.query.reason === "session-expired")
    return "Войдите снова, чтобы продолжить.";
  return route.query.error
    ? "Не удалось завершить вход. Попробуйте подключиться ещё раз."
    : "";
});
async function loadOptions(): Promise<void> {
  if (loading.value || sessionCheckFailed.value) return;
  const version = ++optionsVersion;
  loading.value = true;
  try {
    const options = await request<{ method: string }>("/auth/hh/options");
    if (options.method !== "otp" && options.method !== "oauth")
      throw new Error("Invalid login mode");
    if (active && version === optionsVersion) {
      method.value = options.method;
      optionsUnavailable.value = false;
    }
  } catch {
    if (active && version === optionsVersion) optionsUnavailable.value = true;
  } finally {
    if (active && version === optionsVersion) loading.value = false;
  }
}
async function retrySession(): Promise<void> {
  if (retrying.value) return;
  retrying.value = true;
  const target = route.query.redirect;
  const internal =
    typeof target === "string" &&
    target.startsWith("/") &&
    !target.startsWith("//");
  try {
    await router.replace(
      internal && router.resolve(target).meta.requiresAuth
        ? target
        : "/account",
    );
  } finally {
    retrying.value = false;
  }
}
async function retryAvailability(): Promise<void> {
  if (retrying.value || loading.value) return;
  if (sessionCheckFailed.value) await retrySession();
  else await loadOptions();
}
watch(
  () => route.query.reason,
  () => {
    optionsVersion++;
    method.value = null;
    loading.value = false;
    optionsUnavailable.value = false;
    if (!sessionCheckFailed.value) void loadOptions();
  },
  { immediate: true },
);
</script>
<template>
  <section
    class="login-layout"
    :class="{ 'is-unavailable': serviceUnavailable }"
    aria-labelledby="login-heading"
  >
    <div v-if="!serviceUnavailable" class="login-story">
      <img class="story-logo" src="/logo.svg" width="64" height="64" alt="" />
      <h2>Меньше повторяющихся запросов.<br />Больше подходящих вакансий.</h2>
      <p>
        Ищите вакансии для разработчиков и сохраняйте параметры, к которым
        хочется вернуться.
      </p>
      <span class="story-caption">Job Aggregator</span>
    </div>
    <div class="login-card panel">
      <img
        class="login-mark"
        :class="{ 'unavailable-mark': serviceUnavailable }"
        src="/logo.svg"
        width="44"
        height="44"
        alt=""
      />
      <template v-if="serviceUnavailable">
        <h1 id="login-heading">Сервис временно недоступен</h1>
        <p class="unavailable-copy" role="status">
          Не удалось связаться с сервисом. Подождите немного и попробуйте ещё
          раз.
        </p>
        <UiButton
          class="retry-session"
          :disabled="retrying || loading"
          :busy="retrying || loading"
          @click="retryAvailability"
        >
          {{
            retrying || loading ? "Проверяем доступность…" : "Попробовать снова"
          }}
        </UiButton>
      </template>
      <template v-else>
        <h1 id="login-heading">Войти через HH.ru</h1>
        <p class="login-copy">
          Войдите, чтобы работать со своими сохранёнными поисками.
        </p>
        <UiAlert
          v-if="authMessage"
          :tone="route.query.reason === 'auth-required' ? 'info' : 'error'"
          >{{ authMessage }}</UiAlert
        >
        <p v-if="loading" role="status">Проверяем способ входа…</p>
        <HHCodeLogin
          v-else-if="method === 'otp'"
          @authenticated="retrySession"
        />
        <a
          v-else-if="method === 'oauth'"
          data-test="oauth-login"
          class="oauth-link"
          :href="oauthUrl"
          >Продолжить с HH.ru ↗</a
        >
        <p v-if="method === 'otp'" class="login-note">
          Код нужен только для входа. Не сообщайте его другим людям.
        </p>
      </template>
    </div>
  </section>
</template>
<style scoped>
.login-layout {
  align-items: center;
  display: grid;
  gap: 80px;
  grid-template-columns: 1fr 440px;
  margin: 48px auto;
  max-width: 1000px;
}
.login-story h2 {
  font-size: 28px;
  font-weight: 650;
  letter-spacing: -0.04em;
  line-height: 1.45;
  margin: 28px 0 0;
}
.login-story > p {
  color: var(--color-muted);
  max-width: 38ch;
}
.story-logo {
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  background: transparent;
  color: var(--color-link-hover);
  border-radius: 16px;
  font-size: 24px;
  font-weight: 700;
}
.story-caption {
  color: var(--color-muted);
  display: block;
  font-size: 13px;
  margin-top: 48px;
}
.login-card {
  padding: 36px;
  min-width: 0;
}
.login-mark {
  align-items: center;
  background: transparent;
  color: white;
  display: flex;
  font-size: 16px;
  font-weight: 700;
  height: 44px;
  width: 44px;
  justify-content: center;
  border-radius: 12px;
  margin-bottom: 24px;
}
.login-card h1 {
  font-size: 26px;
}
.login-copy {
  color: var(--color-muted);
  margin: 12px 0 28px;
}
.retry-session {
  width: 100%;
  margin-top: 12px;
}
.login-note {
  color: var(--color-muted);
  font-size: 13px;
  margin: 24px 0 0;
}
.oauth-link {
  display: block;
  background: var(--color-ink);
  color: var(--color-paper, #fff);
  border-radius: 10px;
  padding: 14px;
  margin-top: 20px;
  text-align: center;
  text-decoration: none;
}
.login-layout.is-unavailable {
  display: block;
  max-width: 480px;
  margin: 64px auto;
}
.is-unavailable .login-card {
  padding: 40px;
}
.unavailable-mark {
  position: relative;
  margin-bottom: 32px;
}
.unavailable-mark::after {
  background: var(--color-amber);
  border: 3px solid var(--color-surface);
  border-radius: 50%;
  bottom: -3px;
  content: "";
  height: 15px;
  position: absolute;
  right: -3px;
  width: 15px;
}
.unavailable-copy {
  color: var(--color-muted);
  line-height: 1.7;
  margin: 16px 0 28px;
}
.is-unavailable .retry-session {
  margin: 0;
  min-height: 48px;
}
@media (max-width: 900px) {
  .login-layout {
    gap: 32px;
    grid-template-columns: 1fr 1fr;
  }
  .login-card {
    padding: 28px;
  }
  .login-story h2 {
    font-size: 24px;
  }
}
@media (max-width: 700px) {
  .login-layout {
    display: block;
    margin: 12px auto;
    max-width: 440px;
  }
  .login-story {
    display: none;
  }
  .login-card {
    padding: 24px;
  }
  .login-card h1 {
    font-size: 24px;
  }
}
@media (max-width: 700px) {
  .login-layout.is-unavailable {
    margin: 24px auto;
  }
  .is-unavailable .login-card {
    padding: 28px 24px;
  }
}
</style>

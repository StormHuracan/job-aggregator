<template>
  <section class="login-layout" aria-labelledby="login-heading">
    <div class="login-story">
      <div class="story-symbol" aria-hidden="true">
        <svg viewBox="0 0 80 80" fill="none">
          <rect
            x="17"
            y="12"
            width="46"
            height="56"
            rx="9"
            stroke="currentColor"
            stroke-width="2"
          />
          <path
            d="M28 28h24M28 38h16M28 48h10"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
          <circle cx="59" cy="57" r="16" fill="var(--color-amber)" />
          <path
            d="m52 57 5 5 9-10"
            stroke="var(--color-ink)"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </div>
      <h2>Меньше повторяющихся запросов.<br />Больше подходящих вакансий.</h2>
      <p>
        Ищите вакансии для разработчиков и сохраняйте параметры, к которым
        хочется вернуться.
      </p>
      <span class="story-caption">Job Aggregator</span>
    </div>
    <div class="login-card panel">
      <span v-if="!mobileLogin" class="login-mark" aria-hidden="true">JA</span>
      <h1 id="login-heading">{{ mobileLogin ? "Завершите вход" : "Добро пожаловать" }}</h1>
      <p class="login-copy">
        {{ mobileLogin
          ? "HH.ru открыт в отдельной вкладке. Войдите там и вернитесь сюда."
          : "Войдите через HH.ru, чтобы работать со своими сохранёнными поисками." }}
      </p>
      <UiAlert
        v-if="authMessage && !mobileLogin"
        :tone="
          route.query.reason === 'session-check-failed' || route.query.error
            ? 'error'
            : 'info'
        "
        >{{ authMessage }}</UiAlert
      >
      <UiButton
        v-if="route.query.reason === 'session-check-failed' && !mobileLogin"
        class="retry-session"
        variant="secondary"
        :disabled="retrying"
        @click="retrySession"
        >{{ retrying ? "Проверяем вход…" : "Повторить проверку" }}</UiButton
      >
      <UiButton v-if="!mobileLogin" :disabled="pending" :busy="pending" @click="startLogin"
        >{{ pending ? "Начинаем вход…" : "Продолжить с HH.ru" }}
        <span aria-hidden="true">↗</span></UiButton
      >
      <UiAlert v-if="loginError && !mobileLogin" class="login-error" tone="error">
        {{ loginError }}
      </UiAlert>
      <form
        v-if="mobileLogin"
        class="mobile-completion"
        @submit.prevent="completeLogin"
      >
        <p class="field-hint">
          Если HH.ru предлагает открыть приложение, отмените переход.
          Скопируйте полный адрес возврата hhandroid://oauthresponse и вставьте ниже.
        </p>
        <a
          v-if="authorizationUrl"
          :href="authorizationUrl"
          target="_blank"
          rel="noopener noreferrer"
        >Открыть HH.ru ↗</a>
        <label class="field">Адрес возврата из HH.ru
          <input
            v-model="returnUrl"
            type="text"
            autocomplete="off"
            autocapitalize="off"
            :spellcheck="false"
            required
            :disabled="pending"
            placeholder="hhandroid://oauthresponse?…"
            :aria-invalid="loginError ? true : undefined"
            :aria-describedby="loginError ? 'return-url-error' : undefined"
          />
        </label>
        <UiAlert v-if="loginError" id="return-url-error" tone="error">
          {{ loginError }}
        </UiAlert>
        <p class="field-hint">
          Адрес содержит одноразовый код. Не делитесь им. Срок действия — 10 минут.
        </p>
        <UiButton
          type="submit"
          :disabled="pending || !returnUrl.trim()"
          :busy="pending"
        >Завершить вход</UiButton>
        <UiButton variant="ghost" :disabled="pending" @click="startLogin">
          Начать заново
        </UiButton>
      </form>
      <div v-if="!mobileLogin" class="login-explanation">
        <h2>Зачем подключать HH.ru?</h2>
        <p>
          Доступ нужен для получения вакансий от вашего имени. Пароль от HH.ru
          вы вводите только на сайте HH.ru.
        </p>
      </div>
      <p v-if="!mobileLogin" class="login-note">
        Авторизация проходит на стороне HH.ru. Для встроенного мобильного клиента вход завершается вставкой адреса возврата.
      </p>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
import { ApiError, request } from "../api/client";
const route = useRoute();
const router = useRouter();
const pending = ref(false);
const retrying = ref(false);
const loginError = ref("");
const mobileLogin = ref(false);
const returnUrl = ref("");
const authorizationUrl = ref("");
const authMessage = computed(() => {
  if (route.query.reason === "session-check-failed")
    return "Не удалось проверить вход. Защищённые данные не загружены. Попробуйте ещё раз.";
  if (route.query.reason === "auth-required")
    return "Для просмотра этого раздела войдите через HH.ru.";
  if (route.query.reason === "session-expired")
    return "Сессия истекла. Войдите снова, чтобы продолжить.";
  return route.query.error
    ? "Не удалось завершить вход. Попробуйте подключиться ещё раз."
    : "";
});
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
function resetPending(): void {
  pending.value = false;
}
window.addEventListener("pageshow", resetPending);
onScopeDispose(() => window.removeEventListener("pageshow", resetPending));
async function startLogin(): Promise<void> {
  if (pending.value) return;
  pending.value = true;
  loginError.value = "";
  returnUrl.value = "";
  // Вкладка создаётся в обработчике клика: иначе браузер блокирует popup после await.
  const popup = window.open("about:blank", "_blank");
  if (popup) popup.opener = null;
  try {
    const result = await request<{
      mode: "mobile" | "redirect";
      authorization_url: string;
    }>("/auth/hh/start", { method: "POST" });
    const url = new URL(result.authorization_url);
    if (
      url.protocol !== "https:" || url.hostname !== "hh.ru" ||
      url.pathname !== "/oauth/authorize"
    ) throw new Error("Invalid authorization URL");
    if (result.mode === "redirect") {
      popup?.close();
      window.location.assign(url.href);
    } else {
      mobileLogin.value = true;
      authorizationUrl.value = url.href;
      if (popup) popup.location.href = url.href;
    }
  } catch {
    popup?.close();
    loginError.value = "Не удалось начать вход. Проверьте подключение и попробуйте ещё раз.";
  } finally {
    pending.value = false;
  }
}
async function completeLogin(): Promise<void> {
  if (pending.value) return;
  loginError.value = "";
  try {
    const url = new URL(returnUrl.value.trim());
    if (
      url.protocol !== "hhandroid:" || url.host !== "oauthresponse" ||
      !url.searchParams.get("code") || !url.searchParams.get("state")
    ) throw new Error("Invalid return URL");
  } catch {
    loginError.value = "Вставьте полный адрес hhandroid://oauthresponse с параметрами code и state.";
    return;
  }
  pending.value = true;
  try {
    await request<void>("/auth/hh/complete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ return_url: returnUrl.value.trim() }),
    });
    returnUrl.value = "";
    authorizationUrl.value = "";
    await retrySession();
  } catch (error) {
    returnUrl.value = "";
    loginError.value = error instanceof ApiError && error.status === 400
      ? "Ссылка недействительна или уже использована. Начните вход заново."
      : "Не удалось завершить вход. Начните авторизацию заново.";
  } finally {
    pending.value = false;
  }
}
</script>
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
  margin-bottom: 20px;
}
.login-story > p {
  color: var(--color-muted);
  max-width: 38ch;
}
.story-symbol {
  height: 96px;
  margin-bottom: 28px;
  width: 96px;
}
.story-caption {
  color: var(--color-muted);
  display: block;
  font-size: 13px;
  margin-top: 48px;
}
.login-card {
  padding: 36px;
}
.login-mark {
  align-items: center;
  background: var(--color-ink);
  border-radius: 12px;
  color: var(--color-amber);
  display: flex;
  font-size: 16px;
  font-weight: 700;
  height: 44px;
  justify-content: center;
  margin-bottom: 24px;
  width: 44px;
}
.login-card h1 {
  font-size: 26px;
}
.login-copy {
  color: var(--color-muted);
  margin: 12px 0 28px;
}
.login-card button {
  width: 100%;
}
.retry-session {
  margin-bottom: 12px;
}
.login-error { margin-top: 16px; }
.mobile-completion {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}
.mobile-completion h2 { font-size: 16px; }
.mobile-completion p { margin: 0; }
.mobile-completion a { overflow-wrap: anywhere; }
.login-explanation {
  border-top: 1px solid var(--color-border);
  margin-top: 28px;
  padding-top: 24px;
}
.login-explanation h2 {
  font-size: 14px;
}
.login-explanation p,
.login-note {
  color: var(--color-muted);
  font-size: 13px;
}
.login-note {
  font-size: 12px;
  margin: 24px 0 0;
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
</style>

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
      <span class="login-mark" aria-hidden="true">JA</span>
      <h1 id="login-heading">Добро пожаловать</h1>
      <p class="login-copy">
        Войдите через HH.ru, чтобы работать со своими сохранёнными поисками.
      </p>
      <UiAlert v-if="authMessage" :tone="route.query.reason === 'session-check-failed' || route.query.error ? 'error' : 'info'">
        {{ authMessage }}
      </UiAlert>
      <UiButton v-if="route.query.reason === 'session-check-failed'" class="retry-session" variant="secondary" :disabled="retrying" @click="retrySession">
        {{ retrying ? "Проверяем вход…" : "Повторить проверку" }}
      </UiButton>
      <UiButton :disabled="pending" :busy="pending" @click="startLogin"
        >{{ pending ? "Переходим на HH.ru…" : "Продолжить с HH.ru" }}
        <span aria-hidden="true">↗</span></UiButton
      >
      <div class="login-explanation">
        <h2>Зачем подключать HH.ru?</h2>
        <p>
          Доступ нужен для получения вакансий от вашего имени. Пароль от HH.ru
          вы вводите только на сайте HH.ru.
        </p>
      </div>
      <p class="login-note">
        Авторизация проходит на стороне HH.ru.<br />После входа вы вернётесь в
        Job Aggregator.
      </p>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
const route = useRoute();
const router = useRouter();
const pending = ref(false);
const retrying = ref(false);
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
function startLogin(): void {
  if (pending.value) return;
  pending.value = true;
  const base = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
  window.location.assign(`${base}/auth/hh/login`);
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

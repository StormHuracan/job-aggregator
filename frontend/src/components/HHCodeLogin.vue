<script setup lang="ts">
import { computed, onScopeDispose, ref } from "vue";
import { ApiError, request } from "../api/client";
import UiAlert from "./ui/UiAlert.vue";
import UiButton from "./ui/UiButton.vue";

const emit = defineEmits<{ authenticated: [] }>();
type Prompt = { step: "code" | "captcha" | "authenticated"; captcha_image?: string; retry_after?: number };
const step = ref<"login" | "code" | "captcha">("login");
const username = ref("");
const code = ref("");
const captcha = ref("");
const image = ref("");
const busy = ref(false);
const error = ref("");
const deadline = ref(0);
const now = ref(Date.now());
const remaining = computed(() => Math.max(0, Math.ceil((deadline.value - now.value) / 1000)));
let active = true;
const timer = window.setInterval(() => { now.value = Date.now(); }, 250);
onScopeDispose(() => { active = false; window.clearInterval(timer); });

function accept(prompt: Prompt): void {
  code.value = "";
  captcha.value = "";
  if (prompt.step === "authenticated") {
    username.value = "";
    image.value = "";
    emit("authenticated");
  } else if (prompt.step === "code") {
    image.value = "";
    step.value = "code";
  } else if (prompt.step === "captcha" && /^data:image\/(png|jpeg|webp);base64,/.test(prompt.captcha_image ?? "")) {
    image.value = prompt.captcha_image!;
    step.value = "captcha";
  } else throw new Error("Invalid login response");
}

async function perform(path: string, payload?: object): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const prompt = await request<Prompt>(`/auth/hh/otp/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!active) return;
    if (path === "start") deadline.value = Date.now() + (prompt.retry_after ?? 60) * 1000;
    accept(prompt);
  } catch (cause) {
    if (!active) return;
    code.value = "";
    captcha.value = "";
    const status = cause instanceof ApiError ? cause.status : 0;
    if (status === 410) {
      step.value = "login";
      image.value = "";
      error.value = "Срок действия попытки истёк. Запросите новый код.";
    } else if (status === 400) error.value = "Код не подошёл. Проверьте его и попробуйте ещё раз.";
    else if (status === 422) error.value = "Проверьте email, номер телефона или введённый код.";
    else if (status === 429) {
      deadline.value = Date.now() + 60000;
      error.value = "Слишком много попыток. Подождите перед повторным запросом.";
    } else error.value = "Не удалось связаться с HH.ru. Попробуйте ещё раз. Если ошибка повторяется, начните вход заново.";
  } finally { busy.value = false; }
}
async function submit(): Promise<void> {
  if (step.value === "login") {
    if (remaining.value || !username.value.trim()) return;
    await perform("start", { username: username.value.trim() });
  } else if (step.value === "code") {
    if (!/^[0-9]{4,8}$/.test(code.value.trim())) {
      error.value = "Введите от 4 до 8 цифр из сообщения HH.ru.";
      return;
    }
    await perform("verify", { code: code.value.trim() });
  } else if (captcha.value.trim()) await perform("captcha", { text: captcha.value.trim() });
}
async function changeLogin(): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    await request<void>("/auth/hh/otp/cancel", { method: "POST" });
    if (!active) return;
    step.value = "login";
    code.value = captcha.value = image.value = error.value = "";
    deadline.value = 0;
  } catch {
    if (active) error.value = "Не удалось отменить вход. Проверьте соединение и повторите.";
  } finally { busy.value = false; }
}
</script>

<template>
  <form class="code-login" @submit.prevent="submit">
    <template v-if="step === 'login'">
      <label class="field">Email или телефон из HH.ru
        <input v-model="username" name="username" type="text" autocomplete="username"
          inputmode="email" maxlength="254" required :disabled="busy"
          placeholder="mail@example.ru или +7 999 123-45-67" />
      </label>
      <p class="field-hint">HH.ru отправит одноразовый код по SMS или email. Пароль не нужен.</p>
    </template>
    <template v-else-if="step === 'code'">
      <p class="field-hint">Введите код, который HH.ru отправил на {{ username }}.</p>
      <label class="field">Код из сообщения
        <input v-model="code" name="code" type="text" inputmode="numeric"
          autocomplete="one-time-code" pattern="[0-9]{4,8}" minlength="4" maxlength="8"
          required :disabled="busy" placeholder="Введите код" />
      </label>
    </template>
    <template v-else>
      <p class="field-hint">HH.ru просит подтвердить, что вы человек. Введите символы с картинки.</p>
      <img :src="image" alt="Проверка HH.ru" class="captcha-image" />
      <label class="field">Символы с картинки
        <input v-model="captcha" name="captcha" type="text" autocomplete="off"
          autocapitalize="off" :spellcheck="false" maxlength="100" required :disabled="busy" />
      </label>
    </template>
    <UiAlert v-if="error" tone="error">{{ error }}</UiAlert>
    <UiButton type="submit" :disabled="busy || (step === 'login' && remaining > 0)" :busy="busy">
      {{ busy ? "Подождите…" : step === 'login' ? (remaining ? `Повторить через ${remaining} с` : "Получить код") : step === 'code' ? "Войти" : "Подтвердить" }}
    </UiButton>
    <UiButton v-if="step === 'code'" data-test="resend" variant="secondary"
      :disabled="busy || remaining > 0" @click="perform('start', { username: username.trim() })">
      {{ remaining ? `Новый код через ${remaining} с` : "Отправить код ещё раз" }}
    </UiButton>
    <UiButton v-if="step !== 'login'" data-test="change-login" variant="ghost"
      :disabled="busy" @click="changeLogin">Изменить email или телефон</UiButton>
  </form>
</template>
<style scoped>
.code-login { display: grid; gap: 16px; margin-top: 24px; }
.code-login p { margin: 0; overflow-wrap: anywhere; }
.captcha-image { max-width: 100%; height: auto; border-radius: 8px; }
</style>

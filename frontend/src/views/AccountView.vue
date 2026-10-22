<template>
  <section aria-labelledby="account-heading">
    <div class="page-heading">
      <div>
        <h1 id="account-heading">Личный кабинет</h1>
        <p>Профиль, подключение источника и параметры поиска.</p>
      </div>
    </div>
    <UiAlert
      >Демонстрационный кабинет. Настройки сохраняются только в памяти этой
      вкладки и сбрасываются при перезагрузке.</UiAlert
    >
    <AsyncState :error="error" :loading="loading"
      ><template #error-actions
        ><UiButton variant="secondary" @click="load"
          >Повторить</UiButton
        ></template
      >
      <template v-if="user">
        <div class="profile-grid">
          <div class="panel profile">
            <div class="avatar" aria-hidden="true">
              {{ user.display_name.slice(0, 1) }}
            </div>
            <div>
              <p class="field-hint">Профиль пользователя</p>
              <h2>{{ user.display_name }}</h2>
              <span class="demo-badge">Демо-режим</span>
            </div>
          </div>
          <div class="panel connection">
            <div class="connection-heading">
              <h2>Подключение HH.ru</h2>
              <span
                class="connection-status"
                :class="{ connected: user.hh_connected }"
                >{{ user.hh_connected ? "Подключён" : "Не подключён" }}</span
              >
            </div>
            <p>Для получения вакансий нужен доступ к вашему аккаунту HH.ru.</p>
            <RouterLink class="connection-link" to="/login"
              >{{
                user.hh_connected
                  ? "Управлять подключением"
                  : "Перейти к подключению"
              }}
              <span aria-hidden="true">↗</span></RouterLink
            >
          </div>
        </div>
        <div class="account-workspace">
          <form class="settings-form panel" @submit.prevent="save">
            <div>
              <h2>Настройки поиска</h2>
              <p class="muted">
                Параметры по умолчанию для новых поисков в демо-кабинете.
              </p>
            </div>
            <label class="field"
              >Регион по умолчанию<input
                v-model.trim="defaultArea"
                maxlength="255"
                placeholder="Например, Москва"
                :disabled="pending !== null" /></label
            ><label class="field"
              >Количество страниц за один сбор<input
                v-model.number="pagesLimit"
                min="1"
                step="1"
                type="number"
                required
                :disabled="pending !== null"
              /><span class="field-hint"
                >Больше страниц — больше вакансий и дольше ожидание.</span
              ></label
            ><UiAlert
              v-if="feedback"
              :tone="actionError ? 'error' : 'success'"
              >{{ feedback }}</UiAlert
            >
            <div class="form-actions">
              <UiButton
                type="submit"
                :disabled="pending !== null"
                :busy="pending === 'save'"
                >{{
                  pending === "save" ? "Сохраняем…" : "Сохранить настройки"
                }}</UiButton
              >
            </div>
          </form>
          <aside class="account-aside">
            <div class="panel matches">
              <h2>
                Новых совпадений<span class="matches-count">{{
                  user.new_matches_count
                }}</span>
              </h2>
              <p class="muted">
                {{
                  user.new_matches_count
                    ? "Можно сбросить счётчик просмотренных вакансий."
                    : "Новых совпадений пока нет."
                }}
              </p>
              <UiButton
                variant="secondary"
                :disabled="pending !== null || user.new_matches_count === 0"
                @click="markSeen"
                >Отметить прочитанными</UiButton
              >
            </div>
            <div class="session">
              <h2>Сеанс работы</h2>
              <p class="field-hint">Завершите просмотр демо-кабинета.</p>
              <UiButton
                variant="ghost"
                :disabled="pending !== null"
                @click="signOut"
                >Выйти из кабинета</UiButton
              >
            </div>
          </aside>
        </div>
      </template>
    </AsyncState>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import type { CurrentUser } from "../api/user";
import AsyncState from "../components/AsyncState.vue";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
import { accountFixture } from "../mocks/user";
const router = useRouter();
const defaultArea = ref("");
const error = ref<string | null>(null);
const loading = ref(true);
const pagesLimit = ref(1);
const user = ref<CurrentUser | null>(null);
const pending = ref<string | null>(null);
const feedback = ref("");
const actionError = ref(false);
async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    user.value = await accountFixture.getCurrentUser();
    defaultArea.value = user.value.settings.default_area ?? "";
    pagesLimit.value = user.value.settings.default_pages_limit;
  } catch {
    error.value = "Не удалось загрузить данные личного кабинета";
  } finally {
    loading.value = false;
  }
}
async function action(
  name: string,
  operation: () => Promise<void>,
  success: string,
): Promise<void> {
  if (pending.value) return;
  pending.value = name;
  feedback.value = "";
  actionError.value = false;
  try {
    await operation();
    feedback.value = success;
  } catch {
    feedback.value = "Не удалось выполнить действие. Попробуйте ещё раз.";
    actionError.value = true;
  } finally {
    pending.value = null;
  }
}
async function save(): Promise<void> {
  if (
    !user.value ||
    !Number.isSafeInteger(pagesLimit.value) ||
    pagesLimit.value < 1
  )
    return;
  await action(
    "save",
    async () => {
      user.value!.settings = await accountFixture.updateSettings({
        default_area: defaultArea.value || null,
        default_pages_limit: pagesLimit.value,
      });
    },
    "Настройки сохранены в демо-кабинете до перезагрузки вкладки.",
  );
}
async function markSeen(): Promise<void> {
  if (!user.value) return;
  await action(
    "seen",
    async () => {
      await accountFixture.markMatchesSeen();
      user.value!.new_matches_count = 0;
    },
    "Счётчик совпадений сброшен.",
  );
}
async function signOut(): Promise<void> {
  await action(
    "logout",
    async () => {
      await accountFixture.logout();
      await router.push("/login");
    },
    "",
  );
}
onMounted(load);
</script>
<style scoped>
.profile-grid {
  display: grid;
  gap: 20px;
  grid-template-columns: 1fr 1fr;
  margin-bottom: 28px;
}
.profile {
  align-items: center;
  display: flex;
  gap: 16px;
  padding: 24px;
}
.profile h2 {
  margin: 4px 0 8px;
}
.avatar {
  align-items: center;
  background: #e9edfa;
  border-radius: 50%;
  color: var(--color-link);
  display: flex;
  flex-shrink: 0;
  font-size: 22px;
  font-weight: 600;
  height: 56px;
  justify-content: center;
  width: 56px;
}
.demo-badge {
  background: var(--color-surface-subtle);
  border-radius: 4px;
  color: var(--color-muted);
  font-size: 12px;
  padding: 3px 8px;
}
.connection {
  padding: 24px;
}
.connection-heading {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: space-between;
  margin-bottom: 12px;
}
.connection-heading h2 {
  margin: 0;
}
.connection-status {
  background: var(--color-warning-bg);
  border-radius: 6px;
  color: var(--color-warning);
  font-size: 12px;
  padding: 4px 8px;
}
.connected {
  background: var(--color-success-bg);
  color: var(--color-success);
}
.connection p {
  color: var(--color-muted);
  font-size: 14px;
  margin-bottom: 8px;
}
.connection-link {
  align-items: center;
  display: inline-flex;
  font-size: 14px;
  gap: 8px;
  min-height: 44px;
  text-decoration: none;
}
.account-workspace {
  align-items: start;
  display: grid;
  gap: 28px;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
}
.settings-form {
  display: grid;
  gap: 20px;
  padding: 24px;
}
.settings-form p.muted {
  font-size: 14px;
  margin: 0;
}
.form-actions {
  border-top: 1px solid var(--color-border);
  padding-top: 20px;
}
.matches {
  padding: 24px;
}
.matches h2 {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
}
.matches-count {
  font-size: 24px;
}
.matches p {
  font-size: 14px;
}
.session {
  padding: 24px;
}
.session h2 {
  font-size: 15px;
}
.session button {
  margin: 8px 0 0 -16px;
}
@media (max-width: 700px) {
  .profile-grid,
  .account-workspace {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .profile,
  .connection,
  .settings-form,
  .matches {
    padding: 20px;
  }
  .form-actions button {
    width: 100%;
  }
}
</style>

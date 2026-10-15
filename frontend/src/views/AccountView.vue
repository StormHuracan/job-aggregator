<template>
  <section aria-labelledby="account-heading">
    <h1 id="account-heading">Личный кабинет</h1>
    <AsyncState :error="error" :loading="loading">
      <template #default>
        <template v-if="user">
          <div class="account-summary"><p><span>Пользователь</span>{{ user.display_name }}</p><p><span>HH.ru</span>{{ user.hh_connected ? "подключён" : "не подключён" }}</p><p><span>Новых совпадений</span>{{ user.new_matches_count }}</p></div>

          <div class="account-workspace">
            <form class="settings-form" @submit.prevent="save">
              <div class="section-heading">
                <h2>Настройки поиска</h2>
                <p>Используются при следующем запуске сохранённых поисков.</p>
              </div>
              <label>
                Регион по умолчанию
                <input v-model.trim="defaultArea" maxlength="255" />
              </label>
              <label>
                Лимит страниц
                <input v-model.number="pagesLimit" min="1" type="number" />
              </label>
              <div class="form-actions">
                <button type="submit">Сохранить настройки</button>
              </div>
            </form>

            <aside class="account-actions" aria-label="Действия с кабинетом">
              <div>
                <h2>Совпадения</h2>
                <p>После просмотра можно очистить счётчик новых вакансий.</p>
              </div>
              <button class="secondary-action" type="button" @click="markSeen">Отметить прочитанными</button>
              <button class="sign-out" type="button" @click="signOut">Выйти из кабинета</button>
            </aside>
          </div>
        </template>
      </template>
      <template #error-actions><button type="button" @click="load">Повторить</button></template>
    </AsyncState>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import type { CurrentUser } from "../api/user";
import AsyncState from "../components/AsyncState.vue";
import { accountFixture } from "../mocks/user";

const router = useRouter();
const defaultArea = ref("");
const error = ref<string | null>(null);
const loading = ref(true);
const pagesLimit = ref(1);
const user = ref<CurrentUser | null>(null);

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

async function save(): Promise<void> {
  if (!user.value || pagesLimit.value < 1) return;
  user.value.settings = await accountFixture.updateSettings({
    default_area: defaultArea.value || null,
    default_pages_limit: pagesLimit.value,
  });
}

async function markSeen(): Promise<void> {
  if (!user.value) return;
  await accountFixture.markMatchesSeen();
  user.value.new_matches_count = 0;
}

async function signOut(): Promise<void> {
  await accountFixture.logout();
  await router.push("/login");
}

onMounted(load);
</script>
<style scoped>
.account-summary { display: grid; gap: 1px; grid-template-columns: repeat(3, 1fr); margin: 0 0 2rem; overflow: hidden; border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.account-summary p { background: #f4f7fa; font-size: 1.2rem; font-weight: 700; margin: 0; padding: 1rem; }
.account-summary span { color: var(--color-muted); display: block; font-size: 0.75rem; font-weight: 650; margin-bottom: 0.35rem; }
.account-workspace { align-items: start; display: grid; gap: var(--space-8); grid-template-columns: minmax(0, 1fr) minmax(15rem, 0.6fr); }
.settings-form { display: grid; gap: 1rem; max-width: 35rem; }
.section-heading h2, .account-actions h2 { font-size: 1.05rem; margin: 0; }
.section-heading p, .account-actions p { color: var(--color-muted); font-size: 0.9rem; margin: 0.25rem 0 0; }
label { display: grid; gap: 0.35rem; }
.form-actions { border-top: 1px solid var(--color-border); margin-top: 0.5rem; padding-top: 1rem; }
.account-actions { background: #f4f7fa; border: 1px solid var(--color-border); border-radius: var(--radius-sm); display: grid; gap: 0.75rem; padding: 1rem; }
.account-actions button { text-align: left; width: 100%; }
.secondary-action { background: var(--color-navy); }
.secondary-action:hover:not(:disabled) { background: #0d1e2e; }
.sign-out { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
.sign-out:hover:not(:disabled) { background: #e5ebf1; }
@media (max-width: 42rem) { .account-summary, .account-workspace { grid-template-columns: 1fr; } }
</style>

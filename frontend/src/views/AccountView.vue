<template>
  <section aria-labelledby="account-heading">
    <h1 id="account-heading">Личный кабинет</h1>
    <AsyncState :error="error" :loading="loading">
      <template #default>
        <template v-if="user">
          <div class="account-summary"><p><span>Пользователь</span>{{ user.display_name }}</p><p><span>HH.ru</span>{{ user.hh_connected ? "подключён" : "не подключён" }}</p><p><span>Новых совпадений</span>{{ user.new_matches_count }}</p></div>

          <form @submit.prevent="save">
            <label>
              Регион по умолчанию
              <input v-model.trim="defaultArea" maxlength="255" />
            </label>
            <label>
              Лимит страниц
              <input v-model.number="pagesLimit" min="1" type="number" />
            </label>
            <button type="submit">Сохранить настройки</button>
          </form>

          <button type="button" @click="markSeen">Отметить совпадения прочитанными</button>
          <button type="button" @click="signOut">Выйти</button>
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
form { display: grid; gap: 1rem; max-width: 35rem; } label { display: grid; gap: 0.35rem; } button + button { margin-left: 0.75rem; }
@media (max-width: 42rem) { .account-summary { grid-template-columns: 1fr; } }
</style>

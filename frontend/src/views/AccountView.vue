<template>
  <section aria-labelledby="account-heading">
    <h1 id="account-heading">Личный кабинет</h1>
    <AsyncState :error="error" :loading="loading">
      <template #default>
        <template v-if="user">
          <p>Пользователь: {{ user.display_name }}</p>
          <p>HH.ru: {{ user.hh_connected ? "подключён" : "не подключён" }}</p>
          <p>Новых совпадений: {{ user.new_matches_count }}</p>

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

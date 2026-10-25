<template>
  <section v-if="!sessionExpired" aria-labelledby="account-heading">
    <div class="page-heading">
      <div>
        <h1 id="account-heading">Личный кабинет</h1>
        <p>Ваш профиль, аккаунт HH.ru и настройки поиска.</p>
      </div>
    </div>
    <AsyncState :error="error" :loading="loading"
      ><template #loading><UiSkeleton variant="profile" /></template
      ><template #error-actions
        ><UiButton variant="secondary" @click="load"
          >Повторить</UiButton
        ></template
      >
      <template v-if="user">
        <div class="account-sheet">
          <section
            class="account-row profile-block"
            aria-labelledby="profile-heading"
          >
            <div class="row-heading">
              <h2 id="profile-heading">Профиль</h2>
              <p>Ваш аккаунт в Job Aggregator.</p>
            </div>
            <div class="profile">
              <div class="avatar" aria-hidden="true">
                {{ user.display_name.slice(0, 1) }}
              </div>
              <div>
                <p class="profile-name">{{ user.display_name }}</p>
                <span class="field-hint">Аккаунт № {{ user.id }}</span>
              </div>
            </div>
          </section>
          <section
            class="account-row integration-block"
            aria-labelledby="integration-heading"
          >
            <div class="row-heading">
              <h2 id="integration-heading">Интеграции</h2>
              <p>Доступ к внешнему источнику вакансий.</p>
            </div>
            <div class="connection">
              <div class="connection-heading">
                <h2>Подключение HH.ru</h2>
                <UiBadge :tone="user.hh_connected ? 'accent' : 'warning'">{{
                  user.hh_connected ? "Подключён" : "Не подключён"
                }}</UiBadge>
              </div>
              <p>
                Для получения вакансий нужен доступ к вашему аккаунту HH.ru.
              </p>
              <p v-if="user.hh_connected" class="expiry">{{ expiryLabel }}</p>
              <p v-if="accessExpired" class="field-hint">
                Приложение попробует обновить доступ при следующем запросе. Если
                это не удастся, подключите HH.ru заново.
              </p>
              <p class="field-hint">
                Статус сохранённого подключения, не онлайн-проверка HH.ru.
              </p>
              <RouterLink class="connection-link" to="/login"
                >{{
                  user.hh_connected
                    ? "Подключить заново"
                    : "Перейти к подключению"
                }}
                <UiIcon name="link" :size="16"
              /></RouterLink>
            </div>
          </section>
          <section
            class="account-row settings-block"
            aria-labelledby="settings-heading"
          >
            <div class="row-heading">
              <h2 id="settings-heading">Настройки поиска</h2>
              <p>
                Параметры для сбора сохранённых поисков. Ручная загрузка с HH.ru
                настраивается отдельно.
              </p>
            </div>
            <form class="settings-form" @submit.prevent="save">
              <label class="field"
                >Регион по умолчанию<input
                  v-model.trim="defaultArea"
                  @input="clearFieldError('default_area')"
                  maxlength="255"
                  placeholder="Например, Москва"
                  :disabled="pending !== null"
                  :aria-invalid="fieldErrors.default_area ? true : undefined"
                  :aria-describedby="
                    fieldErrors.default_area ? 'default-area-error' : undefined
                  "
                /><span
                  v-if="fieldErrors.default_area"
                  id="default-area-error"
                  class="error-text"
                  role="alert"
                  >{{ fieldErrors.default_area }}</span
                ><span class="field-hint"
                  >Регион пока хранится как предпочтение и не применяется
                  автоматически. В сохранённом поиске укажите регион
                  отдельно.</span
                ></label
              ><label class="field"
                >Сколько страниц посмотреть за один поиск<input
                  v-model.number="pagesLimit"
                  @input="clearFieldError('default_pages_limit')"
                  min="1"
                  step="1"
                  type="number"
                  required
                  :disabled="pending !== null"
                  :aria-invalid="
                    fieldErrors.default_pages_limit ? true : undefined
                  "
                  :aria-describedby="
                    fieldErrors.default_pages_limit
                      ? 'pages-limit-error'
                      : undefined
                  "
                /><span
                  v-if="fieldErrors.default_pages_limit"
                  id="pages-limit-error"
                  class="error-text"
                  role="alert"
                  >{{ fieldErrors.default_pages_limit }}</span
                ><span class="field-hint"
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
          </section>
          <section
            v-if="user.new_matches_count !== null"
            class="account-row matches-block"
            aria-labelledby="matches-heading"
          >
            <div class="row-heading">
              <h2 id="matches-heading">Совпадения</h2>
              <p>Новые вакансии по вашим сохранённым поискам.</p>
            </div>
            <div class="matches">
              <h2>
                Новых совпадений<span class="matches-count">{{
                  user.new_matches_count
                }}</span>
              </h2>
              <p class="muted">
                {{
                  user.new_matches_count
                    ? "Отметьте новые вакансии просмотренными, когда ознакомитесь с ними."
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
          </section>
          <section
            class="account-row session-block"
            aria-labelledby="session-heading"
          >
            <div class="row-heading">
              <h2 id="session-heading">Сессия и безопасность</h2>
              <p>Управление входом на этом устройстве.</p>
            </div>
            <div class="session">
              <h3>Текущий сеанс</h3>
              <p class="field-hint">
                Завершите текущий сеанс на этом устройстве.
              </p>
              <UiButton
                variant="secondary"
                :disabled="pending !== null"
                @click="signOut"
                ><UiIcon name="logout" />Выйти из кабинета</UiButton
              >
            </div>
          </section>
        </div>
        <TelegramConnection v-if="user && !sessionExpired" @session-expired="user = null; sessionExpired = true" />
      </template>
    </AsyncState>
  </section>
</template>
<script setup lang="ts">
import { computed } from "vue";
import TelegramConnection from "../components/TelegramConnection.vue";
import { RouterLink } from "vue-router";
import AsyncState from "../components/AsyncState.vue";
import UiAlert from "../components/ui/UiAlert.vue";
import UiButton from "../components/ui/UiButton.vue";
import UiBadge from "../components/ui/UiBadge.vue";
import UiIcon from "../components/ui/UiIcon.vue";
import UiSkeleton from "../components/ui/UiSkeleton.vue";
import { useAccount } from "../composables/useAccount";
const {
  user,
  sessionExpired,
  loading,
  error,
  defaultArea,
  pagesLimit,
  pending,
  feedback,
  actionError,
  fieldErrors,
  load,
  save,
  markSeen,
  signOut,
  clearFieldError,
} = useAccount();
const accessExpiry = computed(() => {
  const date = user.value?.access_expires_at
    ? new Date(user.value.access_expires_at)
    : null;
  return date && Number.isFinite(date.getTime()) ? date : null;
});
const accessExpired = computed(
  () =>
    accessExpiry.value !== null && accessExpiry.value.getTime() <= Date.now(),
);
const expiryLabel = computed(() =>
  !accessExpiry.value
    ? "Срок доступа не указан"
    : `${accessExpired.value ? "Срок доступа истёк" : "Доступ действует до"} ${accessExpiry.value.toLocaleString("ru-RU", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}`,
);
</script>
<style scoped>
.profile {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.avatar {
  align-items: center;
  background: var(--color-accent-soft);
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
.settings-form {
  display: grid;
  gap: 20px;
}
.form-actions {
  border-top: 1px solid var(--color-border);
  padding-top: 20px;
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
.session button {
  margin-top: 16px;
}
.account-row {
  display: grid;
  align-content: start;
  gap: 24px;
  padding: 28px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-panel);
}
.account-sheet {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
  grid-template-areas: "profile integration" "settings integration" "settings matches" "session session";
  gap: 20px;
}
.profile-block {
  grid-area: profile;
  gap: 16px;
}
.settings-block {
  grid-area: settings;
  align-self: start;
}
.integration-block {
  grid-area: integration;
}
.matches-block {
  grid-area: matches;
  gap: 16px;
}
.session-block {
  grid-area: session;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: transparent;
  box-shadow: none;
}
.session {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 24px;
}
.session h3 {
  display: none;
}
.session button {
  margin: 0;
}
.session > p {
  max-width: 30ch;
}
.matches-block .row-heading p {
  display: none;
}
.matches h2 {
  font-size: 15px;
  color: var(--color-muted);
  font-weight: 500;
}
.matches-count {
  color: var(--color-link);
  font-size: 28px;
  font-weight: 700;
}
.row-heading p {
  color: var(--color-muted);
  font-size: 14px;
  margin: 0;
  max-width: 62ch;
}
.profile,
.connection,
.settings-form,
.matches,
.session {
  padding: 0;
  min-width: 0;
}
.profile-name {
  color: var(--color-ink);
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
  overflow-wrap: anywhere;
}
.profile > div {
  min-width: 0;
}
.profile > div:last-child {
  flex: 1 1 160px;
}
.expiry {
  font-weight: 600;
  color: var(--color-ink) !important;
  margin-top: 16px;
}
@media (max-width: 900px) {
  .account-sheet {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .profile-block,
  .session-block {
    display: grid;
  }
  .account-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
    padding: 24px 20px;
  }
  .row-heading p {
    max-width: none;
  }
}
@media (max-width: 700px) {
  .form-actions button {
    width: 100%;
  }
}
</style>

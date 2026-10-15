<template>
  <section aria-labelledby="login-heading" class="login-page">
    <div class="login-mark" aria-hidden="true">JA</div>
    <p class="login-kicker">Ваш поиск — в одном месте</p>
    <h1 id="login-heading">Войдите, чтобы продолжить</h1>
    <p class="login-copy">Подключите HH.ru: сохранённые поиски, статусы вакансий и настройки станут персональными.</p>
    <button type="button" @click="startLogin">Продолжить с HH.ru</button>
    <p class="login-note">Мы не публикуем вакансии и не выполняем действия от вашего имени.</p>
  </section>
</template>

<script setup lang="ts">
function startLogin(): void {
  window.location.assign("/api/auth/hh/login");
}
</script>
<style scoped>
.login-page { margin-inline: auto; max-width: 34rem; text-align: center; }.login-mark { align-items: center; background: var(--color-amber); border-radius: 50%; color: var(--color-navy); display: inline-flex; font-size: 1.1rem; font-weight: 850; height: 3.5rem; justify-content: center; letter-spacing: -0.06em; margin-bottom: var(--space-6); width: 3.5rem; }.login-kicker { color: var(--color-link); font-size: 0.9rem; font-weight: 750; margin: 0 0 var(--space-2); }.login-page h1 { margin-bottom: var(--space-4); }.login-copy { color: var(--color-muted); margin: 0 auto var(--space-6); max-width: 42ch; }.login-note { color: var(--color-muted); font-size: 0.85rem; margin: var(--space-4) auto 0; max-width: 45ch; }
</style>

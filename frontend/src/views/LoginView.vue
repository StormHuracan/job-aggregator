<template>
  <section aria-labelledby="login-heading">
    <h1 id="login-heading">Вход в Job Aggregator</h1>
    <p>Войдите через HH.ru, чтобы открыть вакансии и персональные настройки.</p>
    <button type="button" @click="startLogin">Войти через HH.ru</button>
  </section>
</template>

<script setup lang="ts">
function startLogin(): void {
  window.location.assign("/api/auth/hh/login");
}
</script>

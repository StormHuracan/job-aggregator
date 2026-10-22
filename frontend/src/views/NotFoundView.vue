<template>
  <section class="not-found" aria-labelledby="not-found-heading">
    <span class="error-code">404</span>
    <h1 id="not-found-heading">Здесь пока ничего нет</h1>
    <p>
      Возможно, страница была перемещена или в адресе есть опечатка. Продолжите
      поиск с вакансий.
    </p>
    <RouterLink class="button" to="/vacancies">Перейти к вакансиям</RouterLink
    ><RouterLink class="back-link" to="/saved-searches"
      >Открыть сохранённые поиски</RouterLink
    >
  </section>
</template>
<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
<style scoped>
.not-found {
  margin: 64px auto;
  max-width: 440px;
  text-align: center;
}
.error-code {
  color: var(--color-muted);
  display: block;
  font-size: 64px;
  font-weight: 500;
  letter-spacing: -0.06em;
  margin-bottom: 20px;
}
.not-found p {
  color: var(--color-muted);
  margin: 16px 0 28px;
}
.back-link {
  align-items: center;
  display: flex;
  font-size: 14px;
  justify-content: center;
  margin-top: 16px;
  min-height: 44px;
}
</style>

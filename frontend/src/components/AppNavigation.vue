<template>
  <header class="header">
    <nav aria-label="Основная навигация" class="navigation">
      <RouterLink class="brand" to="/vacancies"><span class="brand-mark">JA</span><span>Job Aggregator</span></RouterLink>
      <ul class="links">
        <li><RouterLink to="/vacancies">Вакансии</RouterLink></li>
        <li><RouterLink to="/saved-searches">Сохранённые поиски</RouterLink></li>
        <li><RouterLink to="/account">Личный кабинет</RouterLink></li>
      </ul>
    </nav>
  </header>
</template>

<style scoped>
.header {
  background: var(--color-navy);
  color: #fff;
}

.navigation {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin: 0 auto;
  max-width: 76rem;
  padding: var(--space-4);
}

.brand {
  align-items: center;
  color: #fff;
  display: inline-flex;
  gap: 0.65rem;
  font-weight: 700;
  text-decoration: none;
}

.links {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: var(--space-3);
  list-style: none;
  margin: 0;
  padding: 0;
}

.links a {
  border-radius: var(--radius-sm);
  color: #c7d5e2;
  padding: 0.4rem 0.55rem;
  text-decoration: none;
}

.links a.router-link-active {
  background: rgb(255 255 255 / 14%);
  color: #fff;
  font-weight: 600;
}
.brand-mark { align-items: center; background: var(--color-amber); border-radius: 50%; color: var(--color-navy); display: inline-flex; font-size: 0.7rem; font-weight: 800; height: 1.9rem; justify-content: center; letter-spacing: -0.06em; width: 1.9rem; }
</style>

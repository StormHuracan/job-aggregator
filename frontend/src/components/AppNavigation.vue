<template>
  <header class="header">
    <nav aria-label="Основная навигация" class="navigation">
      <RouterLink class="brand" to="/vacancies">Job Aggregator</RouterLink>
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
  border-bottom: 1px solid var(--color-border);
}

.navigation {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin: 0 auto;
  max-width: 72rem;
  padding: var(--space-4);
}

.brand {
  color: var(--color-text);
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
  color: var(--color-muted);
}

.links a.router-link-active {
  color: var(--color-text);
  font-weight: 600;
}
</style>

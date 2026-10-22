<template>
  <header class="header">
    <nav aria-label="Основная навигация" class="navigation">
      <RouterLink class="brand" to="/vacancies"
        ><span class="brand-mark">JA<span></span></span
        ><span>Job Aggregator</span></RouterLink
      >
      <ul class="links">
        <li>
          <RouterLink to="/vacancies"
            ><svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="10.5" cy="10.5" r="6.5" />
              <path d="m16 16 4 4" /></svg
            >Вакансии</RouterLink
          >
        </li>
        <li>
          <RouterLink to="/saved-searches"
            ><svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 4h12v17l-6-4-6 4Z" /></svg
            >Сохранённые поиски</RouterLink
          >
        </li>
        <li>
          <RouterLink to="/account"
            ><svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21a8 8 0 0 1 16 0" /></svg
            >Личный кабинет</RouterLink
          >
        </li>
      </ul>
    </nav>
  </header>
</template>
<style scoped>
.header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.navigation {
  align-items: center;
  display: flex;
  gap: 48px;
  margin: 0 auto;
  max-width: 1168px;
  min-height: 80px;
  padding: 0 32px;
}
.brand {
  align-items: center;
  color: var(--color-ink);
  display: inline-flex;
  flex-shrink: 0;
  gap: 10px;
  font-size: 16px;
  font-weight: 750;
  letter-spacing: -0.03em;
  min-height: 44px;
  text-decoration: none;
}
.brand-mark {
  align-items: center;
  background: var(--color-ink);
  border-radius: 10px;
  color: white;
  display: flex;
  height: 34px;
  justify-content: center;
  position: relative;
  width: 34px;
  font-size: 13px;
}
.brand-mark span {
  background: var(--color-amber);
  border: 2px solid white;
  border-radius: 50%;
  bottom: -2px;
  height: 11px;
  position: absolute;
  right: -2px;
  width: 11px;
}
.links {
  align-self: stretch;
  display: flex;
  gap: 24px;
  list-style: none;
  margin: 0;
  padding: 0;
}
.links li {
  display: flex;
}
.links a {
  align-items: center;
  border-bottom: 2px solid transparent;
  color: var(--color-muted);
  display: flex;
  font-size: 14px;
  font-weight: 600;
  gap: 8px;
  min-height: 44px;
  padding: 12px 0;
  text-decoration: none;
}
.links a:hover {
  color: var(--color-ink);
}
.links a.router-link-active {
  border-bottom-color: var(--color-link);
  color: var(--color-link);
}
svg {
  fill: none;
  height: 18px;
  stroke: currentColor;
  stroke-width: 1.6;
  width: 18px;
  flex-shrink: 0;
}
@media (max-width: 900px) {
  .navigation {
    gap: 24px;
  }
  .links {
    gap: 20px;
  }
  .links svg {
    display: none;
  }
}
@media (max-width: 700px) {
  .navigation {
    align-items: start;
    flex-direction: column;
    gap: 0;
    min-height: 0;
    padding: 8px 16px 0;
  }
  .brand {
    font-size: 15px;
  }
  .brand-mark {
    height: 28px;
    width: 28px;
  }
  .links {
    display: grid;
    gap: 12px;
    grid-template-columns: 0.8fr 1.4fr 1.1fr;
    width: 100%;
  }
  .links a {
    font-size: 12px;
    justify-content: center;
    line-height: 1.4;
    padding: 8px 0;
    text-align: center;
  }
  .links li {
    min-width: 0;
  }
  .links a {
    width: 100%;
  }
}
</style>

<template>
  <article class="vacancy-card">
    <div class="vacancy-main">
      <h3>{{ vacancy.title }}</h3>
      <p class="company">{{ vacancy.company_name ?? "Компания не указана" }}</p>
      <p class="meta">
        <span>{{ vacancy.area_name ?? "Город не указан" }}</span
        ><span v-if="published">Опубликовано {{ published }}</span>
      </p>
      <p v-if="snippet" class="description">
        {{ snippet }}
      </p>
    </div>
    <div class="vacancy-aside">
      <p class="salary">{{ salary }}</p>
      <a
        v-if="sourceUrl"
        :href="sourceUrl"
        rel="noopener noreferrer"
        target="_blank"
        >{{ vacancy.source === "hh" ? "Открыть на HH.ru" : "Открыть оригинал" }}
        <span aria-hidden="true">↗</span
        ><span class="sr-only"> (в новой вкладке)</span></a
      >
      <span v-else class="field-hint">Ссылка недоступна</span>
    </div>
  </article>
</template>
<script setup lang="ts">
import { computed } from "vue";
import type { VacancyResponse } from "../api/vacancies";
import {
  safeExternalVacancyUrl,
  vacancySnippetToText,
} from "../utils/vacancy-presentation";
const props = defineProps<{ vacancy: VacancyResponse }>();
const snippet = computed(() => vacancySnippetToText(props.vacancy.description));
const sourceUrl = computed(() =>
  safeExternalVacancyUrl(props.vacancy.source_url),
);
const published = computed(() => {
  const date = props.vacancy.published_at
    ? new Date(props.vacancy.published_at)
    : null;
  return date && !Number.isNaN(date.getTime())
    ? date.toLocaleDateString("ru-RU", { day: "numeric", month: "long" })
    : null;
});
const salary = computed(() => {
  const {
    salary_from: from,
    salary_to: to,
    salary_currency: currency,
  } = props.vacancy;
  const format = (value: number) => value.toLocaleString("ru-RU");
  const suffix =
    currency === "RUR" || currency === "RUB" ? "₽" : (currency ?? "");
  if (from === null && to === null) return "Зарплата не указана";
  const range =
    from !== null && to !== null
      ? from === to
        ? format(from)
        : `${format(from)}–${format(to)}`
      : from !== null
        ? `от ${format(from)}`
        : `до ${format(to!)}`;
  return `${range} ${suffix}`.trim();
});
</script>
<style scoped>
.vacancy-card {
  display: grid;
  gap: 16px 32px;
  grid-template-columns: minmax(0, 1fr) minmax(160px, 240px);
  padding: 28px;
}
.vacancy-card + .vacancy-card {
  border-top: 1px solid var(--color-border);
}
.company {
  overflow-wrap: anywhere;
  color: var(--color-muted);
  font-size: 15px;
  margin: 0 0 4px;
}
h3 {
  font-size: 20px;
  margin-bottom: 8px;
}
.meta {
  color: var(--color-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 14px;
  gap: 4px 16px;
  margin: 0;
}
.description {
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  display: -webkit-box;
  font-size: 14px;
  margin: 12px 0 0;
  max-width: 65ch;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.vacancy-aside {
  align-items: end;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 240px;
}
.salary {
  color: var(--color-ink);
  font-size: 18px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  margin: 0;
}
.vacancy-aside a {
  align-items: center;
  display: inline-flex;
  font-size: 14px;
  gap: 8px;
  min-height: 44px;
  text-decoration: none;
}
.vacancy-aside a:hover {
  text-decoration: underline;
}
.sr-only {
  clip-path: inset(50%);
  height: 1px;
  overflow: hidden;
  position: absolute;
  width: 1px;
}
@media (max-width: 700px) {
  .vacancy-card {
    gap: 12px;
    grid-template-columns: minmax(0, 1fr);
    padding: 20px 16px;
  }
  .vacancy-aside {
    align-items: start;
    gap: 0;
    grid-column: 1;
    max-width: none;
  }
  .vacancy-main,
  .vacancy-aside {
    display: contents;
  }
  .vacancy-card {
    gap: 8px;
  }
  h3 {
    order: 0;
    margin: 0;
  }
  .salary {
    order: 1;
  }
  .company {
    order: 2;
    margin: 4px 0 0;
  }
  .meta {
    order: 3;
  }
  .description {
    order: 4;
    margin: 4px 0 0;
  }
  .vacancy-aside a,
  .vacancy-aside > span {
    order: 5;
    justify-self: start;
  }
  .description {
    -webkit-line-clamp: 2;
  }
}
</style>

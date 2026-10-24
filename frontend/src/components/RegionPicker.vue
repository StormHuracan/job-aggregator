<script setup lang="ts">
import { computed, nextTick, onScopeDispose, ref, useId, watch } from "vue";
import { ApiError } from "../api/client";
import { suggestHHAreas, type HHAreaSuggestion } from "../api/hh-areas";

const props = defineProps<{ modelValue: HHAreaSuggestion | null; disabled?: boolean }>();
const emit = defineEmits<{
  "update:modelValue": [value: HHAreaSuggestion | null];
  unauthorized: [];
}>();
const id = useId();
const input = ref<HTMLInputElement>();
const root = ref<HTMLDivElement>();
const label = (area: HHAreaSuggestion) =>
  area.parent_name ? `${area.name} · ${area.parent_name}` : area.name;
const query = ref(props.modelValue ? label(props.modelValue) : "");
const items = ref<HHAreaSuggestion[]>([]);
const opened = ref(false);
const focused = ref(false);
const loading = ref(false);
const error = ref("");
const invalid = ref(false);
const activeIndex = ref(-1);
const searched = ref(false);
const listId = `${id}-regions`;
const hasQuery = computed(() => query.value.trim().length >= 2);
let revision = 0;
let timer: ReturnType<typeof setTimeout> | undefined;
let controller: AbortController | undefined;
let alive = true;

function cancel(): void {
  revision++;
  clearTimeout(timer);
  controller?.abort();
  loading.value = false;
}
function validate(): void {
  input.value?.setCustomValidity(
    query.value.trim() && !props.modelValue
      ? "Выберите регион из списка или очистите поле."
      : "",
  );
}
watch(() => props.modelValue, (value, previous) => {
  if (value) query.value = label(value);
  else if (previous && query.value === label(previous)) query.value = "";
  validate();
});
onScopeDispose(() => { alive = false; cancel(); });

async function load(version: number): Promise<void> {
  if (!hasQuery.value || props.modelValue || props.disabled) return;
  loading.value = true;
  error.value = "";
  controller = new AbortController();
  try {
    const response = await suggestHHAreas(query.value.trim(), controller.signal);
    if (!alive || version !== revision) return;
    items.value = response;
    searched.value = true;
    activeIndex.value = -1;
  } catch (cause) {
    if (!alive || version !== revision) return;
    if (cause instanceof ApiError && cause.status === 401) emit("unauthorized");
    else error.value = cause instanceof ApiError && cause.status === 409
      ? "Подключите HH.ru повторно, чтобы выбрать регион."
      : "Не удалось загрузить регионы. Попробуйте ещё раз.";
  } finally {
    if (alive && version === revision) loading.value = false;
  }
}
function changed(event: Event): void {
  cancel();
  query.value = (event.target as HTMLInputElement).value;
  emit("update:modelValue", null);
  items.value = [];
  activeIndex.value = -1;
  searched.value = false;
  error.value = "";
  invalid.value = false;
  opened.value = true;
  // props обновится на следующем tick; непустой ввод ещё не является выбором.
  input.value?.setCustomValidity(query.value.trim() ? "Выберите регион из списка или очистите поле." : "");
  if (hasQuery.value) {
    const version = revision;
    timer = setTimeout(() => { void load(version); }, 250);
  }
}
function choose(area: HHAreaSuggestion): void {
  cancel();
  query.value = label(area);
  emit("update:modelValue", area);
  opened.value = false;
  invalid.value = false;
  input.value?.setCustomValidity("");
}
async function clear(): Promise<void> {
  cancel();
  query.value = "";
  items.value = [];
  activeIndex.value = -1;
  searched.value = false;
  error.value = "";
  invalid.value = false;
  emit("update:modelValue", null);
  input.value?.setCustomValidity("");
  await nextTick();
  input.value?.focus();
}
function focus(): void {
  focused.value = true;
  opened.value = true;
  if (hasQuery.value && !props.modelValue && !items.value.length && !loading.value)
    void load(revision);
}
function focusout(event: FocusEvent): void {
  if (event.relatedTarget instanceof Node && root.value?.contains(event.relatedTarget)) return;
  focused.value = false;
  opened.value = false;
}
function retry(): void {
  void load(revision);
  input.value?.focus();
}
function keydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    opened.value = false;
    cancel();
  } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    opened.value = true;
    if (items.value.length) {
      const direction = event.key === "ArrowDown" ? 1 : -1;
      activeIndex.value = activeIndex.value < 0
        ? (direction > 0 ? 0 : items.value.length - 1)
        : (activeIndex.value + direction + items.value.length) % items.value.length;
      void nextTick(() => document.getElementById(`${id}-option-${activeIndex.value}`)?.scrollIntoView?.({ block: "nearest" }));
    }
  } else if (event.key === "Enter" && opened.value && items.value[activeIndex.value]) {
    event.preventDefault();
    choose(items.value[activeIndex.value]!);
  }
}
</script>

<template>
  <div ref="root" class="field region-picker" @focusout="focusout">
    <label :for="id">Регион</label>
    <div class="region-control">
      <input
        :id="id" ref="input" :value="query" role="combobox"
        aria-autocomplete="list" :aria-expanded="opened && focused"
        :aria-controls="listId"
        :aria-activedescendant="opened && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined"
        :aria-invalid="invalid || undefined" :aria-describedby="`${id}-hint`"
        autocomplete="off" maxlength="255" placeholder="Город или область"
        :disabled="disabled" @input="changed" @focus="focus"
        @keydown="keydown" @invalid="invalid = true"
      />
      <button v-if="query" type="button" class="region-clear" aria-label="Очистить регион"
        :disabled="disabled" @click="clear">×</button>
      <div v-if="opened && focused" class="region-popup">
        <p v-if="loading" role="status">Ищем регионы…</p>
        <template v-else-if="error">
          <p role="alert">{{ error }}</p>
          <button type="button" class="button-secondary" @mousedown.prevent @click="retry">Повторить</button>
        </template>
        <p v-else-if="!hasQuery" role="status">Введите хотя бы две буквы названия.</p>
        <p v-else-if="searched && !items.length" role="status">Ничего не найдено. Попробуйте другое название.</p>
        <ul :id="listId" role="listbox" aria-label="Найденные регионы">
          <li v-for="(area, index) in items" :id="`${id}-option-${index}`" :key="area.id"
            role="option" :aria-selected="activeIndex === index"
            :class="{ active: activeIndex === index }" @mousedown.prevent @click="choose(area)">
            {{ label(area) }}
          </li>
        </ul>
      </div>
    </div>
    <span :id="`${id}-hint`" class="field-hint" :class="{ 'error-text': invalid }">
      {{ invalid ? "Выберите регион из списка или очистите поле." : "Необязательно. Без выбора — любой регион." }}
    </span>
  </div>
</template>

<style scoped>
.region-picker, .region-control { min-width: 0; position: relative; }
.region-control input { padding-right: 48px; }
.region-clear { background: transparent; color: var(--color-muted); height: 44px; min-width: 44px; padding: 0; position: absolute; right: 2px; top: 2px; font-size: 24px; }
.region-clear:hover:not(:disabled) { background: var(--color-surface-subtle); color: var(--color-text); }
.region-popup { background: var(--color-surface); border: 1px solid var(--color-control-border); border-radius: var(--radius-sm); box-shadow: 0 8px 24px rgb(0 0 0 / 12%); left: 0; max-height: 260px; overflow-y: auto; position: absolute; right: 0; top: calc(100% + 4px); z-index: 20; }
.region-popup p { font-size: 14px; font-weight: 400; margin: 0; padding: 12px; }
.region-popup > button { margin: 0 12px 12px; }
.region-popup ul { list-style: none; margin: 0; padding: 0; }
.region-popup li { cursor: pointer; font-size: 14px; font-weight: 400; min-height: 44px; overflow-wrap: anywhere; padding: 10px 12px; }
.region-popup li:hover, .region-popup li.active { background: var(--color-surface-subtle); color: var(--color-link); }
</style>

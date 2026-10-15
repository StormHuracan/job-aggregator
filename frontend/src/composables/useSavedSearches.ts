import { ref } from "vue";

import type { SavedSearch, SavedSearchCreate } from "../api/saved-searches";

const searches = ref<SavedSearch[]>([]);

export function useSavedSearches() {
  function createSearch(input: SavedSearchCreate): void {
    const now = new Date().toISOString();
    searches.value.push({
      area: input.area ?? null,
      created_at: now,
      id: Date.now(),
      is_enabled: true,
      name: input.name,
      text: input.text,
      updated_at: now,
    });
  }

  function setEnabled(id: number, isEnabled: boolean): void {
    const search = searches.value.find((item) => item.id === id);
    if (search) {
      search.is_enabled = isEnabled;
      search.updated_at = new Date().toISOString();
    }
  }

  return { createSearch, searches, setEnabled };
}

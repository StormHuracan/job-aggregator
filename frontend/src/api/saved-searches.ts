import { request } from "./client";

export type SavedSearch = {
  id: number;
  name: string;
  text: string;
  area: string | null;
  min_salary: number | null;
  max_salary: number | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type SavedSearchCreate = {
  name: string;
  text: string;
  area?: string | null;
  min_salary?: number | null;
  max_salary?: number | null;
};

export type SavedSearchUpdate = { is_enabled: boolean };

export function listSavedSearches(): Promise<SavedSearch[]> {
  return request<SavedSearch[]>("/saved-searches");
}

export function createSavedSearch(input: SavedSearchCreate): Promise<SavedSearch> {
  return request<SavedSearch>("/saved-searches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function setSavedSearchEnabled(id: number, isEnabled: boolean): Promise<SavedSearch> {
  const update: SavedSearchUpdate = { is_enabled: isEnabled };
  return request<SavedSearch>(`/saved-searches/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

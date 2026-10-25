import { request } from "./client";

export type HHAreaSuggestion = {
  id: string;
  name: string;
  parent_name: string | null;
};

export function suggestHHAreas(text: string, signal?: AbortSignal): Promise<HHAreaSuggestion[]> {
  return request(`/hh/areas?${new URLSearchParams({ text })}`, { signal });
}

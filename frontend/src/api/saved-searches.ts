export type SavedSearch = { id: number; name: string; text: string; area: string | null; is_enabled: boolean; created_at: string; updated_at: string };
export type SavedSearchCreate = Pick<SavedSearch, "name" | "text" | "area"> & { min_salary?: number | null; max_salary?: number | null };

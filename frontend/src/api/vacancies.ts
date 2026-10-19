import { request } from "./client";

export type VacancyResponse = {
  id: number;
  source: string;
  external_id: string;
  title: string;
  company_name: string | null;
  area_name: string | null;
  salary_from: number | null;
  salary_to: number | null;
  salary_currency: string | null;
  description: string | null;
  source_url: string;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type VacancyListQuery = {
  text?: string | null;
  company?: string | null;
  area?: string | null;
  salary_from?: number | null;
  salary_to?: number | null;
  limit: number;
  offset: number;
};

export type VacancyListResponse = {
  items: VacancyResponse[];
  total: number;
  limit: number;
  offset: number;
};

export function listVacancies(query: VacancyListQuery): Promise<VacancyListResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined) params.set(key, String(value));
  }
  return request<VacancyListResponse>(`/vacancies?${params}`);
}

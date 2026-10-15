export type VacancyResponse = {
  id: number;
  title: string;
  company_name: string | null;
  area_name: string | null;
  salary_from: number | null;
  salary_to: number | null;
  salary_currency: string | null;
  description: string | null;
  source_url: string;
};

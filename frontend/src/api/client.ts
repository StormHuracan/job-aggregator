import { ApiError, validationFieldErrors } from "./errors";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

function errorMessageForStatus(status: number): string {
  if (status === 401) {
    return "Войдите снова, чтобы продолжить.";
  }
  if (status === 503) {
    return "Сервис временно недоступен";
  }

  return "Не удалось выполнить запрос";
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
  } catch {
    throw new ApiError(0, "Не удалось связаться с сервисом. Проверьте интернет и попробуйте ещё раз.");
  }

  if (!response.ok) {
    if (response.status === 422) {
      const body: unknown = await response.json().catch(() => null);
      throw new ApiError(422, "Проверьте поля формы и диапазон зарплаты", validationFieldErrors(body));
    }
    throw new ApiError(response.status, errorMessageForStatus(response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "Не удалось загрузить данные. Попробуйте ещё раз.");
  }
}

export { ApiError } from "./errors";

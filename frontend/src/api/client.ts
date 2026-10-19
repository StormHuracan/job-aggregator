import { ApiError } from "./errors";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

function errorMessageForStatus(status: number): string {
  if (status === 401) {
    return "Сессия истекла. Войдите снова";
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
    throw new ApiError(0, "Не удалось подключиться к API");
  }

  if (!response.ok) {
    throw new ApiError(response.status, errorMessageForStatus(response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "API вернул некорректный ответ");
  }
}

export { ApiError } from "./errors";

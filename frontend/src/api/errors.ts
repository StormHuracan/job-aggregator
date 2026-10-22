export class ApiError extends Error {
  public constructor(
    public readonly status: number,
    message: string,
    public readonly fieldErrors: Readonly<Record<string, string>> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Возвращает только безопасные сообщения для известных полей; input/ctx/msg не копируются. */
export function validationFieldErrors(body: unknown): Record<string, string> {
  const fields: Record<string, string> = {};
  if (!body || typeof body !== "object" || !("detail" in body) || !Array.isArray(body.detail)) return fields;
  for (const item of body.detail) {
    if (!item || typeof item !== "object" || !Array.isArray(item.loc)) continue;
    const [source, field] = item.loc;
    if (source !== "body" || item.loc.length !== 2) continue;
    if (!["name", "text", "area", "min_salary", "max_salary"].includes(field)) continue;
    fields[field] = field === "min_salary" || field === "max_salary"
      ? "Введите целое неотрицательное число"
      : item.type === "string_too_long" ? "Не более 255 символов" : "Проверьте значение поля";
  }
  return fields;
}

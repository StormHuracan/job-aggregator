import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, request } from "./client";

describe("request", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON for a successful response", async () => {
    const fetchStub = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ connected: true }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchStub);

    await expect(request<{ connected: boolean }>("/me")).resolves.toEqual({
      connected: true,
    });
    const [url, init] = fetchStub.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/me");
    expect(new Headers(init.headers).get("Accept")).toBe("application/json");
    expect(init.credentials).toBe("include");
  });

  it("converts a network failure into an ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(request("/health")).rejects.toEqual(
      new ApiError(0, "Не удалось подключиться к API"),
    );
  });

  it("uses a safe message for a non-JSON error response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Service unavailable", {
          status: 503,
          headers: { "Content-Type": "text/plain" },
        }),
      ),
    );

    await expect(request("/vacancies")).rejects.toEqual(
      new ApiError(503, "Сервис временно недоступен"),
    );
  });
});

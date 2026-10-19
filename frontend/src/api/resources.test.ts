import { afterEach, describe, expect, it, vi } from "vitest";

import { runCollection } from "./collection";
import { createSavedSearch, listSavedSearches, setSavedSearchEnabled } from "./saved-searches";
import { listVacancies } from "./vacancies";
import { logout, markMatchesSeen } from "./user";

describe("public API contracts", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("encodes vacancy filters and preserves zero-valued pagination and salary", async () => {
    const response = { items: [], total: 0, limit: 20, offset: 0 };
    const fetchStub = vi.fn().mockResolvedValue(new Response(JSON.stringify(response)));
    vi.stubGlobal("fetch", fetchStub);

    await expect(listVacancies({ text: "C++ & Python", company: "A&B", area: null,
      salary_from: 0, limit: 20, offset: 0 })).resolves.toEqual(response);

    const [path, init] = fetchStub.mock.calls[0] as [string, RequestInit];
    const url = new URL(path, "http://localhost");
    expect(url.pathname).toBe("/api/vacancies");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      text: "C++ & Python", company: "A&B", salary_from: "0", limit: "20", offset: "0",
    });
    expect(init.credentials).toBe("include");
  });

  it("loads saved searches as a list", async () => {
    const fetchStub = vi.fn().mockResolvedValue(new Response("[]"));
    vi.stubGlobal("fetch", fetchStub);
    await expect(listSavedSearches()).resolves.toEqual([]);
    expect(fetchStub.mock.calls[0]?.[0]).toBe("/api/saved-searches");
  });

  it("creates a saved search with salary bounds", async () => {
    const input = { name: "Python", text: "python", area: null, min_salary: 0, max_salary: 250000 };
    const result = { ...input, id: 7, is_enabled: true, created_at: "2026-10-19T12:00:00Z", updated_at: "2026-10-19T12:00:00Z" };
    const fetchStub = vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 201 }));
    vi.stubGlobal("fetch", fetchStub);
    await expect(createSavedSearch(input)).resolves.toEqual(result);
    const [url, init] = fetchStub.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/saved-searches");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(input);
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(init.credentials).toBe("include");
  });

  it("patches only the enabled flag of a saved search", async () => {
    const fetchStub = vi.fn().mockResolvedValue(new Response('{"id":7,"is_enabled":false}'));
    vi.stubGlobal("fetch", fetchStub);
    await setSavedSearchEnabled(7, false);
    const [url, init] = fetchStub.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/saved-searches/7");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ is_enabled: false });
  });

  it("runs collection using the inline request contract", async () => {
    const result = { created: 2, updated: 1, skipped: 3, failed: 0 };
    const fetchStub = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)));
    vi.stubGlobal("fetch", fetchStub);
    const input = { text: "Python developer", area: null, pages_limit: 2 };
    await expect(runCollection(input)).resolves.toEqual(result);
    const [url, init] = fetchStub.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/collection/hh/run");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(input);
    expect(init.credentials).toBe("include");
  });

  it.each([
    ["/auth/logout", logout],
    ["/me/matches/mark-seen", markMatchesSeen],
  ] as const)("accepts HTTP 204 for %s", async (path, operation) => {
    const fetchStub = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchStub);
    await expect(operation()).resolves.toBeUndefined();
    expect(fetchStub).toHaveBeenCalledWith(`/api${path}`, expect.objectContaining({ method: "POST", credentials: "include" }));
  });
});

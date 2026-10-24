import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import type { CurrentUser } from "../api/user";
import { createAppRouter } from "./index";

const user: CurrentUser = {
  access_expires_at: null,
  display_name: "Даниил",
  hh_connected: true,
  id: 1,
  new_matches_count: 0,
  settings: { default_area: null, default_pages_limit: 1 },
};

describe("router", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("checks the real session by default", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 }));
    vi.stubGlobal("fetch", fetch);
    const router = createAppRouter();
    await router.push("/vacancies?text=Python");
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/me");
    expect(router.currentRoute.value).toMatchObject({
      path: "/login",
      query: { redirect: "/vacancies?text=Python" },
    });
  });
  it("redirects the start route to vacancies", async () => {
    const router = createAppRouter(async () => user);
    await router.push("/");
    await router.isReady();

    expect(router.currentRoute.value.path).toBe("/vacancies");
  });

  it("has routes for vacancies, saved searches, and HH authorization", () => {
    const router = createAppRouter(async () => user);
    expect(router.getRoutes().map((route) => route.path)).toEqual(
      expect.arrayContaining([
        "/vacancies",
        "/saved-searches",
        "/login",
        "/account",
      ]),
    );
  });

  it("resolves unknown paths to the not-found route", () => {
    const router = createAppRouter(async () => user);
    const route = router.resolve("/unknown");

    expect(route.name).toBe("not-found");
  });

  it("redirects an unauthenticated user to login with the requested path", async () => {
    const router = createAppRouter(async () => {
      throw new ApiError(401, "Не удалось выполнить запрос");
    });

    await router.push("/account");
    await router.isReady();

    expect(router.currentRoute.value).toMatchObject({
      path: "/login",
      query: { redirect: "/account" },
    });
  });
  it.each([0, 404, 503, 200])(
    "blocks protected pages when checking the session fails (%s)",
    async (status) => {
      const router = createAppRouter(async () => {
        throw new ApiError(status, "private error");
      });
      await router.push("/vacancies?text=Python");
      expect(router.currentRoute.value).toMatchObject({
        path: "/login",
        query: {
          redirect: "/vacancies?text=Python",
          reason: "session-check-failed",
        },
      });
    },
  );

  it("waits for successful session verification before entering a protected page", async () => {
    let finish!: (value: CurrentUser) => void;
    const router = createAppRouter(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    await router.push("/login");
    const navigation = router.push("/account");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(router.currentRoute.value.path).toBe("/login");
    finish(user);
    await navigation;
    expect(router.currentRoute.value.path).toBe("/account");
  });
  it.each([null, {}, { id: -1 }])(
    "rejects a malformed successful session response",
    async (payload) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))),
      );
      const router = createAppRouter();
      await router.push("/vacancies");
      expect(router.currentRoute.value).toMatchObject({
        path: "/login",
        query: { reason: "session-check-failed" },
      });
    },
  );
});

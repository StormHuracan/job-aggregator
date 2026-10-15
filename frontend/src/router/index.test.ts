import { describe, expect, it } from "vitest";

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
  it("redirects the start route to vacancies", async () => {
    const router = createAppRouter(async () => user);
    await router.push("/");
    await router.isReady();

    expect(router.currentRoute.value.path).toBe("/vacancies");
  });

  it("has routes for vacancies, saved searches, and HH authorization", () => {
    const router = createAppRouter(async () => user);
    expect(router.getRoutes().map((route) => route.path)).toEqual(
      expect.arrayContaining(["/vacancies", "/saved-searches", "/login", "/account"]),
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
});

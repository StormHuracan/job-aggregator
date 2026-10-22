import { afterEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser, updateSettings } from "./user";

describe("user API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the current user from the public session endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: 42,
            display_name: "Даниил",
            hh_connected: true,
            access_expires_at: null,
            new_matches_count: 3,
            settings: { default_area: "Москва", default_pages_limit: 2 },
          }),
        ),
      ),
    );

    await expect(getCurrentUser()).resolves.toMatchObject({
      display_name: "Даниил",
      settings: { default_area: "Москва" },
    });
  });

  it("sends only changed settings to the public settings endpoint", async () => {
    const fetchStub = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ default_area: null, default_pages_limit: 3 }),
      ),
    );
    vi.stubGlobal("fetch", fetchStub);

    await updateSettings({ default_area: null, default_pages_limit: 3 });

    const [url, init] = fetchStub.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/me/settings");
    expect(init).toMatchObject({ method: "PATCH" });
    expect(JSON.parse(String(init.body))).toEqual({
      default_area: null,
      default_pages_limit: 3,
    });
  });
});

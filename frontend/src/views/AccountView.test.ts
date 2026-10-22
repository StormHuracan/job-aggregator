import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import type { CurrentUser } from "../api/user";
import AccountView from "./AccountView.vue";

const user: CurrentUser = {
  id: 42,
  display_name: "Даниил",
  hh_connected: true,
  access_expires_at: "2030-01-01T00:00:00Z",
  new_matches_count: 2,
  settings: { default_area: "Москва", default_pages_limit: 3 },
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
let wrapper: VueWrapper;
async function open() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/account", component: AccountView },
      { path: "/login", component: { template: "<p>Вход</p>" } },
    ],
  });
  await router.push("/account");
  wrapper = mount(AccountView, { global: { plugins: [router] } });
  await flushPromises();
  return router;
}
afterEach(() => {
  wrapper?.unmount();
  vi.unstubAllGlobals();
});

describe("AccountView live API", () => {
  it("hides unavailable match statistics instead of showing a fake zero", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ ...user, new_matches_count: null })));
    await open();
    expect(wrapper.find(".matches").exists()).toBe(false);
    expect(wrapper.text()).toContain("Даниил");
  });
  it("loads the public user and settings without demo fallback", async () => {
    const fetch = vi.fn().mockResolvedValue(json(user));
    vi.stubGlobal("fetch", fetch);
    await open();
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/me");
    expect(wrapper.text()).toContain("Даниил");
    expect(wrapper.text()).not.toMatch(
      /демо|access.token|refresh.token|secret/i,
    );
    expect(
      wrapper.get<HTMLInputElement>('input[type="number"]').element.value,
    ).toBe("3");
  });

  it("saves once while pending and applies canonical server settings", async () => {
    let finish!: (value: Response) => void;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(user))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get('input[type="number"]').setValue(5);
    await wrapper.get("form").trigger("submit");
    await wrapper.get("form").trigger("submit");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(
      wrapper.get('button[type="submit"]').attributes("disabled"),
    ).toBeDefined();
    expect(fetch.mock.calls[1]?.[0]).toBe("/api/me/settings");
    expect(JSON.parse(String(fetch.mock.calls[1]?.[1].body))).toEqual({
      default_area: "Москва",
      default_pages_limit: 5,
    });
    finish(json({ default_area: "Казань", default_pages_limit: 4 }));
    await flushPromises();
    expect(
      wrapper.get<HTMLInputElement>('input[type="number"]').element.value,
    ).toBe("4");
    expect(
      wrapper.get<HTMLInputElement>('input:not([type="number"])').element.value,
    ).toBe("Казань");
    expect(wrapper.text()).toContain("Настройки сохранены.");
  });

  it("preserves input and shows server field validation", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(user))
        .mockResolvedValueOnce(
          json(
            {
              detail: [
                {
                  loc: ["body", "default_pages_limit"],
                  type: "greater_than",
                  input: "private-value",
                },
              ],
            },
            422,
          ),
        ),
    );
    await open();
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.get('input[type="number"]').attributes("aria-invalid")).toBe(
      "true",
    );
    expect(wrapper.text()).toContain("Введите целое число от 1");
    expect(wrapper.text()).not.toContain("private-value");
  });

  it("marks matches seen only after the server confirms", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(user))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper
      .findAll("button")
      .find((b) => b.text() === "Отметить прочитанными")!
      .trigger("click");
    await flushPromises();
    expect(fetch.mock.calls[1]?.[0]).toBe("/api/me/matches/mark-seen");
    expect(wrapper.get(".matches-count").text()).toBe("0");
  });

  it("logs out through the server before navigating to login", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(user))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    const router = await open();
    await wrapper
      .findAll("button")
      .find((b) => b.text() === "Выйти из кабинета")!
      .trigger("click");
    await flushPromises();
    expect(fetch.mock.calls[1]?.[0]).toBe("/api/auth/logout");
    expect(router.currentRoute.value.path).toBe("/login");
    expect(wrapper.text()).not.toContain("Даниил");
  });

  it.each(["load", "save", "logout"])(
    "expires the session during %s",
    async (operation) => {
      const fetch = vi.fn();
      if (operation !== "load") fetch.mockResolvedValueOnce(json(user));
      fetch.mockResolvedValue(new Response(null, { status: 401 }));
      vi.stubGlobal("fetch", fetch);
      const router = await open();
      if (operation === "save") await wrapper.get("form").trigger("submit");
      if (operation === "logout")
        await wrapper
          .findAll("button")
          .find((b) => b.text() === "Выйти из кабинета")!
          .trigger("click");
      await flushPromises();
      expect(router.currentRoute.value).toMatchObject({
        path: "/login",
        query: { redirect: "/account" },
      });
      expect(wrapper.text()).not.toContain("Даниил");
    },
  );

  it("shows a retryable loading failure without demo data", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json({}, 503))
        .mockResolvedValueOnce(json(user)),
    );
    await open();
    expect(wrapper.text()).toContain("Сервис временно недоступен");
    expect(wrapper.text()).not.toContain("Демо-пользователь");
    await wrapper
      .findAll("button")
      .find((b) => b.text() === "Повторить")!
      .trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Даниил");
  });

  it("ignores a late unauthorized response after leaving the page", async () => {
    let finish!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(user))
        .mockImplementationOnce(
          () =>
            new Promise<Response>((resolve) => {
              finish = resolve;
            }),
        ),
    );
    const router = await open();
    await wrapper.get("form").trigger("submit");
    wrapper.unmount();
    const pathAfterUnmount = router.currentRoute.value.path;
    finish(new Response(null, { status: 401 }));
    await flushPromises();
    expect(router.currentRoute.value.path).toBe(pathAfterUnmount);
  });
});

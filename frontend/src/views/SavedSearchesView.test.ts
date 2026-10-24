import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import type { SavedSearch } from "../api/saved-searches";
import SavedSearchesView from "./SavedSearchesView.vue";

const search: SavedSearch = {
  id: 7,
  name: "Python",
  text: "Python developer",
  area: "Москва",
  min_salary: 0,
  max_salary: 250000,
  is_enabled: true,
  created_at: "2026-10-20T12:00:00Z",
  updated_at: "2026-10-20T12:00:00Z",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
let wrapper: VueWrapper;

async function open() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/saved-searches", component: SavedSearchesView },
      { path: "/login", component: { template: "<p>Вход</p>" } },
    ],
  });
  await router.push("/saved-searches");
  wrapper = mount(SavedSearchesView, { global: { plugins: [router] } });
  await flushPromises();
  return router;
}

async function fill() {
  await wrapper.get('[data-action="new-search"]').trigger("click");
  await wrapper.get('[name="name"]').setValue("Python");
  await wrapper.get('[name="text"]').setValue("Python developer");
  await wrapper.get('[name="min_salary"]').setValue("0");
  await wrapper.get('[name="max_salary"]').setValue("250000");
}

afterEach(() => {
  wrapper?.unmount();
  vi.unstubAllGlobals();
});

describe("Saved searches live API", () => {
  it("confirms deletion and removes the row only after server success", async () => {
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json([search]))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get('[aria-label="Удалить поиск «Python»"]').trigger("click");
    expect(fetch).toHaveBeenCalledTimes(1);
    await wrapper.get("dialog button.button-primary").trigger("click");
    expect(wrapper.text()).toContain("Python developer");
    expect(fetch.mock.calls[1]?.[1].method).toBe("DELETE");
    finish(new Response(null, { status: 204 }));
    await flushPromises();
    expect(wrapper.text()).not.toContain("Python developer");
    expect(wrapper.text()).toContain("Поиск удалён");
  });
  it("loads the server list and shows criteria including zero salary", async () => {
    const fetch = vi.fn().mockResolvedValue(json([search]));
    vi.stubGlobal("fetch", fetch);
    await open();
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/saved-searches");
    expect(wrapper.text()).toContain("Python developer");
    expect(wrapper.text()).toContain("Москва");
    expect(wrapper.text()).toContain("от 0");
    expect(wrapper.text()).toContain("250");
  });

  it("renders loading, error/retry and empty states", async () => {
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValueOnce(json([]));
    vi.stubGlobal("fetch", fetch);
    await open();
    expect(wrapper.text()).toContain("Загрузка");
    finish(new Response("private failure", { status: 503 }));
    await flushPromises();
    expect(wrapper.text()).toContain("Сервис временно недоступен");
    expect(wrapper.text()).not.toContain("private failure");
    await wrapper.get('[data-action="reload"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Сохранённых поисков пока нет");
  });

  it("creates once while pending and uses the server response", async () => {
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json([]))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetch);
    await open();
    await fill();
    await wrapper.get("form").trigger("submit");
    await wrapper.get("form").trigger("submit");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(
      wrapper.get('button[type="submit"]').attributes("disabled"),
    ).toBeDefined();
    const [url, init] = fetch.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/saved-searches");
    expect(JSON.parse(String(init.body))).toEqual({
      name: "Python",
      text: "Python developer",
      area: null,
      min_salary: 0,
      max_salary: 250000,
    });
    finish(json({ ...search, name: "Серверное имя" }, 201));
    await flushPromises();
    expect(wrapper.text()).toContain("Серверное имя");
    expect(wrapper.find(".saved-form").exists()).toBe(false);
  });

  it("keeps form values and shows safe server field errors on 422", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json([]))
        .mockResolvedValueOnce(
          json(
            {
              detail: [
                {
                  loc: ["body", "name"],
                  type: "string_too_long",
                  input: "private",
                },
              ],
            },
            422,
          ),
        ),
    );
    await open();
    await fill();
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.get<HTMLInputElement>('[name="name"]').element.value).toBe(
      "Python",
    );
    expect(wrapper.get('[name="name"]').attributes("aria-invalid")).toBe(
      "true",
    );
    expect(wrapper.text()).toContain("Не более 255 символов");
    expect(wrapper.text()).not.toContain("private");
  });

  it("disables only the pending toggle and keeps the previous state on failure", async () => {
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        json([search, { ...search, id: 8, name: "Другой" }]),
      )
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(false);
    expect(
      wrapper.findAll('input[type="checkbox"]')[0]!.attributes("disabled"),
    ).toBeDefined();
    expect(
      wrapper.findAll('input[type="checkbox"]')[1]!.attributes("disabled"),
    ).toBeUndefined();
    finish(new Response(null, { status: 500 }));
    await flushPromises();
    expect(
      wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')[0]!.element
        .checked,
    ).toBe(true);
    expect(wrapper.text()).toContain("Не удалось выполнить запрос");
  });

  it("uses the PATCH response to update a search", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json([search]))
      .mockResolvedValueOnce(
        json({ ...search, is_enabled: false, text: "Обновлено сервером" }),
      );
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get('input[type="checkbox"]').setValue(false);
    await flushPromises();
    expect(fetch.mock.calls[1]?.[0]).toBe("/api/saved-searches/7");
    expect(
      wrapper.get<HTMLInputElement>('input[type="checkbox"]').element.checked,
    ).toBe(false);
    expect(wrapper.text()).toContain("Обновлено сервером");
  });

  it.each(["list", "create", "toggle"])(
    "redirects to login on 401 during %s",
    async (operation) => {
      const fetch = vi.fn();
      if (operation !== "list") fetch.mockResolvedValueOnce(json([search]));
      fetch.mockResolvedValue(new Response(null, { status: 401 }));
      vi.stubGlobal("fetch", fetch);
      const router = await open();
      if (operation === "create") {
        await fill();
        await wrapper.get("form").trigger("submit");
      }
      if (operation === "toggle")
        await wrapper.get('input[type="checkbox"]').setValue(false);
      await flushPromises();
      expect(router.currentRoute.value.path).toBe("/login");
      expect(router.currentRoute.value.query.redirect).toBe("/saved-searches");
      expect(wrapper.text()).not.toContain("Python developer");
    },
  );

  it("does not reuse the previous page instance's searches", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json([search]))
        .mockResolvedValueOnce(json([])),
    );
    await open();
    expect(wrapper.text()).toContain("Python developer");
    wrapper.unmount();
    await open();
    expect(wrapper.text()).not.toContain("Python developer");
    expect(wrapper.text()).toContain("Сохранённых поисков пока нет");
  });

  it.each([401, 200])(
    "ignores a late PATCH %s after another request expired the session",
    async (status) => {
      let first!: (response: Response) => void;
      let second!: (response: Response) => void;
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValueOnce(json([search, { ...search, id: 8 }]))
          .mockImplementationOnce(
            () =>
              new Promise<Response>((resolve) => {
                first = resolve;
              }),
          )
          .mockImplementationOnce(
            () =>
              new Promise<Response>((resolve) => {
                second = resolve;
              }),
          ),
      );
      const router = await open();
      await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(false);
      await wrapper.findAll('input[type="checkbox"]')[1]!.setValue(false);
      first(new Response(null, { status: 401 }));
      await flushPromises();
      second(
        status === 401
          ? new Response(null, { status })
          : json({ ...search, id: 8, name: "Поздние личные данные" }),
      );
      await flushPromises();
      expect(router.currentRoute.value).toMatchObject({
        path: "/login",
        query: { redirect: "/saved-searches" },
      });
      expect(wrapper.text()).not.toContain("Поздние личные данные");
    },
  );

  it("does not redirect after the page has been disposed", async () => {
    let finish!: (response: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json([search]))
        .mockImplementationOnce(
          () =>
            new Promise<Response>((resolve) => {
              finish = resolve;
            }),
        ),
    );
    const router = await open();
    await wrapper.get('input[type="checkbox"]').setValue(false);
    wrapper.unmount();
    const locationAfterUnmount = router.currentRoute.value.fullPath;
    finish(new Response(null, { status: 401 }));
    await flushPromises();
    expect(router.currentRoute.value.fullPath).toBe(locationAfterUnmount);
  });
});

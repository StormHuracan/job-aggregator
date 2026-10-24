import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import VacanciesView from "./VacanciesView.vue";

const vacancy = {
  id: 1,
  source: "hh",
  external_id: "1",
  title: "Python developer",
  company_name: "Команда",
  area_name: "Москва",
  salary_from: null,
  salary_to: 250000,
  salary_currency: "RUR",
  description: null,
  source_url: "https://hh.ru/vacancy/1",
  published_at: null,
  created_at: "2026-10-21T10:00:00Z",
  updated_at: "2026-10-21T10:00:00Z",
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
const list = (total = 21) => ({
  items: [vacancy],
  total,
  limit: 20,
  offset: 0,
});
let wrapper: VueWrapper;
const statisticsReload = vi.fn();
// Статистика загружается своим запросом; тесты страницы изолируют её заглушкой.
const statisticsStub = {
  template: '<div data-test="statistics-stub"></div>',
  setup(_props: unknown, { expose }: { expose: (exposed: object) => void }) {
    expose({ reload: statisticsReload });
  },
};
async function open(path = "/vacancies", { realStatistics = false } = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/vacancies", component: VacanciesView },
      { path: "/login", component: { template: "<p>Вход</p>" } },
    ],
  });
  await router.push(path);
  wrapper = mount(VacanciesView, {
    global: {
      plugins: [router],
      stubs: realStatistics ? {} : { VacancyStatistics: statisticsStub },
    },
  });
  await flushPromises();
  return router;
}
afterEach(() => {
  wrapper?.unmount();
  statisticsReload.mockReset();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Vacancy statistics on the page", () => {
  it("keeps the vacancy list visible when statistics fail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.endsWith("/vacancies/stats") ? response({}, 500) : response(list()),
    )));

    await open("/vacancies", { realStatistics: true });

    expect(wrapper.text()).toContain("Python developer");
    expect(wrapper.text()).toContain("Статистика по сохранённым вакансиям");
    expect(wrapper.text()).toContain("Не удалось выполнить запрос");
  });

  it("reloads statistics after a successful manual collection", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(response(
      url.endsWith("/collection/hh/run")
        ? { created: 1, updated: 0, skipped: 0, failed: 0, next_page: 1, exhausted: false }
        : list(),
    ))));
    await open();
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get(".collection-form input").setValue("Python");

    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();

    expect(statisticsReload).toHaveBeenCalledOnce();
  });
});

describe("Vacancies API search", () => {
  it("hides private vacancies when region suggestions return 401", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.includes("/hh/areas?") ? response({}, 401) : response(list()),
    )));
    const router = await open();
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get('[role="combobox"]').trigger("focus");
    await wrapper.get('[role="combobox"]').setValue("Мос");
    await vi.advanceTimersByTimeAsync(250);
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/login");
    expect(wrapper.text()).not.toContain("Python developer");
  });
  it("submits the selected region ID and clears it for an unrestricted search", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockImplementation((url: string) => Promise.resolve(response(
      url.includes("/hh/areas?") ? [{ id: "1", name: "Москва", parent_name: "Россия" }]
      : url.endsWith("/collection/hh/run") ? { created: 1, updated: 0, skipped: 0, failed: 0, next_page: 1, exhausted: false }
      : list(),
    )));
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get(".collection-form input").setValue("Python");
    const region = wrapper.get('[role="combobox"]');
    await region.trigger("focus");
    await region.setValue("Мос");
    await vi.advanceTimersByTimeAsync(250);
    await flushPromises();
    await wrapper.get('[role="option"]').trigger("click");
    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();
    const first = fetch.mock.calls.find(([url]) => url.endsWith("/collection/hh/run"))!;
    expect(JSON.parse(first[1].body).area).toBe("1");
    expect(wrapper.text()).not.toMatch(/Код региона|ID региона/);
    await wrapper.get('[aria-label="Очистить регион"]').trigger("click");
    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();
    const calls = fetch.mock.calls.filter(([url]) => url.endsWith("/collection/hh/run"));
    expect(JSON.parse(calls[1]![1].body).area).toBeNull();
  });

  it("validates the form before the explicit fresh check", async () => {
    const fetch = vi.fn().mockResolvedValue(response(list()));
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get(".source-toggle").trigger("click");
    const validity = vi.spyOn(wrapper.get<HTMLFormElement>(".collection-form").element, "reportValidity").mockReturnValue(false);
    await wrapper.findAll("button").find(b => b.text() === "Проверить новые вакансии")!.trigger("click");
    expect(validity).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("continues the same search and explicitly restarts without a client-side offset", async () => {
    const fetch = vi.fn().mockImplementation((url: string) => Promise.resolve(response(
      url.endsWith("/collection/hh/run")
        ? { created: 1, updated: 0, skipped: 19, failed: 0, next_page: 1, exhausted: false }
        : list(),
    )));
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get(".collection-form input").setValue("Python");
    for (let i = 0; i < 2; i++) {
      await wrapper.get(".collection-form").trigger("submit");
      await flushPromises();
    }
    expect(wrapper.text()).toContain("Продолжить поиск");
    expect(wrapper.text()).toContain("Уже есть в списке: 19");
    expect(wrapper.text()).not.toMatch(/общую базу|ID региона|пропущено|Сбор завершён/);
    await wrapper.findAll("button").find(b => b.text() === "Проверить новые вакансии")!.trigger("click");
    await flushPromises();
    const calls = fetch.mock.calls.filter(([url]) => url.endsWith("/collection/hh/run"));
    expect(calls.map(([, init]) => JSON.parse(init.body).restart)).toEqual([false, false, true]);
    expect(JSON.parse(calls[0]![1].body)).toEqual({ text: "Python", area: null, pages_limit: 1, restart: false });
  });

  it("stops at the end and allows a different query or an explicit fresh check", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(response(
      url.endsWith("/collection/hh/run")
        ? { created: 0, updated: 0, skipped: 20, failed: 0, next_page: 2, exhausted: true }
        : list(),
    ))));
    await open();
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get(".collection-form input").setValue("Python");
    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();
    expect(wrapper.get('.collection-form button[type="submit"]').attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("Все доступные вакансии по этому запросу просмотрены");
    expect(wrapper.findAll("button").find(b => b.text() === "Проверить новые вакансии")!.attributes("disabled")).toBeUndefined();
    await wrapper.get(".collection-form input").setValue("Java");
    expect(wrapper.get('.collection-form button[type="submit"]').attributes("disabled")).toBeUndefined();
    expect(wrapper.text()).not.toContain("Все доступные вакансии по этому запросу просмотрены");
  });

  it("can retry a failed collection without silently restarting the search", async () => {
    let requests = 0;
    const fetch = vi.fn().mockImplementation((url: string) => {
      if (!url.endsWith("/collection/hh/run")) return Promise.resolve(response(list()));
      requests++;
      return Promise.resolve(requests === 1 ? response({}, 503) : response({
        created: 1, updated: 0, skipped: 0, failed: 0, next_page: 2, exhausted: false,
      }));
    });
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get(".collection-form input").setValue("Python");
    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Сервис временно недоступен");
    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Найдено новых: 1");
    const calls = fetch.mock.calls.filter(([url]) => url.endsWith("/collection/hh/run"));
    expect(calls.map(([, init]) => JSON.parse(init.body).restart)).toEqual([false, false]);
  });

  it("asks to reconnect HH on collection 409 instead of claiming another run", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(response(list()))
      .mockResolvedValueOnce(response({}, 409)));
    await open();
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get(".collection-form input").setValue("Python");
    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Подключите HH.ru повторно");
    expect(wrapper.text()).not.toContain("Сбор уже выполняется");
  });
  it("loads URL filters including zero and uses server total for pagination", async () => {
    const fetch = vi
      .fn()
      .mockImplementation(() => Promise.resolve(response(list())));
    vi.stubGlobal("fetch", fetch);
    const router = await open(
      "/vacancies?text=Python&company=Команда&salary_from=0",
    );
    const url = new URL(fetch.mock.calls[0]![0], "https://example.test");
    expect(url.searchParams.get("salary_from")).toBe("0");
    expect(url.searchParams.get("company")).toBe("Команда");
    expect(wrapper.text()).toContain("Python developer");
    expect(wrapper.text()).toContain("до 250");
    const next = wrapper
      .findAll("button")
      .find((button) => button.text() === "Далее")!;
    expect(next.attributes("disabled")).toBeUndefined();
    await next.trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.query.offset).toBe("20");
  });

  it("does not filter results until submitted and restores fields on history navigation", async () => {
    const fetch = vi
      .fn()
      .mockImplementation(() => Promise.resolve(response(list())));
    vi.stubGlobal("fetch", fetch);
    const router = await open();
    await wrapper.get("#vacancy-query").setValue("Frontend");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("Python developer");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(router.currentRoute.value.query.text).toBe("Frontend");
    await router.replace("/vacancies?text=Python");
    await flushPromises();
    expect(wrapper.get<HTMLInputElement>("#vacancy-query").element.value).toBe(
      "Python",
    );
  });

  it("separates failure from empty results and allows retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response({}, 503))
        .mockResolvedValueOnce(response({ ...list(0), items: [] })),
    );
    await open();
    expect(wrapper.text()).toContain("Сервис временно недоступен");
    expect(wrapper.text()).not.toContain("Вакансии не найдены");
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Повторить загрузку")!
      .trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Вакансии не найдены");
  });

  it("ignores stale results from an earlier query", async () => {
    let finish!: (value: Response) => void;
    const fetch = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValue(response({ ...list(0), items: [] }));
    vi.stubGlobal("fetch", fetch);
    const router = await open();
    await router.replace("/vacancies?text=missing");
    await flushPromises();
    finish(response(list()));
    await flushPromises();
    expect(wrapper.text()).toContain("Вакансии не найдены");
    expect(wrapper.text()).not.toContain("Python developer");
  });

  it("redirects an expired session without rendering private results", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, 401)));
    const router = await open();
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/login");
    expect(router.currentRoute.value.query.redirect).toBe("/vacancies");
    expect(wrapper.text()).not.toContain("Python developer");
  });
  it("offers the first page when a saved URL is beyond current results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ ...list(), items: [], offset: 40 })),
    );
    const router = await open("/vacancies?offset=40");
    expect(wrapper.text()).toContain("На этой странице вакансий нет");
    expect(wrapper.text()).not.toContain("41–21");
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "На первую страницу")!
      .trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.query.offset).toBe("0");
  });
  it("hides previously loaded vacancies immediately when collection returns 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(list()))
        .mockResolvedValueOnce(response({}, 401)),
    );
    const router = await open();
    expect(wrapper.text()).toContain("Python developer");
    let finish!: (allow: boolean) => void;
    router.beforeEach((to) =>
      to.path === "/login"
        ? new Promise<boolean>((resolve) => {
            finish = resolve;
          })
        : true,
    );
    await wrapper.get(".source-toggle").trigger("click");
    await wrapper.get(".collection-form input").setValue("Python");
    await wrapper.get(".collection-form").trigger("submit");
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/vacancies");
    expect(wrapper.find("#vacancies-heading").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Python developer");
    finish(true);
    await flushPromises();
    expect(router.currentRoute.value.query.reason).toBe("session-expired");
  });
});

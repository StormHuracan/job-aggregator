import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import VacancyStatistics from "./VacancyStatistics.vue";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
const stats = (overrides: Record<string, unknown> = {}) => ({
  total_vacancies: 3,
  salary_currency: "RUR",
  salary_sample_size: 2,
  average_salary: 225000,
  top_areas: [
    { area_name: "Москва", vacancies_count: 2 },
    { area_name: "Казань", vacancies_count: 1 },
  ],
  ...overrides,
});
const text = (value: string) => value.replace(/\s+/g, " ").trim();
let wrapper: VueWrapper;

async function render() {
  wrapper = mount(VacancyStatistics);
  await flushPromises();
}

afterEach(() => {
  wrapper?.unmount();
  vi.unstubAllGlobals();
});

describe("VacancyStatistics", () => {
  it("loads real statistics from the API and shows the sample limits", async () => {
    const fetch = vi.fn().mockResolvedValue(response(stats()));
    vi.stubGlobal("fetch", fetch);

    await render();

    expect(fetch.mock.calls[0]![0]).toBe("/api/vacancies/stats");
    expect(wrapper.text()).toContain("Статистика по сохранённым вакансиям");
    expect(text(wrapper.get('[data-test="total"]').text())).toBe("3");
    expect(text(wrapper.get('[data-test="average"]').text())).toBe("225 000 ₽");
    expect(text(wrapper.get('[data-test="sample"]').text())).toBe("2");
    expect(wrapper.findAll("li").map((li) => text(li.text()))).toEqual([
      "Москва — 2",
      "Казань — 1",
    ]);
    expect(wrapper.text()).toContain("не сумма после вычета налогов");
  });

  it("shows insufficient data instead of a fake zero average", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(stats({ salary_sample_size: 0, average_salary: null })),
      ),
    );

    await render();

    expect(wrapper.get('[data-test="average"]').text()).toBe("Недостаточно данных");
    expect(wrapper.get('[data-test="average"]').text()).not.toContain("0");
  });

  it("shows an empty state for a database without vacancies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          stats({
            total_vacancies: 0,
            salary_sample_size: 0,
            average_salary: null,
            top_areas: [],
          }),
        ),
      ),
    );

    await render();

    expect(wrapper.text()).toContain("Сохранённых вакансий пока нет");
    expect(wrapper.find('[data-test="average"]').exists()).toBe(false);
  });

  it("shows a safe error and loads again after retry", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(response({ detail: "SELECT * FROM vacancies" }, 500))
      .mockResolvedValueOnce(response(stats()));
    vi.stubGlobal("fetch", fetch);

    await render();

    expect(wrapper.text()).toContain("Не удалось выполнить запрос");
    expect(wrapper.text()).not.toContain("SELECT");
    await wrapper.findAll("button").find((b) => b.text() === "Повторить")!.trigger("click");
    await flushPromises();

    expect(fetch).toHaveBeenCalledTimes(2);
    expect(text(wrapper.get('[data-test="average"]').text())).toBe("225 000 ₽");
  });
});

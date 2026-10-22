import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import VacancyCard from "./VacancyCard.vue";

describe("VacancyCard", () => {
  it("renders nullable fields safely and opens the source securely", () => {
    const wrapper = mount(VacancyCard, {
      props: { vacancy: { id: 1, source: "hh", external_id: "1", published_at: null, created_at: "2026-10-19T12:00:00Z", updated_at: "2026-10-19T12:00:00Z", title: "Python developer", company_name: null, area_name: null, salary_from: null, salary_to: null, salary_currency: null, description: "<strong>Безопасно</strong>", source_url: "https://hh.ru/vacancy/1" } },
    });
    expect(wrapper.text()).toContain("Зарплата не указана");
    expect(wrapper.text()).toContain("Безопасно");
    expect(wrapper.html()).not.toContain("<strong>");
    expect(wrapper.get("a").attributes()).toMatchObject({ target: "_blank", rel: "noopener noreferrer" });
  });
});

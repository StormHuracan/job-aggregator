import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import router from "../router";
import AppNavigation from "./AppNavigation.vue";

describe("AppNavigation", () => {
  it("renders labeled links to all main sections", () => {
    const wrapper = mount(AppNavigation, {
      global: { plugins: [router] },
    });

    expect(wrapper.get('li a[href="/vacancies"]').text()).toBe("Вакансии");
    expect(wrapper.get('a[href="/saved-searches"]').text()).toBe(
      "Сохранённые поиски",
    );
    expect(wrapper.get('a[href="/account"]').text()).toBe("Личный кабинет");
  });
});

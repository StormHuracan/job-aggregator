import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api/user", () => ({
  getCurrentUser: vi.fn().mockResolvedValue({
    display_name: "Даниил",
    hh_connected: true,
    id: 1,
    new_matches_count: 2,
    access_expires_at: null,
    settings: { default_area: "Москва", default_pages_limit: 1 },
  }),
  logout: vi.fn(),
  markMatchesSeen: vi.fn(),
  updateSettings: vi.fn(),
}));

vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import AccountView from "./AccountView.vue";

describe("AccountView", () => {
  it("shows public user data without any session secrets", async () => {
    const wrapper = mount(AccountView, {
      global: { stubs: { RouterLink: true, RouterView: true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Демо-пользователь");
    expect(wrapper.text()).toContain("Новых совпадений0");
    expect(wrapper.text()).not.toMatch(/access token|refresh token|secret/i);
  });
});

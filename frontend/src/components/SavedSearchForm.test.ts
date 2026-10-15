import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SavedSearchForm from "./SavedSearchForm.vue";

describe("SavedSearchForm", () => {
  it("shows field errors when required values are empty", async () => {
    const wrapper = mount(SavedSearchForm);
    await wrapper.get("form").trigger("submit");
    expect(wrapper.text()).toContain("Укажите название");
    expect(wrapper.text()).toContain("Укажите текст поиска");
  });
});

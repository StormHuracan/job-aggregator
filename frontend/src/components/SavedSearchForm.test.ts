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

  it.each([
    ["-1", "", "Введите целое неотрицательное число"],
    ["1.5", "", "Введите целое неотрицательное число"],
    ["200", "100", "Максимум не может быть меньше минимума"],
  ])("rejects invalid salary bounds %s / %s", async (min, max, message) => {
    const wrapper = mount(SavedSearchForm);
    await wrapper.get('[name="name"]').setValue("Python");
    await wrapper.get('[name="text"]').setValue("python");
    await wrapper.get('[name="min_salary"]').setValue(min);
    await wrapper.get('[name="max_salary"]').setValue(max);
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("create")).toBeUndefined();
    expect(wrapper.text()).toContain(message);
  });

  it("trims text, normalizes optional values and preserves zero salary", async () => {
    const wrapper = mount(SavedSearchForm);
    await wrapper.get('[name="name"]').setValue(" Python ");
    await wrapper.get('[name="text"]').setValue(" python ");
    await wrapper.get('[name="area"]').setValue("  ");
    await wrapper.get('[name="min_salary"]').setValue("0");
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("create")?.[0]).toEqual([{
      name: "Python", text: "python", area: null, min_salary: 0, max_salary: null,
    }]);
  });

  it.each(["name", "text", "area"])("rejects %s longer than the public limit", async (field) => {
    const wrapper = mount(SavedSearchForm);
    await wrapper.get('[name="name"]').setValue("Python");
    await wrapper.get('[name="text"]').setValue("python");
    await wrapper.get(`[name="${field}"]`).setValue("x".repeat(256));
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("create")).toBeUndefined();
    expect(wrapper.text()).toContain("Не более 255 символов");
  });

  it("counts Unicode code points like the backend", async () => {
    const wrapper = mount(SavedSearchForm);
    await wrapper.get('[name="name"]').setValue("😀".repeat(200));
    await wrapper.get('[name="text"]').setValue("python");
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("create")).toHaveLength(1);
  });
});

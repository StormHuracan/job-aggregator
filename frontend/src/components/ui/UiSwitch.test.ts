import { mount } from "@vue/test-utils";
import { expect, it } from "vitest";
import UiSwitch from "./UiSwitch.vue";
it("keeps the visual thumb on the confirmed state while the native checkbox changes", async () => {
  const wrapper = mount(UiSwitch, {
    props: { modelValue: true, label: "Поиск" },
  });
  await wrapper.get("input").setValue(false);
  expect(wrapper.get(".switch-track").attributes("data-checked")).toBe("true");
  await wrapper.setProps({ disabled: true });
  expect(wrapper.get(".switch-track").attributes("data-checked")).toBe("true");
  await wrapper.setProps({ modelValue: false, disabled: false });
  expect(wrapper.get(".switch-track").attributes("data-checked")).toBe("false");
});
it("keeps a stable accessible name and does not optimistically change server state", async () => {
  const wrapper = mount(UiSwitch, {
    props: { modelValue: true, label: "Активность поиска Python" },
  });
  await wrapper.get("input").setValue(false);
  expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
  expect(wrapper.get<HTMLInputElement>("input").element.checked).toBe(true);
  await wrapper.setProps({ modelValue: false, disabled: true });
  expect(wrapper.get("input").attributes("aria-label")).toBe(
    "Активность поиска Python",
  );
  expect(wrapper.get("input").attributes("disabled")).toBeDefined();
});

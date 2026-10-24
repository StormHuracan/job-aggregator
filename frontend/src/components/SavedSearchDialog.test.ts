import { flushPromises, mount } from "@vue/test-utils";
import { expect, it } from "vitest";
import SavedSearchDialog from "./SavedSearchDialog.vue";

it("starts a fresh form on reopen without carrying another search's fields", async () => {
  const wrapper = mount(SavedSearchDialog, {
    props: {
      open: true,
      initialValues: { text: "Python", area: "Москва", min_salary: 0 },
    },
  });
  await flushPromises();
  await wrapper.get('[name="name"]').setValue("Несохранённое название");
  await wrapper.setProps({ open: false });
  await wrapper.setProps({ open: true, initialValues: { text: "Rust" } });
  await flushPromises();
  expect(wrapper.get<HTMLInputElement>('[name="name"]').element.value).toBe("");
  expect(wrapper.get<HTMLInputElement>('[name="text"]').element.value).toBe(
    "Rust",
  );
  expect(wrapper.get<HTMLInputElement>('[name="area"]').element.value).toBe("");
  expect(
    wrapper.get<HTMLInputElement>('[name="min_salary"]').element.value,
  ).toBe("");
  wrapper.unmount();
});

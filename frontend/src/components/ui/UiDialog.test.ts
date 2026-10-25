import { mount, flushPromises } from "@vue/test-utils";
import { afterEach, expect, it, vi } from "vitest";
import UiDialog from "./UiDialog.vue";

afterEach(() => vi.restoreAllMocks());
it("wraps Tab and Shift+Tab at the edges of the modal", async () => {
  const wrapper = mount(UiDialog, {
    props: { open: true, title: "Новый поиск" },
    slots: { default: "<button data-last>Сохранить</button>" },
    attachTo: document.body,
  });
  await flushPromises();
  const last = wrapper.get<HTMLButtonElement>("[data-last]");
  last.element.focus();
  await last.trigger("keydown", { key: "Tab" });
  const first = wrapper.get<HTMLButtonElement>('[aria-label="Закрыть диалог"]');
  expect(document.activeElement).toBe(first.element);
  await first.trigger("keydown", { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(last.element);
  wrapper.unmount();
});
it("returns focus to main content if the opener is disabled while saving", async () => {
  const main = document.createElement("main");
  main.id = "main-content";
  main.tabIndex = -1;
  const opener = document.createElement("button");
  document.body.append(main, opener);
  opener.focus();
  const wrapper = mount(UiDialog, {
    props: { open: true, title: "Новый поиск" },
    attachTo: document.body,
  });
  await flushPromises();
  opener.disabled = true;
  await wrapper.setProps({ open: false });
  await flushPromises();
  expect(document.activeElement).toBe(main);
  wrapper.unmount();
  main.remove();
  opener.remove();
});
it("opens a native modal with a title and emits close on Escape", async () => {
  const showModal = vi.fn(function (this: HTMLDialogElement) {
    this.open = true;
  });
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: showModal,
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.open = false;
    },
  });
  const wrapper = mount(UiDialog, {
    props: { open: false, title: "Новый поиск" },
    attachTo: document.body,
  });
  await wrapper.setProps({ open: true });
  await flushPromises();
  expect(showModal).toHaveBeenCalledOnce();
  expect(wrapper.get("dialog").attributes("aria-labelledby")).toBe(
    wrapper.get("h2").attributes("id"),
  );
  await wrapper.get("dialog").trigger("cancel");
  expect(wrapper.emitted("close")).toHaveLength(1);
  wrapper.unmount();
});

import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import RegionPicker from "./RegionPicker.vue";

const moscow = { id: "1", name: "Москва", parent_name: "Россия" };
const json = (items: unknown, status = 200) => new Response(JSON.stringify(items), { status });
let wrapper: VueWrapper;
function open() {
  vi.useFakeTimers();
  wrapper = mount(RegionPicker, {
    props: { modelValue: null, "onUpdate:modelValue": (value: unknown) => wrapper.setProps({ modelValue: value }) },
  });
  return wrapper.get<HTMLInputElement>("input");
}
async function search(text = "Мос") {
  await wrapper.get("input").trigger("focus");
  await wrapper.get("input").setValue(text);
  await vi.advanceTimersByTimeAsync(250);
  await flushPromises();
}
afterEach(() => { wrapper?.unmount(); vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("region search", () => {
  it("debounces, selects by keyboard and emits an ID-bearing region instead of typed text", async () => {
    const fetch = vi.fn().mockResolvedValue(json([moscow]));
    vi.stubGlobal("fetch", fetch);
    const input = open();
    await input.trigger("focus");
    await input.setValue("М");
    await vi.advanceTimersByTimeAsync(300);
    expect(fetch).not.toHaveBeenCalled();
    await input.setValue("Мос");
    await vi.advanceTimersByTimeAsync(249);
    expect(fetch).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(fetch.mock.calls[0]![0]).toBe("/api/hh/areas?text=%D0%9C%D0%BE%D1%81");
    expect(wrapper.get('[role="option"]').text()).toBe("Москва · Россия");
    await input.trigger("keydown", { key: "ArrowDown" });
    expect(input.attributes("aria-activedescendant")).toBe(wrapper.get('[role="option"]').attributes("id"));
    await input.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("update:modelValue")!.at(-1)).toEqual([moscow]);
    expect(input.element.value).toBe("Москва · Россия");
    expect(input.attributes("aria-expanded")).toBe("false");
    await wrapper.get('[aria-label="Очистить регион"]').trigger("click");
    expect(input.element.value).toBe("");
    expect(wrapper.emitted("update:modelValue")!.at(-1)).toEqual([null]);
    await input.trigger("focus");
    await input.trigger("keydown", { key: "Enter" });
    expect(input.element.checkValidity()).toBe(true);
  });

  it("requires choosing a suggestion for nonempty input and clears the previous selection on edits", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([moscow])));
    const input = open();
    await search();
    expect(input.element.validationMessage).toBe("Выберите регион из списка или очистите поле.");
    await wrapper.get('[role="option"]').trigger("click");
    expect(input.element.validationMessage).toBe("");
    await input.setValue("Москв");
    expect(wrapper.emitted("update:modelValue")!.at(-1)).toEqual([null]);
    expect(input.element.checkValidity()).toBe(false);
  });

  it("ignores stale results immediately when the user changes the query", async () => {
    let finish!: (value: Response) => void;
    const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>(r => { finish = r; })).mockResolvedValue(json([]));
    vi.stubGlobal("fetch", fetch);
    open();
    await search("Мос");
    await wrapper.get("input").setValue("Каз");
    finish(json([moscow]));
    await flushPromises();
    expect(wrapper.text()).not.toContain("Москва");
    await vi.advanceTimersByTimeAsync(250);
    await flushPromises();
    expect(wrapper.text()).toContain("Ничего не найдено");
    await wrapper.get("input").trigger("keydown", { key: "Escape" });
    expect(wrapper.get("input").attributes("aria-expanded")).toBe("false");
  });

  it.each([401, 409, 503])("handles %s without pretending the region list is empty", async status => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "private" }, status)));
    open();
    await search();
    if (status === 401) expect(wrapper.emitted("unauthorized")).toHaveLength(1);
    else {
      expect(wrapper.text()).toContain(status === 409 ? "Подключите HH.ru повторно" : "Не удалось загрузить регионы");
      expect(wrapper.text()).not.toContain("Ничего не найдено");
      expect(wrapper.text()).not.toContain("private");
    }
  });

  it("ignores late failures after unmount", async () => {
    let finish!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise<Response>(resolve => { finish = resolve; })));
    open();
    await search();
    wrapper.unmount();
    finish(json({}, 401));
    await flushPromises();
    expect(wrapper.emitted("unauthorized")).toBeUndefined();
  });

  it("keeps retry reachable when keyboard focus moves inside the picker", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json({}, 503)).mockResolvedValue(json([moscow]));
    vi.stubGlobal("fetch", fetch);
    const input = open();
    await search();
    const retry = wrapper.findAll("button").find(button => button.text() === "Повторить")!;
    await input.trigger("blur", { relatedTarget: retry.element });
    await input.trigger("focusout", { relatedTarget: retry.element });
    expect(wrapper.text()).toContain("Повторить");
    await retry.trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="option"]').text()).toBe("Москва · Россия");
    await input.trigger("focusout", { relatedTarget: document.body });
    expect(input.attributes("aria-expanded")).toBe("false");
  });
});

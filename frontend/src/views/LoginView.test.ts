import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import LoginView from "./LoginView.vue";

let wrapper: VueWrapper;
async function open(path = "/login") {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: "/login", component: LoginView },
    { path: "/account", component: { template: "<p>Кабинет</p>" }, meta: { requiresAuth: true } },
  ] });
  await router.push(path);
  wrapper = mount(LoginView, { global: { plugins: [router] } });
  await flushPromises();
  return router;
}
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const options = () => new Response(JSON.stringify({ method: "otp" }));

describe("HH login options", () => {
  it("shows start failures inline and retries configuration without leaving login", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(null, { status: 503 })).mockResolvedValueOnce(options());
    vi.stubGlobal("fetch", fetch);
    const router = await open();
    expect(wrapper.text()).toContain("Не удалось начать вход");
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.find('[name="username"]').exists()).toBe(true);
    expect(router.currentRoute.value.path).toBe("/login");
  });
  it("needs no popup or manual mobile callback", async () => {
    const popup = vi.spyOn(window, "open").mockReturnValue(null);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(options()));
    await open();
    expect(popup).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain("hhandroid");
    expect(wrapper.find('[name="username"]').exists()).toBe(true);
  });
  it("validates malformed codes before sending to HH", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(options()).mockResolvedValueOnce(
      new Response(JSON.stringify({ step: "code", retry_after: 60 })),
    );
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get('[name="username"]').setValue("user@example.test");
    await wrapper.get("form").trigger("submit"); await flushPromises();
    await wrapper.get('[name="code"]').setValue("not-a-code");
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("Введите от 4 до 8 цифр");
  });
  it("keeps a safe retry for an unavailable session check", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(options()));
    const router = await open("/login?reason=session-check-failed&redirect=//evil.test");
    expect(wrapper.text()).toContain("Защищённые данные не загружены");
    await wrapper.get(".retry-session").trigger("click"); await flushPromises();
    expect(router.currentRoute.value.path).toBe("/account");
  });
});

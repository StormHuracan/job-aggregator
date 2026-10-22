import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import LoginView from "./LoginView.vue";

let wrapper: VueWrapper;
async function open() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: "/login", component: LoginView },
    { path: "/account", component: { template: "<p>Кабинет</p>" }, meta: { requiresAuth: true } },
  ] });
  await router.push("/login");
  wrapper = mount(LoginView, { global: { plugins: [router] } });
  return router;
}
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const start = () => new Response(JSON.stringify({ mode: "mobile", authorization_url: "https://hh.ru/oauth/authorize?client_id=sdk&state=browser-state" }));

describe("HH builtin login", () => {
  it("shows start failures inline without leaving login", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));
    const router = await open();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Не удалось начать вход");
    expect(router.currentRoute.value.path).toBe("/login");
    expect(wrapper.get("button").attributes("disabled")).toBeUndefined();
  });
  it("supports blocked popups and completes through POST without URL credentials", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    const fetch = vi.fn().mockResolvedValueOnce(start()).mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    const router = await open();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.get('a[target="_blank"]').attributes("href")).toContain("https://hh.ru/oauth/authorize");
    const url = "hhandroid://oauthresponse?code=private-code&state=browser-state";
    await wrapper.get("input").setValue(url);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(fetch.mock.calls[1]?.[0]).toBe("/api/auth/hh/complete");
    expect(fetch.mock.calls[1]?.[1].method).toBe("POST");
    expect(JSON.parse(fetch.mock.calls[1]?.[1].body)).toEqual({ return_url: url });
    expect(router.currentRoute.value.fullPath).toBe("/account");
  });
  it("rejects malformed addresses locally", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    const fetch = vi.fn().mockResolvedValue(start());
    vi.stubGlobal("fetch", fetch);
    await open();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    await wrapper.get("input").setValue("https://evil.test/?code=secret");
    await wrapper.get("form").trigger("submit");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("Вставьте полный адрес");
  });
});

import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import LoginView from "./LoginView.vue";
import { createAppRouter } from "../router";
import { ApiError } from "../api/client";

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
  it("shows one calm unavailable state and retries without leaving login", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(null, { status: 503 })).mockResolvedValueOnce(options());
    vi.stubGlobal("fetch", fetch);
    const router = await open();
    expect(wrapper.get("h1").text()).toBe("Сервис временно недоступен");
    expect(wrapper.findAll("button")).toHaveLength(1);
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Код нужен только для входа");
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
    const fetch = vi.fn().mockResolvedValue(options());
    vi.stubGlobal("fetch", fetch);
    const router = await open("/login?reason=session-check-failed&redirect=//evil.test");
    expect(wrapper.text()).toContain("Сервис временно недоступен");
    expect(fetch).not.toHaveBeenCalled();
    await wrapper.get(".retry-session").trigger("click"); await flushPromises();
    expect(router.currentRoute.value.path).toBe("/account");
  });

  it("uses the real guard to recover or show normal login when the session expired", async () => {
    const loader = vi.fn().mockRejectedValueOnce(new ApiError(0, "offline"))
      .mockRejectedValueOnce(new ApiError(401, "expired"));
    const fetch = vi.fn().mockResolvedValue(options());
    vi.stubGlobal("fetch", fetch);
    const router = createAppRouter(loader);
    await router.push("/account");
    wrapper = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("Сервис временно недоступен");
    expect(fetch).not.toHaveBeenCalled();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.query.reason).toBe("auth-required");
    expect(wrapper.find('[name="username"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain("Сервис временно недоступен");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("keeps one disabled retry while checking and never opens protected routes on failure", async () => {
    let finish!: (value: unknown) => void;
    const loader = vi.fn().mockRejectedValueOnce(new ApiError(0, "offline"))
      .mockImplementationOnce(() => new Promise<never>((_, reject) => { finish = reject; }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(options()));
    const router = createAppRouter(loader);
    await router.push("/account");
    wrapper = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.get("button").attributes("disabled")).toBeDefined();
    finish(new ApiError(0, "offline"));
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/login");
    expect(wrapper.findAll("button")).toHaveLength(1);
    expect(wrapper.text()).toContain("Сервис временно недоступен");
  });

  it("opens the original protected page only after the real guard recovers", async () => {
    const loader = vi.fn().mockRejectedValueOnce(new ApiError(0, "offline")).mockResolvedValueOnce({
      id: 42, display_name: "Тест", hh_connected: true, access_expires_at: null,
      new_matches_count: null, settings: { default_area: null, default_pages_limit: 1 },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(options()));
    const router = createAppRouter(loader);
    await router.push("/vacancies?text=Python");
    wrapper = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.fullPath).toBe("/vacancies?text=Python");
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("ignores old login options after a failed session check replaces the page state", async () => {
    let finish!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise<Response>(resolve => { finish = resolve; })));
    const router = await open();
    await router.replace("/login?reason=session-check-failed");
    finish(options());
    await flushPromises();
    expect(wrapper.find('[name="username"]').exists()).toBe(false);
    expect(wrapper.findAll("button")).toHaveLength(1);
    expect(wrapper.text()).toContain("Сервис временно недоступен");
  });
});

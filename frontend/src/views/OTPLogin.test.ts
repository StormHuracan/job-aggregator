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
  await flushPromises();
  return router;
}
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const options = () => json({ method: "otp" });
const codePrompt = () => json({ step: "code", retry_after: 60, expires_in: 600 });
async function sendLogin() {
  await wrapper.get('[name="username"]').setValue("user@example.test");
  await wrapper.get("form").trigger("submit");
  await flushPromises();
}
afterEach(() => {
  wrapper?.unmount();
  vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers();
});

describe("HH OTP login", () => {
  it("sends login and verifies code through POST without a manual callback", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(options()).mockResolvedValueOnce(codePrompt())
      .mockResolvedValueOnce(json({ step: "authenticated" }));
    vi.stubGlobal("fetch", fetch);
    const router = await open(); await sendLogin();
    expect(wrapper.text()).not.toContain("hhandroid");
    await wrapper.get('[name="code"]').setValue("123456");
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(fetch.mock.calls[1]?.[0]).toBe("/api/auth/hh/otp/start");
    expect(JSON.parse(fetch.mock.calls[1]?.[1].body)).toEqual({ username: "user@example.test" });
    expect(fetch.mock.calls[2]?.[0]).toBe("/api/auth/hh/otp/verify");
    expect(JSON.parse(fetch.mock.calls[2]?.[1].body)).toEqual({ code: "123456" });
    expect(fetch.mock.calls[2]?.[1].credentials).toBe("include");
    expect(router.currentRoute.value.fullPath).toBe("/account");
  });
  it("keeps the code form on wrong code and clears rejected input", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(options()).mockResolvedValueOnce(codePrompt())
      .mockResolvedValueOnce(json({}, 400)));
    await open(); await sendLogin();
    await wrapper.get('[name="code"]').setValue("1111");
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("Код не подошёл");
    expect((wrapper.get('[name="code"]').element as HTMLInputElement).value).toBe("");
  });
  it("presents captcha and posts the manual answer", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(options())
      .mockResolvedValueOnce(json({ step: "captcha", captcha_image: "data:image/png;base64,cG5n", retry_after: 60 }))
      .mockResolvedValueOnce(codePrompt());
    vi.stubGlobal("fetch", fetch);
    await open(); await sendLogin();
    expect(wrapper.get('img[alt="Проверка HH.ru"]').attributes("src")).toBe("data:image/png;base64,cG5n");
    await wrapper.get('[name="captcha"]').setValue("answer");
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(fetch.mock.calls[2]?.[0]).toBe("/api/auth/hh/otp/captcha");
    expect(JSON.parse(fetch.mock.calls[2]?.[1].body)).toEqual({ text: "answer" });
    expect(wrapper.find('[name="code"]').exists()).toBe(true);
  });
  it("enforces resend countdown and supports changing login", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockResolvedValueOnce(options()).mockResolvedValueOnce(codePrompt())
      .mockResolvedValueOnce(codePrompt()).mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await open(); await sendLogin();
    expect(wrapper.get('[data-test="resend"]').attributes("disabled")).toBeDefined();
    await vi.advanceTimersByTimeAsync(61000);
    expect(wrapper.get('[data-test="resend"]').attributes("disabled")).toBeUndefined();
    await wrapper.get('[data-test="resend"]').trigger("click"); await flushPromises();
    await wrapper.get('[data-test="change-login"]').trigger("click"); await flushPromises();
    expect(fetch.mock.calls[3]?.[0]).toBe("/api/auth/hh/otp/cancel");
    expect(wrapper.find('[name="username"]').exists()).toBe(true);
  });
  it("returns to login when the attempt expires", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(options()).mockResolvedValueOnce(codePrompt())
      .mockResolvedValueOnce(json({}, 410)));
    await open(); await sendLogin();
    await wrapper.get('[name="code"]').setValue("1234");
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.find('[name="username"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("Срок действия");
  });
  it("shows network failures and allows retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(options()).mockRejectedValue(new Error("offline")));
    await open(); await sendLogin();
    expect(wrapper.text()).toContain("Не удалось связаться");
    expect(wrapper.get('button[type="submit"]').attributes("disabled")).toBeUndefined();
  });
  it("preserves configured redirect OAuth mode", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ method: "oauth" })));
    await open();
    expect(wrapper.get('[data-test="oauth-login"]').attributes("href")).toBe("/api/auth/hh/login");
    expect(wrapper.find('[name="username"]').exists()).toBe(false);
  });
});

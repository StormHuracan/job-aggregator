import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import TelegramConnection from "./TelegramConnection.vue";

const replace = vi.hoisted(() => vi.fn());
vi.mock("vue-router", () => ({ useRouter: () => ({ replace }) }));
let wrapper: VueWrapper;
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
function mockFetch(action?: () => Promise<Response>) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/me/telegram" && (!init?.method || init.method === "GET")) {
      return json({ enabled: true, connected: false });
    }
    return action ? action() : new Response(null, { status: 204 });
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
afterEach(() => { wrapper?.unmount(); vi.unstubAllGlobals(); vi.clearAllMocks(); vi.useRealTimers(); });

describe("Telegram connection", () => {
  it("creates a link only on click and requires explicit navigation to the bot", async () => {
    const fetch = mockFetch(async () => json({ url: "https://t.me/test_bot?start=secret", expires_at: new Date(Date.now() + 600000).toISOString() }));
    wrapper = mount(TelegramConnection);
    await flushPromises();
    expect(fetch).toHaveBeenCalledTimes(1);
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(fetch.mock.calls.at(-1)![0]).toBe("/api/me/telegram/link");
    expect(fetch.mock.calls.at(-1)![1]?.method).toBe("POST");
    expect(wrapper.get("a").attributes("href")).toBe("https://t.me/test_bot?start=secret");
    expect(wrapper.text()).toContain("ещё не подтверждает привязку");
  });
  it("disconnects through API before confirming success", async () => {
    const fetch = mockFetch();
    wrapper = mount(TelegramConnection); await flushPromises();
    await wrapper.findAll("button")[1]!.trigger("click"); await flushPromises();
    expect(fetch.mock.calls.at(-1)![1]?.method).toBe("DELETE");
    expect(wrapper.text()).toContain("Telegram отключён");
  });
  it.each(["javascript:alert(1)", "https://evil.test/?start=secret"])("rejects unsafe link %s", async (url) => {
    mockFetch(async () => json({ url, expires_at: new Date(Date.now() + 600000).toISOString() }));
    wrapper = mount(TelegramConnection); await flushPromises();
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.find("a").exists()).toBe(false);
    expect(wrapper.text()).toContain("Не удалось");
  });
  it("refreshes the confirmed binding and does not offer another link", async () => {
    mockFetch(); wrapper = mount(TelegramConnection); await flushPromises();
    vi.stubGlobal("fetch", vi.fn(async () => json({ enabled: true, connected: true })));
    await wrapper.findAll("button")[2]!.trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("Telegram подключён");
    expect(wrapper.get("button").attributes("disabled")).toBeDefined();
  });
  it.each([409, 503])("shows safe error for %s", async (status) => {
    mockFetch(async () => json({ detail: "secret" }, status));
    wrapper = mount(TelegramConnection); await flushPromises();
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain("secret");
  });
  it("hides account data through the parent when session expires", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({}, 401)));
    wrapper = mount(TelegramConnection); await flushPromises();
    expect(wrapper.emitted("sessionExpired")).toHaveLength(1);
    expect(replace).toHaveBeenCalled();
  });
});

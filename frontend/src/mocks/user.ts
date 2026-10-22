import type { CurrentUser, UserSettings, UserSettingsUpdate } from "../api/user";

let user: CurrentUser = {
  access_expires_at: null,
  display_name: "Демо-пользователь",
  hh_connected: false,
  id: 1,
  new_matches_count: 0,
  settings: { default_area: null, default_pages_limit: 1 },
};

export const accountFixture = {
  async getCurrentUser(): Promise<CurrentUser> { return structuredClone(user); },
  async markMatchesSeen(): Promise<void> { user.new_matches_count = 0; },
  async logout(): Promise<void> {},
  async updateSettings(update: UserSettingsUpdate): Promise<UserSettings> {
    user.settings = { ...user.settings, ...update };
    return structuredClone(user.settings);
  },
};

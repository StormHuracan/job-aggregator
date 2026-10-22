import { request } from "./client";

export type UserSettings = {
  default_area: string | null;
  default_pages_limit: number;
};

export type UserSettingsUpdate = {
  default_area?: string | null;
  default_pages_limit?: number;
};

export type CurrentUser = {
  id: number;
  display_name: string;
  hh_connected: boolean;
  access_expires_at: string | null;
  new_matches_count: number | null;
  settings: UserSettings;
};

export function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/me");
}

export function updateSettings(settings: UserSettingsUpdate): Promise<UserSettings> {
  return request<UserSettings>("/me/settings", {
    body: JSON.stringify(settings),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
}

export function markMatchesSeen(): Promise<void> {
  return request<void>("/me/matches/mark-seen", { method: "POST" });
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

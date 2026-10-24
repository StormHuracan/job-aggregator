import { request } from "./client";

export type CollectionRunRequest = {
  text: string;
  area: string | null;
  pages_limit: number;
  restart?: boolean;
};

export type CollectionRunResponse = {
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  next_page: number;
  exhausted: boolean;
};

export function runCollection(input: CollectionRunRequest): Promise<CollectionRunResponse> {
  return request<CollectionRunResponse>("/collection/hh/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

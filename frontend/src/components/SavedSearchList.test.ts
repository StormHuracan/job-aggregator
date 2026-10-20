import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SavedSearchList from "./SavedSearchList.vue";

describe("SavedSearchList", () => {
  it("shows an empty state", () => {
    expect(mount(SavedSearchList, { props: { searches: [] } }).text()).toContain("Сохранённых поисков пока нет");
  });
});

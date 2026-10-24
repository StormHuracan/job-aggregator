import { describe, expect, it } from "vitest";
import {
  safeExternalVacancyUrl,
  vacancySnippetToText,
} from "./vacancy-presentation";

describe("vacancy presentation", () => {
  it("cleans HH markup and encoded markers without rendering HTML", () => {
    expect(
      vacancySnippetToText("<highlight>Python</highlight> &amp; SQL"),
    ).toBe("Python & SQL");
    expect(
      vacancySnippetToText("&lt;highlight&gt;Python&lt;/highlight&gt;"),
    ).toBe("Python");
    expect(
      vacancySnippetToText(
        "<script>alert(1)</script><style>p{}</style><p>Работа</p><p>Удалённо</p>",
      ),
    ).toBe("Работа Удалённо");
    expect(vacancySnippetToText(null)).toBe("");
  });
  it("permits only absolute HTTP links", () => {
    for (const url of [
      "javascript:alert(1)",
      "data:text/html,hi",
      "",
      "/vacancies/1",
      "//hh.ru/1",
    ])
      expect(safeExternalVacancyUrl(url)).toBeNull();
    expect(safeExternalVacancyUrl("https://hh.ru/vacancy/1")).toBe(
      "https://hh.ru/vacancy/1",
    );
  });
  it("preserves encoded type parameters in technical descriptions", () => {
    expect(
      vacancySnippetToText("Опыт C# List&lt;string&gt; и Java List&lt;T&gt;"),
    ).toBe("Опыт C# List<string> и Java List<T>");
  });
});

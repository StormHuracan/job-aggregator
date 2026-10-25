/** Инертный template не загружает ресурсы; в интерфейс попадает только текст. */
export function vacancySnippetToText(value: string | null): string {
  const template = document.createElement("template");
  template.innerHTML = value ?? "";
  template.content
    .querySelectorAll("script,style,iframe,object,noscript")
    .forEach((node) => node.remove());
  template.content.querySelectorAll("p,div,li,br,h1,h2,h3").forEach((node) => {
    node.before(document.createTextNode(" "));
    node.after(document.createTextNode(" "));
  });
  let text = template.content.textContent ?? "";
  // Повторно декодируем entities как текст, не как HTML: List&lt;T&gt; должен сохраниться.
  for (let pass = 0; pass < 2; pass++) {
    template.innerHTML = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    text = template.content.textContent ?? "";
  }
  return text
    .replace(/<(script|style|iframe|object)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, "")
    .replace(
      /<\/?(?:highlight|p|div|li|br|strong|b|em|i|h[1-6])\b[^>]*>/gi,
      " ",
    )
    .replace(/\s+/g, " ")
    .trim();
}

export function safeExternalVacancyUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

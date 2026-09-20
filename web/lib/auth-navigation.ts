/** Only return to application pages, never external URLs or auth/API loops. */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\s]/.test(value)) return "/dashboard";
  try {
    const url = new URL(value, "http://app.local");
    if (url.origin !== "http://app.local" || /^\/(login|signup|api)(\/|$)/.test(url.pathname)) return "/dashboard";
    return url.pathname + url.search + url.hash;
  } catch {
    return "/dashboard";
  }
}

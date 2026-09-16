/** Shared formatters (§62-63). Numbers use tabular-nums via CSS classes. */

export function fmtPct(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(digits)}%`;
}

export function fmtActivePp(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  const v = (x * 100).toFixed(digits);
  return `${x > 0 ? "+" : ""}${v}%p`;
}

export function fmtReturn(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  const v = (x * 100).toFixed(digits);
  return `${x > 0 ? "+" : ""}${v}%`;
}

export function fmtNav(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return x.toFixed(digits);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = iso.slice(0, 10).split("-");
  if (d.length !== 3) return iso;
  return `${d[0]}.${d[1]}.${d[2]}`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}

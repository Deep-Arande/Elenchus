/** Small formatting helpers. Expanded in later phases. */

export function formatDate(
  value: string | number | Date,
  locale = "en-IN",
): string {
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

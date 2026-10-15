import { getRequestConfig } from "next-intl/server";

// V1 ships an English UI; Hindi (hi) and Marathi (mr) message files exist and
// are ready to switch on (AGENTS.md section 3, 10.5). Locale selection/routing
// is added in a later phase; for now we serve a fixed locale.
export const defaultLocale = "en" as const;
export const locales = ["en", "hi", "mr"] as const;
export type Locale = (typeof locales)[number];

export default getRequestConfig(async () => {
  const locale = defaultLocale;
  const messages = (await import(`../messages/${locale}.json`)).default;
  return { locale, messages };
});

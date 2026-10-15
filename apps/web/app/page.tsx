import { useTranslations } from "next-intl";

export default function Home() {
  const t = useTranslations("home");

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-4 px-6 py-16">
      <h1 className="text-4xl font-semibold tracking-tight">{t("title")}</h1>
      <p className="text-xl text-neutral-600 dark:text-neutral-300">
        {t("tagline")}
      </p>
      <p className="text-base leading-relaxed text-neutral-700 dark:text-neutral-300">
        {t("subtitle")}
      </p>
      <p className="text-sm text-neutral-500">{t("scaffoldNotice")}</p>
      <footer className="mt-8 border-t border-neutral-200 pt-4 text-xs text-neutral-500 dark:border-neutral-800">
        {t("disclaimer")}
      </footer>
    </main>
  );
}

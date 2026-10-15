import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

export default function Home() {
  const t = useTranslations("home");

  return (
    <main className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-reading flex-col justify-center gap-4 px-6 py-16">
      <h1 className="font-serif text-4xl font-semibold tracking-tight">{t("title")}</h1>
      <p className="text-xl text-muted">{t("tagline")}</p>
      <p className="text-base leading-relaxed text-ink">{t("subtitle")}</p>
      <div className="mt-2">
        <Link
          href="/try"
          className="inline-flex items-center gap-2 rounded-[var(--radius)] bg-accent px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          Check a claim
          <ArrowRight size={16} />
        </Link>
      </div>
      <footer className="mt-8 border-t border-border pt-4 text-xs text-muted">
        {t("disclaimer")}
      </footer>
    </main>
  );
}

import Link from "next/link";
import { ScanSearch } from "lucide-react";
import { ThemeToggle } from "./theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-5">
        <Link href="/" className="flex items-center gap-2 font-serif text-lg font-semibold">
          <ScanSearch size={18} className="text-accent" />
          Elenchus
        </Link>
        <nav className="flex items-center gap-4">
          <Link href="/try" className="text-sm text-muted transition-colors hover:text-ink">
            New check
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { createCheck, getInfo, runCheck, type CheckState, type Language } from "@/lib/proto";
import { SAMPLE_CLAIMS } from "@/lib/proto-samples";

interface EditableClaim {
  id: string;
  text: string;
  selected: boolean;
  checkworthy: boolean;
  claim_type: string;
}

export default function TryPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [language, setLanguage] = useState<Language>("en");
  const [check, setCheck] = useState<CheckState | null>(null);
  const [claims, setClaims] = useState<EditableClaim[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mock, setMock] = useState<boolean | null>(null);

  useEffect(() => {
    getInfo()
      .then((i) => setMock(i.llm_mock || i.search_mock))
      .catch(() => setMock(null));
  }, []);

  async function onExtract() {
    setBusy(true);
    setError(null);
    try {
      const c = await createCheck(text.trim(), language);
      setCheck(c);
      setClaims(
        c.claims.map((cl) => ({
          id: cl.id,
          text: cl.text_original,
          selected: cl.selected,
          checkworthy: cl.checkworthy,
          claim_type: cl.claim_type,
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the API.");
    } finally {
      setBusy(false);
    }
  }

  async function onRun() {
    if (!check) return;
    setBusy(true);
    setError(null);
    try {
      await runCheck(
        check.id,
        claims.map((c) => ({ id: c.id, selected: c.selected, text_original: c.text })),
        language,
      );
      router.push(`/try/${check.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the check.");
      setBusy(false);
    }
  }

  const selectedCount = claims.filter((c) => c.selected).length;

  return (
    <main className="mx-auto max-w-reading px-5 py-10">
      <h1 className="font-serif text-3xl font-semibold tracking-tight">Check a claim</h1>
      <p className="mt-2 text-muted">
        Paste a message, forward or statement. Elenchus finds the checkable claims, searches the
        web and shows you the evidence — it never gives a verdict.
      </p>

      {mock && (
        <p className="mt-4 rounded-[var(--radius)] border border-border bg-surface px-3 py-2 text-xs text-muted">
          Running in <span className="font-medium text-ink">mock mode</span> — add
          <code className="mx-1">GEMINI_API_KEY</code> and
          <code className="mx-1">FIRECRAWL_API_KEY</code> for real results.
        </p>
      )}

      {!check && (
        <>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            placeholder="Paste text here…"
            className="mt-6 w-full resize-y rounded-[var(--radius)] border border-border bg-surface p-4 text-ink outline-none focus:border-accent"
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted">Try:</span>
            {SAMPLE_CLAIMS.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => {
                  setText(s.text);
                  setLanguage(s.language);
                }}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted transition-colors hover:border-accent hover:text-ink"
              >
                {s.label}
              </button>
            ))}
          </div>
          <div className="mt-5 flex items-center gap-3">
            <label className="text-sm text-muted">
              Output language{" "}
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value as Language)}
                className="ml-1 rounded-[var(--radius)] border border-border bg-surface px-2 py-1 text-ink"
              >
                <option value="en">English</option>
                <option value="hi">हिन्दी</option>
                <option value="mr">मराठी</option>
              </select>
            </label>
            <button
              type="button"
              onClick={onExtract}
              disabled={busy || text.trim().length === 0}
              className="inline-flex items-center gap-2 rounded-[var(--radius)] bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy && <Loader2 size={15} className="animate-spin" />}
              Extract claims
            </button>
          </div>
        </>
      )}

      {check && (
        <section className="mt-8">
          <h2 className="font-serif text-xl font-semibold">Confirm the claims to check</h2>
          <p className="mt-1 text-sm text-muted">
            Untick anything you don&apos;t want checked. You can edit the wording.
          </p>
          <ul className="mt-4 space-y-3">
            {claims.map((c, i) => (
              <li
                key={c.id}
                className="flex items-start gap-3 rounded-[var(--radius)] border border-border bg-surface p-3"
              >
                <input
                  type="checkbox"
                  checked={c.selected}
                  onChange={(e) =>
                    setClaims((prev) =>
                      prev.map((x, j) => (j === i ? { ...x, selected: e.target.checked } : x)),
                    )
                  }
                  className="mt-1.5 h-4 w-4 accent-[var(--accent)]"
                />
                <div className="flex-1">
                  <input
                    value={c.text}
                    onChange={(e) =>
                      setClaims((prev) =>
                        prev.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)),
                      )
                    }
                    className="w-full bg-transparent text-ink outline-none"
                  />
                  {!c.checkworthy && (
                    <span className="mt-1 inline-block text-xs text-muted">
                      {c.claim_type} — not typically checkable
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-5 flex items-center gap-3">
            <button
              type="button"
              onClick={onRun}
              disabled={busy || selectedCount === 0}
              className="inline-flex items-center gap-2 rounded-[var(--radius)] bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy && <Loader2 size={15} className="animate-spin" />}
              Check {selectedCount} selected claim{selectedCount === 1 ? "" : "s"}
            </button>
            <button
              type="button"
              onClick={() => {
                setCheck(null);
                setClaims([]);
              }}
              className="text-sm text-muted hover:text-ink"
            >
              Start over
            </button>
          </div>
        </section>
      )}

      {error && <p className="mt-4 text-sm text-stance-contradicts">{error}</p>}

      <footer className="mt-12 border-t border-border pt-4 text-xs text-muted">
        Elenchus is a research demo. It surfaces evidence; it does not give verdicts. Always read the
        sources.
      </footer>
    </main>
  );
}

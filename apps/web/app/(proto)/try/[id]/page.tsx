"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ExternalLink, Loader2 } from "lucide-react";
import {
  getCheck,
  getGraph,
  streamEvents,
  updateSession,
  type CheckState,
  type Claim,
  type GraphData,
  type Language,
  type ProtoEvent,
} from "@/lib/proto";
import { GraphView } from "@/components/proto/graph-view";
import { StatusBadge } from "@/components/proto/status-badge";
import { StanceChip } from "@/components/proto/stance-chip";
import { TraceTimeline } from "@/components/proto/trace-timeline";

function confidenceWord(c: number | null): string {
  if (c === null) return "";
  if (c >= 0.75) return "High confidence";
  if (c >= 0.5) return "Moderate confidence";
  return "Weak evidence";
}

export default function ResultPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [check, setCheck] = useState<CheckState | null>(null);
  const [events, setEvents] = useState<ProtoEvent[]>([]);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>("en");

  useEffect(() => {
    let cancelled = false;
    getCheck(id)
      .then((c) => {
        if (!cancelled) {
          setCheck(c);
          setLanguage(c.language);
          if (c.status === "done") setDone(true);
        }
      })
      .catch((e) => !cancelled && setError(String(e)));

    const stop = streamEvents(id, {
      onEvent: (ev) => setEvents((prev) => [...prev, ev]),
      onDone: async () => {
        if (cancelled) return;
        setDone(true);
        try {
          setCheck(await getCheck(id));
          setGraph(await getGraph(id));
        } catch (e) {
          setError(String(e));
        }
      },
      onError: (m) => !cancelled && setError(m),
    });

    return () => {
      cancelled = true;
      stop();
    };
  }, [id]);

  async function onLanguage(next: Language) {
    setLanguage(next);
    try {
      await updateSession({ language: next });
    } catch {
      /* ignore */
    }
  }

  const selectedClaims = useMemo(
    () => (check?.claims ?? []).filter((c) => c.selected),
    [check],
  );

  return (
    <main className="mx-auto max-w-5xl px-5 py-10">
      <div className="flex items-center justify-between gap-4">
        <Link href="/try" className="text-sm text-muted hover:text-ink">
          ← New check
        </Link>
        <label className="text-xs text-muted">
          Output language{" "}
          <select
            value={language}
            onChange={(e) => onLanguage(e.target.value as Language)}
            className="ml-1 rounded-[var(--radius)] border border-border bg-surface px-2 py-1 text-ink"
          >
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="mr">मराठी</option>
          </select>
          <span className="ml-2">· remembered this session only</span>
        </label>
      </div>

      <h1 className="mt-4 font-serif text-3xl font-semibold tracking-tight">
        {done ? "Results" : "Checking…"}
      </h1>

      {error && <p className="mt-3 text-sm text-stance-contradicts">{error}</p>}

      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_1.4fr]">
        {/* Live trace */}
        <section>
          <h2 className="mb-3 flex items-center gap-2 font-serif text-lg font-semibold">
            {!done && <Loader2 size={16} className="animate-spin text-accent" />}
            How we checked this
          </h2>
          <TraceTimeline events={events} />
        </section>

        {/* Results */}
        <section className="space-y-5">
          {selectedClaims.length === 0 && !done && (
            <p className="text-sm text-muted">Gathering evidence…</p>
          )}
          {selectedClaims.map((claim) => (
            <ClaimResultCard key={claim.id} claim={claim} check={check!} />
          ))}
        </section>
      </div>

      {/* Graph */}
      <section className="mt-10">
        <h2 className="mb-3 font-serif text-lg font-semibold">Claim &amp; source graph</h2>
        <GraphView data={graph ?? { nodes: [], edges: [] }} />
        <p className="mt-2 text-xs text-muted">
          Rounded nodes are claims; circles are sources. Edge colour + direction shows each
          source&apos;s stance (supports / contradicts / context).
        </p>
      </section>

      <footer className="mt-12 border-t border-border pt-4 text-xs text-muted">
        Elenchus is a research demo. It surfaces evidence; it does not give verdicts. Always read the
        sources.
      </footer>
    </main>
  );
}

function ClaimResultCard({ claim, check }: { claim: Claim; check: CheckState }) {
  const hasResult = claim.status !== null;
  return (
    <article className="rounded-[var(--radius)] border border-border bg-surface p-4 shadow-sm">
      <p className="font-medium text-ink">{claim.text_original}</p>
      <div className="mt-2 flex items-center gap-3">
        {claim.status ? (
          <StatusBadge status={claim.status} />
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted">
            <Loader2 size={13} className="animate-spin" /> checking…
          </span>
        )}
        {claim.confidence !== null && (
          <span className="text-xs text-muted">{confidenceWord(claim.confidence)}</span>
        )}
      </div>

      {claim.summary && <p className="mt-3 text-sm leading-relaxed text-ink">{claim.summary}</p>}

      {hasResult && claim.evidence.length > 0 && (
        <ul className="mt-4 space-y-3 border-t border-border pt-3">
          {claim.evidence.map((ev, i) => {
            const src = check.sources[ev.source_id];
            return (
              <li key={i} className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <StanceChip stance={ev.stance} />
                  {src && (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                    >
                      {src.domain ?? src.title ?? "source"}
                      <ExternalLink size={11} />
                    </a>
                  )}
                </div>
                <blockquote className="mt-1 border-l-2 border-border pl-3 text-muted">
                  “{ev.quote}”
                </blockquote>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}

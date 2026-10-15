"use client";

import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Quote,
  Search,
  Sparkles,
} from "lucide-react";
import type { ProtoEvent } from "@/lib/proto";

function describe(ev: ProtoEvent): { icon: React.ReactNode; text: string; strong?: boolean } | null {
  const p = ev.payload;
  switch (ev.type) {
    case "step_started":
      return { icon: <Sparkles size={15} />, text: `Checking: ${String(p.claim ?? "")}`, strong: true };
    case "query":
      return { icon: <Search size={15} />, text: `Searched “${String(p.query ?? "")}”` };
    case "search_results": {
      const n = Array.isArray(p.hits) ? p.hits.length : 0;
      return { icon: <Search size={15} />, text: `Found ${n} result${n === 1 ? "" : "s"}` };
    }
    case "page_fetched":
      return { icon: <FileText size={15} />, text: `Read ${String(p.title ?? p.url ?? "")}` };
    case "evidence":
      return {
        icon: <Quote size={15} />,
        text: `${String(p.stance ?? "")}: “${String(p.quote ?? "").slice(0, 110)}”`,
      };
    case "status":
      return {
        icon: <CheckCircle2 size={15} />,
        text: `${String(p.status ?? "")} · ${Number(p.evidence_count ?? 0)} evidence item(s)`,
        strong: true,
      };
    case "warning":
    case "error":
      return { icon: <AlertTriangle size={15} />, text: String(p.message ?? ev.type) };
    default:
      return null;
  }
}

export function TraceTimeline({ events }: { events: ProtoEvent[] }) {
  const rows = events.map((ev) => ({ ev, d: describe(ev) })).filter((r) => r.d !== null);
  if (rows.length === 0) {
    return <p className="text-sm text-muted">Waiting for the first step…</p>;
  }
  return (
    <ol className="relative space-y-3 border-l border-border pl-5">
      {rows.map(({ ev, d }) => (
        <li key={ev.seq} className="relative">
          <span className="absolute -left-[26px] flex h-5 w-5 items-center justify-center rounded-full bg-surface text-muted ring-1 ring-border">
            {d!.icon}
          </span>
          <p className={d!.strong ? "text-sm font-medium text-ink" : "text-sm text-muted"}>
            {d!.text}
          </p>
        </li>
      ))}
    </ol>
  );
}

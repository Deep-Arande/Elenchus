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

type Row = { icon: React.ReactNode; text: string; strong?: boolean; tone?: "warn" | "error" };

function describe(ev: ProtoEvent): Row | null {
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
      return { icon: <AlertTriangle size={15} />, text: String(p.message ?? "warning"), tone: "warn" };
    case "error":
      return { icon: <AlertTriangle size={15} />, text: String(p.message ?? "error"), tone: "error" };
    default:
      return null;
  }
}

const TONE_COLOR: Record<"warn" | "error", string> = {
  warn: "var(--status-insufficient)",
  error: "var(--stance-contradicts)",
};

export function TraceTimeline({ events }: { events: ProtoEvent[] }) {
  const rows = events.map((ev) => ({ ev, d: describe(ev) })).filter((r) => r.d !== null);
  if (rows.length === 0) {
    return <p className="text-sm text-muted">Waiting for the first step…</p>;
  }
  return (
    <ol className="relative space-y-3 border-l border-border pl-5">
      {rows.map(({ ev, d }) => {
        const tone = d!.tone;
        const color = tone ? TONE_COLOR[tone] : undefined;
        return (
          <li key={ev.seq} className="relative">
            <span
              className="absolute -left-[26px] flex h-5 w-5 items-center justify-center rounded-full bg-surface ring-1 ring-border"
              style={{ color: color ?? "var(--muted)" }}
            >
              {d!.icon}
            </span>
            <p
              className={d!.strong ? "text-sm font-medium text-ink" : "text-sm text-muted"}
              style={color ? { color } : undefined}
            >
              {d!.text}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

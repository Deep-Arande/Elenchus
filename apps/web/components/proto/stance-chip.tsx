import { Check, Info, X } from "lucide-react";
import type { Stance } from "@/lib/proto";

// Always icon + text label, never colour alone (AGENTS.md section 10.2).
const MAP = {
  supports: { label: "Supports", color: "var(--stance-supports)", Icon: Check },
  contradicts: { label: "Contradicts", color: "var(--stance-contradicts)", Icon: X },
  context: { label: "Context", color: "var(--stance-context)", Icon: Info },
} as const;

export function StanceChip({ stance }: { stance: Stance }) {
  const m = MAP[stance];
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold" style={{ color: m.color }}>
      <m.Icon size={13} />
      {m.label}
    </span>
  );
}

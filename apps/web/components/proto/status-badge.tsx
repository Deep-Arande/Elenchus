import { CheckCircle2, HelpCircle } from "lucide-react";
import type { EvidenceStatus } from "@/lib/proto";

const MAP = {
  EVIDENCE_FOUND: { label: "Evidence found", color: "var(--status-evidence)", Icon: CheckCircle2 },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient evidence",
    color: "var(--status-insufficient)",
    Icon: HelpCircle,
  },
} as const;

export function StatusBadge({ status }: { status: EvidenceStatus }) {
  const m = MAP[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
      style={{ color: m.color, backgroundColor: `color-mix(in srgb, ${m.color} 14%, transparent)` }}
    >
      <m.Icon size={14} />
      {m.label}
    </span>
  );
}

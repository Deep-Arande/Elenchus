"use client";

import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import { Check, Info, Maximize2, X } from "lucide-react";
import type { GraphData } from "@/lib/proto";

cytoscape.use(fcose);

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

const STANCE_LABEL = { supports: "supports", contradicts: "contradicts", context: "context" } as const;

export function GraphView({ data }: { data: GraphData }) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!ref.current || data.nodes.length === 0) return;

    const ink = cssVar("--ink", "#1c1c1e");
    const surface = cssVar("--surface", "#ffffff");
    const accent = cssVar("--accent", "#2f4b8f");
    const evidence = cssVar("--status-evidence", "#1f7a6d");
    const insufficient = cssVar("--status-insufficient", "#b7791f");
    const stance = {
      supports: cssVar("--stance-supports", "#1f7a6d"),
      contradicts: cssVar("--stance-contradicts", "#b23a48"),
      context: cssVar("--stance-context", "#64748b"),
    };

    const cy = cytoscape({
      container: ref.current,
      elements: [
        ...data.nodes.map((n) => ({
          data: {
            id: n.id,
            label: n.label,
            kind: n.type,
            color:
              n.type === "source"
                ? accent
                : n.status === "INSUFFICIENT_EVIDENCE"
                  ? insufficient
                  : evidence,
          },
        })),
        ...data.edges.map((e) => ({
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            color: stance[e.type],
            label: STANCE_LABEL[e.type],
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: ink,
            "font-size": 11,
            "font-weight": 500,
            "text-wrap": "wrap",
            "text-max-width": "150px",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "background-color": "data(color)",
            "border-width": 2,
            "border-color": surface,
            width: 30,
            height: 30,
          },
        },
        {
          // Claims are larger rounded rectangles so they read as the "subjects".
          selector: 'node[kind = "claim"]',
          style: {
            shape: "round-rectangle",
            width: 46,
            height: 46,
            "font-weight": 600,
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 1,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 9,
            color: "data(color)",
            "text-background-color": surface,
            "text-background-opacity": 1,
            "text-background-padding": "2px",
            "text-background-shape": "roundrectangle",
            "text-rotation": "autorotate",
          },
        },
      ],
      layout: {
        name: "fcose",
        animate: true,
        animationDuration: 500,
        padding: 40,
        nodeSeparation: 150,
        idealEdgeLength: 150,
        nodeRepulsion: 9000,
        gravity: 0.2,
        randomize: true,
      } as cytoscape.LayoutOptions,
      minZoom: 0.25,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
    });

    cyRef.current = cy;
    cy.ready(() => cy.fit(undefined, 40));
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data]);

  if (data.nodes.length === 0) {
    return (
      <p className="rounded-[var(--radius)] border border-dashed border-border bg-surface p-6 text-center text-sm text-muted">
        The graph appears once evidence is gathered.
      </p>
    );
  }

  const claimCount = data.nodes.filter((n) => n.type === "claim").length;
  const sourceCount = data.nodes.filter((n) => n.type === "source").length;

  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface">
      {/* Toolbar + counts */}
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="text-xs text-muted">
          {claimCount} claim{claimCount === 1 ? "" : "s"} · {sourceCount} source
          {sourceCount === 1 ? "" : "s"} · {data.edges.length} link
          {data.edges.length === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          onClick={() => cyRef.current?.fit(undefined, 40)}
          className="inline-flex items-center gap-1 rounded-[var(--radius)] border border-border px-2 py-1 text-xs text-muted transition-colors hover:text-ink"
        >
          <Maximize2 size={12} /> Fit
        </button>
      </div>

      {/* Canvas */}
      <div ref={ref} className="h-[420px] w-full overflow-hidden" />

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border px-3 py-2.5 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-[3px] bg-status-evidence" /> Claim (evidence)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-[3px] bg-status-insufficient" /> Claim (insufficient)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full bg-accent" /> Source
        </span>
        <span className="mx-1 h-3 w-px bg-border" />
        <span className="flex items-center gap-1 text-stance-supports">
          <Check size={13} /> supports
        </span>
        <span className="flex items-center gap-1 text-stance-contradicts">
          <X size={13} /> contradicts
        </span>
        <span className="flex items-center gap-1 text-stance-context">
          <Info size={13} /> context
        </span>
      </div>
    </div>
  );
}

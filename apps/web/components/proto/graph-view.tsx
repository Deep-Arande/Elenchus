"use client";

import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import type { GraphData } from "@/lib/proto";

cytoscape.use(fcose);

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export function GraphView({ data }: { data: GraphData }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || data.nodes.length === 0) return;

    const ink = cssVar("--ink", "#1c1c1e");
    const muted = cssVar("--muted", "#6b6b70");
    const border = cssVar("--border", "#e7e3dc");
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
          data: { id: e.id, source: e.source, target: e.target, color: stance[e.type] },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: ink,
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": "120px",
            "text-valign": "bottom",
            "text-margin-y": 4,
            "background-color": "data(color)",
            width: 26,
            height: 26,
          },
        },
        { selector: 'node[kind = "claim"]', style: { shape: "round-rectangle", width: 34, height: 34 } },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
      ],
      layout: { name: "fcose", animate: true, padding: 24, nodeSeparation: 90 } as cytoscape.LayoutOptions,
      minZoom: 0.3,
      maxZoom: 2.5,
    });

    cy.fit(undefined, 30);
    return () => cy.destroy();
  }, [data]);

  if (data.nodes.length === 0) {
    return <p className="text-sm text-muted">The graph appears once evidence is gathered.</p>;
  }

  return (
    <div
      ref={ref}
      className="h-[360px] w-full overflow-hidden rounded-[var(--radius)] border border-border bg-surface"
    />
  );
}

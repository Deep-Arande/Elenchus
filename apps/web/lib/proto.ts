/**
 * Prototype API client (throwaway; talks to the backend /proto endpoints).
 *
 * Session is carried in the `X-Proto-Session` header, read from the create
 * response and persisted in localStorage. Delete this file with the (proto)
 * route group to remove the prototype.
 */

import { API_BASE_URL } from "./api";

export type Language = "en" | "hi" | "mr" | "hi-Latn" | "other";
export type Stance = "supports" | "contradicts" | "context";
export type EvidenceStatus = "EVIDENCE_FOUND" | "INSUFFICIENT_EVIDENCE";
export type CheckStatus = "awaiting_confirmation" | "running" | "done" | "failed";

export interface SourceRef {
  id: string;
  url: string;
  domain: string | null;
  title: string | null;
}

export interface EvidenceItem {
  source_id: string;
  stance: Stance;
  quote: string;
  relevance: number;
  verified: boolean;
}

export interface Claim {
  id: string;
  text_original: string;
  text_en: string | null;
  language: Language;
  claim_type: string;
  checkworthy: boolean;
  entities: string[];
  time_reference: string | null;
  selected: boolean;
  status: EvidenceStatus | null;
  confidence: number | null;
  summary: string | null;
  evidence: EvidenceItem[];
}

export interface CheckState {
  id: string;
  session_id: string;
  input_text: string;
  language: Language;
  status: CheckStatus;
  claims: Claim[];
  sources: Record<string, SourceRef>;
  error: string | null;
  created_at: string;
  mock: boolean;
}

export interface GraphNode {
  id: string;
  type: "claim" | "source";
  label: string;
  status: EvidenceStatus | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: Stance;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ProtoEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  ts: string;
}

const SID_KEY = "proto_sid";

function getSid(): string | null {
  try {
    return localStorage.getItem(SID_KEY);
  } catch {
    return null;
  }
}

function setSid(id: string): void {
  try {
    localStorage.setItem(SID_KEY, id);
  } catch {
    /* ignore */
  }
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const sid = getSid();
  if (sid) h["X-Proto-Session"] = sid;
  return h;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${detail}`.trim());
  }
  return res.json() as Promise<T>;
}

export async function getInfo(): Promise<{ llm_mock: boolean; search_mock: boolean }> {
  return json(await fetch(`${API_BASE_URL}/proto/info`));
}

export async function createCheck(text: string, language?: Language): Promise<CheckState> {
  const res = await fetch(`${API_BASE_URL}/proto/checks`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ text, language }),
  });
  const data = await json<CheckState>(res);
  setSid(data.session_id);
  return data;
}

export async function runCheck(
  id: string,
  claims: { id: string; selected: boolean; text_original?: string }[],
  language?: Language,
): Promise<CheckState> {
  return json(
    await fetch(`${API_BASE_URL}/proto/checks/${id}/run`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ claims, language }),
    }),
  );
}

export async function getCheck(id: string): Promise<CheckState> {
  return json(await fetch(`${API_BASE_URL}/proto/checks/${id}`, { headers: headers() }));
}

export async function getGraph(id: string): Promise<GraphData> {
  return json(await fetch(`${API_BASE_URL}/proto/checks/${id}/graph`, { headers: headers() }));
}

export async function updateSession(prefs: {
  language?: Language;
  strict_sources?: boolean;
}): Promise<void> {
  await fetch(`${API_BASE_URL}/proto/session`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(prefs),
  });
}

/**
 * Subscribe to the live trace via SSE. Returns a cleanup function.
 * Note: EventSource cannot send custom headers; the events endpoint is keyed
 * only by check id, so no session header is needed.
 */
export function streamEvents(
  id: string,
  handlers: {
    onEvent: (ev: ProtoEvent) => void;
    onDone?: () => void;
    onError?: (message: string) => void;
  },
): () => void {
  const es = new EventSource(`${API_BASE_URL}/proto/checks/${id}/events`);
  es.onmessage = (e: MessageEvent<string>) => {
    let ev: ProtoEvent;
    try {
      ev = JSON.parse(e.data) as ProtoEvent;
    } catch {
      return;
    }
    if (ev.type === "done") {
      handlers.onDone?.();
      es.close();
    } else if (ev.type === "error") {
      handlers.onError?.(String(ev.payload.message ?? "error"));
      es.close();
    } else {
      handlers.onEvent(ev);
    }
  };
  es.onerror = () => {
    // The stream closes normally on completion; only surface if still connecting.
    if (es.readyState === EventSource.CONNECTING) {
      handlers.onError?.("Lost connection to the live trace.");
    }
    es.close();
  };
  return () => es.close();
}

/**
 * Server-Sent Events helper (placeholder).
 *
 * Phase 5 implements the live-trace reader with auto-reconnect and replay for
 * `GET /checks/{id}/events` (AGENTS.md section 6.1 "Live events").
 */

export type SseHandler = (event: MessageEvent) => void;

export function openEventStream(url: string, onMessage: SseHandler): EventSource {
  const source = new EventSource(url);
  source.onmessage = onMessage;
  return source;
}

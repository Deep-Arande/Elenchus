"use client";

import { useState } from "react";
import { Loader2, Send } from "lucide-react";
import { askStream, type ConversationTurn } from "@/lib/proto";

type Msg = { role: "user" | "assistant"; text: string };

export function Conversation({ checkId, seed }: { checkId: string; seed: ConversationTurn[] }) {
  const [turns, setTurns] = useState<Msg[]>(seed.map((t) => ({ role: t.role, text: t.text })));
  const [input, setInput] = useState("");
  const [asking, setAsking] = useState(false);

  async function onAsk(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || asking) return;
    setInput("");
    setAsking(true);
    setTurns((prev) => [...prev, { role: "user", text: q }, { role: "assistant", text: "" }]);

    const appendToLast = (fn: (t: string) => string) =>
      setTurns((prev) => {
        const copy = prev.slice();
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { role: "assistant", text: fn(last.text) };
        return copy;
      });

    await askStream(checkId, q, {
      onDelta: (t) => appendToLast((prevText) => prevText + t),
      onDone: () => setAsking(false),
      onError: (m) => {
        appendToLast(() => `(couldn't answer — ${m})`);
        setAsking(false);
      },
    });
  }

  return (
    <section className="mt-10">
      <h2 className="font-serif text-lg font-semibold">Ask about this</h2>
      <p className="mt-1 text-xs text-muted">
        Answers are grounded only in the evidence gathered above — no new searches.
      </p>

      {turns.length > 0 && (
        <div className="mt-4 space-y-3">
          {turns.map((t, i) => (
            <div key={i} className={t.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <div
                className={
                  t.role === "user"
                    ? "max-w-[85%] rounded-[var(--radius)] bg-accent px-3 py-2 text-sm text-white"
                    : "max-w-[85%] rounded-[var(--radius)] border border-border bg-surface px-3 py-2 text-sm leading-relaxed text-ink"
                }
              >
                {t.text ? (
                  t.text
                ) : asking && i === turns.length - 1 ? (
                  <Loader2 size={14} className="animate-spin text-muted" />
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={onAsk} className="mt-4 flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={asking}
          placeholder="e.g. which source contradicts the first claim?"
          className="flex-1 rounded-[var(--radius)] border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={asking || input.trim().length === 0}
          className="inline-flex items-center gap-1.5 rounded-[var(--radius)] bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {asking ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          Ask
        </button>
      </form>
    </section>
  );
}

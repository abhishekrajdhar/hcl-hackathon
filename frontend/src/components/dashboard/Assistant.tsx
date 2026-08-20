"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { IconChat, IconSend, IconSpark } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import { useChat, type ChatMessage } from "@/lib/hooks/useChat";
import { ToolCards } from "@/components/dashboard/chat/ToolCards";

const SUGGESTIONS = [
  "I want to become an NLP engineer",
  "What should I learn next?",
  "Show me my learning path",
  "Why are you recommending PyTorch?",
  "Find courses on transformers",
  "I scored 85% on the deep learning quiz",
];

export function Assistant({
  resolveResourceUrl,
}: {
  /** Optional lookup from the dashboard's recommendation list (title → URL). */
  resolveResourceUrl?: (title: string) => string | null;
}) {
  const {
    messages,
    send,
    retry,
    sending,
    conversations,
    loadingHistory,
    openConversation,
    newConversation,
  } = useChat();
  const [text, setText] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  // Ids of animated messages whose typewriter reveal has finished.
  const [revealed, setRevealed] = useState<Set<string>>(new Set());
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, revealed]);

  const submit = (value?: string) => {
    const v = value ?? text;
    if (!v.trim() || sending) return;
    void send(v);
    setText("");
  };

  const actions = {
    onAsk: (t: string) => submit(t),
    onStart: (title: string) => {
      const url = resolveResourceUrl?.(title);
      if (url) window.open(url, "_blank", "noopener");
      else submit(`Find me courses on ${title}`);
    },
  };

  const showSuggestions = messages.length <= 1;

  return (
    <Card className="flex h-[640px] flex-col">
      <CardHeader
        title="AI Learning Assistant"
        subtitle="Grounded in your real learning data — never invented"
        icon={<IconChat />}
        action={
          <div className="flex items-center gap-1.5">
            {conversations.length > 0 && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setHistoryOpen((o) => !o)}
                  className="rounded-lg border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted hover:text-fg"
                >
                  History
                </button>
                {historyOpen && (
                  <div className="absolute right-0 top-8 z-10 max-h-64 w-64 overflow-y-auto rounded-xl border border-border bg-surface p-1 shadow-card">
                    {conversations.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => {
                          setHistoryOpen(false);
                          void openConversation(c.id);
                        }}
                        className="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-xs text-fg hover:bg-surface-2"
                      >
                        {c.title || "Conversation"}
                        <span className="block text-[10px] text-muted">
                          {new Date(c.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={newConversation}
              className="rounded-lg border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted hover:text-fg"
            >
              New chat
            </button>
            <Badge tone="brand">coach</Badge>
          </div>
        }
      />

      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto px-5 py-3">
        {loadingHistory && (
          <p className="text-center text-xs text-muted">Loading conversation…</p>
        )}
        {messages.map((m) => (
          <MessageRow
            key={m.id}
            message={m}
            done={!m.animate || revealed.has(m.id)}
            onRevealed={() => setRevealed((s) => new Set(s).add(m.id))}
            onRetry={() => void retry(m)}
            actions={actions}
          />
        ))}
        {sending && (
          <div className="flex items-end gap-2">
            <Avatar />
            <div className="rounded-2xl rounded-bl-sm bg-surface-2 px-3.5 py-2.5 text-sm text-muted">
              <span className="inline-flex gap-1">
                <Dot /> <Dot delay={120} /> <Dot delay={240} />
              </span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {showSuggestions && (
        <div className="flex flex-wrap gap-1.5 px-5 pb-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              className="rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted transition-colors hover:border-brand/40 hover:text-fg"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex items-center gap-2 border-t border-border p-3"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='Try "I want to become an NLP engineer"…'
          disabled={sending}
          className="flex-1 rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-brand disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={sending || !text.trim()}
          aria-label="Send message"
          className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <IconSend className="h-4 w-4" />
        </button>
      </form>
    </Card>
  );
}

// ---- message row ------------------------------------------------------------

function MessageRow({
  message: m,
  done,
  onRevealed,
  onRetry,
  actions,
}: {
  message: ChatMessage;
  done: boolean;
  onRevealed: () => void;
  onRetry: () => void;
  actions: { onAsk: (t: string) => void; onStart: (t: string) => void };
}) {
  const isUser = m.role === "user";
  const hasCardData = (m.tools ?? []).some((t) => Object.keys(t.data ?? {}).length > 0);
  return (
    <div className={clsx("flex items-end gap-2", isUser && "flex-row-reverse")}>
      {!isUser && <Avatar error={m.error} />}
      <div className={clsx("max-w-[85%] min-w-0", isUser && "flex flex-col items-end")}>
        <div
          className={clsx(
            "rounded-2xl px-3.5 py-2.5 text-sm",
            isUser
              ? "rounded-br-sm bg-brand text-white"
              : m.error
                ? "rounded-bl-sm border border-danger/30 bg-danger/5 text-fg"
                : "rounded-bl-sm bg-surface-2 text-fg",
          )}
        >
          <p className="whitespace-pre-wrap">
            {!isUser && m.animate && !done ? (
              <Typewriter text={m.content} onDone={onRevealed} />
            ) : (
              m.content
            )}
          </p>
          {m.error && m.retryText && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 rounded-lg bg-danger/10 px-2.5 py-1 text-xs font-medium text-danger hover:bg-danger/20"
            >
              Retry
            </button>
          )}
        </div>

        {/* Structured cards appear once the reply text has fully streamed in. */}
        {!isUser && done && m.tools && hasCardData && (
          <ToolCards tools={m.tools} actions={actions} />
        )}

        {/* Transparency chips: which real tools grounded this reply. */}
        {!isUser && done && !m.error && m.tools && m.tools.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {m.tools.map((t, i) => (
              <span
                key={`${t.name}-${i}`}
                title={t.summary}
                className="rounded bg-fg/5 px-1.5 py-0.5 text-[10px] text-muted"
              >
                {t.name.replaceAll("_", " ")}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Avatar({ error }: { error?: boolean }) {
  return (
    <span
      className={clsx(
        "grid h-7 w-7 shrink-0 place-items-center rounded-full",
        error ? "bg-danger/10 text-danger" : "bg-brand-soft text-brand",
      )}
    >
      <IconSpark className="h-4 w-4" />
    </span>
  );
}

// ---- streaming-like typewriter ---------------------------------------------

const CHARS_PER_SECOND = 220;

function Typewriter({ text, onDone }: { text: string; onDone: () => void }) {
  const [count, setCount] = useState(0);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    setCount(0);
    // Time-based reveal: robust against timer throttling in background tabs.
    const start = performance.now();
    const iv = window.setInterval(() => {
      const elapsed = performance.now() - start;
      const next = Math.min(text.length, Math.floor((elapsed / 1000) * CHARS_PER_SECOND));
      setCount(next);
      if (next >= text.length) {
        window.clearInterval(iv);
        // Defer so we never set parent state during this component's render.
        window.setTimeout(() => doneRef.current(), 120);
      }
    }, 24);
    return () => window.clearInterval(iv);
  }, [text]);

  return (
    <>
      {text.slice(0, count)}
      <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse rounded-sm bg-brand align-middle" />
    </>
  );
}

function Dot({ delay = 0 }: { delay?: number }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}

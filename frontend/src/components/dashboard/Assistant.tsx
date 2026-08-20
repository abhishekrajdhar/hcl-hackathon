"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { IconChat, IconSend } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import { useChat } from "@/lib/hooks/useChat";

const SUGGESTIONS = [
  "What should I learn next?",
  "Why are you recommending PyTorch?",
  "Can I skip statistics?",
  "What should I do this week?",
];

export function Assistant() {
  const { messages, send, sending } = useChat();
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = (value?: string) => {
    const v = value ?? text;
    if (!v.trim()) return;
    void send(v);
    setText("");
  };

  return (
    <Card className="flex h-[560px] flex-col">
      <CardHeader
        title="AI Learning Assistant"
        subtitle="Grounded in your real learning data"
        icon={<IconChat />}
        action={<Badge tone="brand">coach</Badge>}
      />
      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto px-5 py-3">
        {messages.map((m, i) => (
          <div key={i} className={clsx("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div
              className={clsx(
                "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm",
                m.role === "user"
                  ? "rounded-br-sm bg-brand text-white"
                  : "rounded-bl-sm bg-surface-2 text-fg",
              )}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.meta?.tools && m.meta.tools.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {m.meta.tools.map((t) => (
                    <span key={t} className="rounded bg-fg/5 px-1.5 py-0.5 text-[10px] text-muted">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-sm bg-surface-2 px-3.5 py-2 text-sm text-muted">
              <span className="inline-flex gap-1">
                <Dot /> <Dot delay={120} /> <Dot delay={240} />
              </span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-1.5 px-5 pb-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              className="rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted hover:text-fg"
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
          placeholder="Ask your learning coach…"
          className="flex-1 rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <button
          type="submit"
          disabled={sending || !text.trim()}
          className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-white disabled:opacity-40"
        >
          <IconSend className="h-4 w-4" />
        </button>
      </form>
    </Card>
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

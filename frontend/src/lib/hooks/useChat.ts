"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  meta?: { intent?: string; tools?: string[]; source?: string };
}

const WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "Hi! I'm your learning coach. Ask me what to learn next, why something is recommended, or tell me what you finished.",
};

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();

  const send = useCallback(
    async (text: string) => {
      const clean = text.trim();
      if (!clean || sending) return;
      setMessages((m) => [...m, { role: "user", content: clean }]);
      setSending(true);
      try {
        const res: ChatResponse = await api.sendChat(clean, conversationId);
        setConversationId(res.conversation_id);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: res.reply,
            meta: {
              intent: res.intent,
              tools: res.tools_used.map((t) => t.name),
              source: res.source,
            },
          },
        ]);
      } catch (e) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content:
              e instanceof Error && e.message.includes("401")
                ? "Please sign in to chat with your learning coach."
                : "Sorry, I couldn't reach the coach service just now.",
          },
        ]);
      } finally {
        setSending(false);
      }
    },
    [conversationId, sending],
  );

  return { messages, send, sending };
}

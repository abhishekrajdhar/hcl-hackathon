"use client";

// Chat state for the learning assistant. All learner state lives in the
// backend — this hook only holds the visible transcript. Conversation memory
// is keyed by `conversation_id`; the authenticated user comes from the bearer
// token attached by the API client.

import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi, getToken, ApiError } from "@/lib/api";
import type { ConversationRead, ToolInvocation } from "@/lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Structured tool results — rendered as cards, not plain text. */
  tools?: ToolInvocation[];
  intent?: string;
  source?: string;
  /** This turn failed; `retryText` holds the user text to resend. */
  error?: boolean;
  retryText?: string;
  /** Reveal with the streaming-like typewriter effect. */
  animate?: boolean;
}

const WELCOME: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm your learning coach. Tell me a goal (try \"I want to become an NLP engineer\"), ask what to learn next, or report what you finished — I'll adapt your path.",
};

let counter = 0;
function uid(): string {
  counter += 1;
  return `m-${Date.now().toString(36)}-${counter}`;
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return "Please sign in to chat with your learning coach.";
    if (e.status === 429) return "The coach is a bit busy — give it a few seconds and retry.";
    return `The coach service returned an error (${e.status}). ${e.message}`;
  }
  return "I couldn't reach the coach service. Check your connection and retry.";
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [conversations, setConversations] = useState<ConversationRead[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const sendingRef = useRef(false);

  const refreshConversations = useCallback(async () => {
    if (!getToken()) return;
    try {
      setConversations(await chatApi.listConversations());
    } catch {
      // History is a convenience — never block the chat on it.
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  /** POST the text; append the assistant reply (or an error bubble). */
  const deliver = useCallback(
    async (clean: string) => {
      setSending(true);
      sendingRef.current = true;
      try {
        const res = await chatApi.sendChat(clean, conversationId);
        setConversationId(res.conversation_id);
        setMessages((m) => [
          ...m,
          {
            id: uid(),
            role: "assistant",
            content: res.reply,
            tools: res.tools_used,
            intent: res.intent,
            source: res.source,
            animate: true,
          },
        ]);
        if (!conversationId) void refreshConversations();
      } catch (e) {
        setMessages((m) => [
          ...m,
          { id: uid(), role: "assistant", content: errorText(e), error: true, retryText: clean },
        ]);
      } finally {
        setSending(false);
        sendingRef.current = false;
      }
    },
    [conversationId, refreshConversations],
  );

  const send = useCallback(
    async (text: string) => {
      const clean = text.trim();
      if (!clean || sendingRef.current) return;
      setMessages((m) => [...m, { id: uid(), role: "user", content: clean }]);
      await deliver(clean);
    },
    [deliver],
  );

  /** Re-send the user text behind a failed turn, replacing the error bubble. */
  const retry = useCallback(
    async (failed: ChatMessage) => {
      if (!failed.retryText || sendingRef.current) return;
      setMessages((m) => m.filter((x) => x.id !== failed.id));
      await deliver(failed.retryText);
    },
    [deliver],
  );

  /** Load a past conversation (dialogue only — backend stores the transcript). */
  const openConversation = useCallback(async (id: string) => {
    setLoadingHistory(true);
    try {
      const detail = await chatApi.getConversation(id);
      setConversationId(detail.id);
      setMessages([
        WELCOME,
        ...detail.messages.map((m): ChatMessage => {
          const meta = m.meta ?? {};
          const tools = Array.isArray(meta.tools) ? (meta.tools as string[]) : [];
          return {
            id: m.id,
            role: m.role === "user" ? "user" : "assistant",
            content: m.content,
            intent: typeof meta.intent === "string" ? meta.intent : undefined,
            source: typeof meta.source === "string" ? meta.source : undefined,
            // History stores tool names only (no data) — surface them as chips.
            tools: tools.map((name) => ({ name, available: true, summary: "", data: {} })),
          };
        }),
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { id: uid(), role: "assistant", content: "I couldn't load that conversation.", error: true },
      ]);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const newConversation = useCallback(() => {
    setConversationId(undefined);
    setMessages([WELCOME]);
  }, []);

  return {
    messages,
    send,
    retry,
    sending,
    conversationId,
    conversations,
    loadingHistory,
    openConversation,
    newConversation,
  };
}

// Conversational assistant endpoints. The backend maintains all learner state
// and conversation memory — the frontend only sends the message text plus the
// conversation id, and the authenticated user is derived from the bearer token.
import type {
  ChatResponse,
  ConversationDetail,
  ConversationRead,
  UUID,
} from "@/lib/types";
import { request } from "./client";

export function sendChat(message: string, conversationId?: UUID): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: { message, conversation_id: conversationId },
  });
}

export function listConversations(limit = 20): Promise<ConversationRead[]> {
  return request<ConversationRead[]>("/chat/conversations", { query: { limit } });
}

export function getConversation(conversationId: UUID): Promise<ConversationDetail> {
  return request<ConversationDetail>(`/chat/conversations/${conversationId}`);
}

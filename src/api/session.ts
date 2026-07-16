import { api } from './client';
import { toProducts } from './products';
import { ChatTurnResponse, Product, SessionState } from '../types';

export interface SessionMessageResult {
  sessionId: string;
  reply: string;
  sessionState: SessionState;
  filters: { category?: string; style: string; styles?: string[]; occasion: string; budget: string; color?: string; size?: string; age?: string };
  products: Product[];
  total: number;
  turnType: 'fast_path' | 'llm_extraction';
}

async function toResult(response: ChatTurnResponse): Promise<SessionMessageResult> {
  return {
    sessionId: response.session_id,
    reply: response.reply,
    sessionState: response.session_state,
    filters: response.filters,
    products: await toProducts(response.products.items),
    total: response.products.total,
    turnType: response.turn_type,
  };
}

export async function sendSessionMessage(
  sessionId: string | null,
  query: string,
  department?: 'men' | 'women',
  sessionState?: SessionState | null
): Promise<SessionMessageResult> {
  const response = await api.post<ChatTurnResponse>('/session/message', {
    session_id: sessionId,
    query,
    department: department ?? null,
    session_state: sessionState ?? null,
  });
  return toResult(response);
}

export async function resetSession(sessionId: string): Promise<SessionMessageResult> {
  const response = await api.post<ChatTurnResponse>('/session/reset', { session_id: sessionId });
  return toResult(response);
}

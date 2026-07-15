export interface ShoppingIntent {
  category: string | null;
  color: string | null;
  size: string | null;
  priceMax: number | null;
  priceMin: number | null;
  descriptive: string | null;
  occasion: string | null;
}

export interface ProductResult {
  id: string;
  title: string;
  price: number;
  currency: string;
  imageUrl: string;
  productUrl: string;
  score: number;
  reason: string;
}

export interface SearchResult {
  intent: ShoppingIntent;
  products: ProductResult[];
  notice: string | null;
  meta: {
    storeDomain: string;
    fetchedCount: number;
    catalogCapped: boolean;
    relaxed: boolean;
    relaxedFilters: string[];
    durationMs: number;
  };
}

export type ErrorCode =
  | 'UNSUPPORTED_PAGE'
  | 'UNSUPPORTED_STORE'
  | 'MIC_PERMISSION_DENIED'
  | 'EMPTY_AUDIO'
  | 'AUDIO_TOO_LARGE'
  | 'TRANSCRIPTION_FAILED'
  | 'EMPTY_INTENT'
  | 'CATALOG_UNAVAILABLE'
  | 'CATALOG_TIMEOUT'
  | 'RATE_LIMITED'
  | 'PROVIDER_UNAVAILABLE'
  | 'NO_MATCHES'
  | 'REQUEST_CANCELLED'
  | 'INTERNAL_ERROR';

export interface ExtensionError {
  code: ErrorCode;
  message: string;
  retriable: boolean;
}

export type WorkerRequest =
  | { type: 'GET_ACTIVE_STORE' }
  | { type: 'SEARCH_PRODUCTS'; requestId: string; query: string; previousIntent?: ShoppingIntent | null }
  | { type: 'CANCEL_SEARCH'; requestId: string }
  | { type: 'OPEN_PRODUCT'; productUrl: string };

export type WorkerResponse =
  | { ok: true; data: SearchResult }
  | { ok: true; store: { name: string; domain: string } }
  | { ok: true; cancelled: true }
  | { ok: true; opened: true }
  | { ok: false; error: ExtensionError };

export interface SessionSnapshot {
  requestId: string;
  query: string;
  stage: 'searching' | 'results' | 'error';
  result?: SearchResult;
  error?: ExtensionError;
  updatedAt: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

export interface ConversationState {
  messages: ChatMessage[];
  currentResult: SearchResult | null;
  lastQuery: string;
  updatedAt: number;
}

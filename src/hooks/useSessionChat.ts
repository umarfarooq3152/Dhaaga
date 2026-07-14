import { useCallback, useEffect, useRef, useState } from 'react';
import { resetSession as resetSessionApi, sendSessionMessage } from '../api/session';
import { FilterChips, Message, Product } from '../types';

const DEFAULT_FILTERS: FilterChips = {
  style: 'All Styles',
  occasion: 'All Occasions',
  budget: 'All Budgets',
};

function nowStr(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

let messageIdCounter = 0;
function nextMessageId(prefix: string): string {
  // Date.now() alone can collide when two messages are created in the same
  // millisecond (e.g. React StrictMode's double-invoked effects in dev) —
  // a monotonic counter guarantees uniqueness regardless of timing.
  messageIdCounter += 1;
  return `${prefix}-${Date.now()}-${messageIdCounter}`;
}

/** DiscoveryScreen's quick-filter chips route into this same chat pipeline
 * (matching the existing screen-transition flow) by composing a natural
 * language message from the selected filters. */
function composeInitialQuery(
  query?: string,
  filters?: { style?: string; occasion?: string; budget?: string }
): string {
  if (query && query.trim()) return query;

  const parts: string[] = [];
  if (filters?.style) parts.push(filters.style);
  if (filters?.occasion) parts.push(`for ${filters.occasion}`);
  if (filters?.budget) parts.push(filters.budget);
  return parts.length > 0 ? `Show me ${parts.join(', ')}` : '';
}

interface UseSessionChatResult {
  messages: Message[];
  filteredProducts: Product[];
  filters: FilterChips;
  isChatLoading: boolean;
  isProductsLoading: boolean;
  sendMessage: (text: string) => void;
  resetSession: () => void;
}

export function useSessionChat(
  userName: string,
  department?: 'men' | 'women',
  initialQuery?: string,
  initialFilters?: { style?: string; occasion?: string; budget?: string }
): UseSessionChatResult {
  const sessionIdRef = useRef<string | null>(null);
  const hasTriggeredInitialRef = useRef(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [filteredProducts, setFilteredProducts] = useState<Product[]>([]);
  const [filters, setFilters] = useState<FilterChips>(DEFAULT_FILTERS);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isProductsLoading, setIsProductsLoading] = useState(false);

  const sendMessage = useCallback((text: string) => {
    if (!text.trim()) return;

    const userMessage: Message = {
      id: nextMessageId('user'),
      sender: 'user',
      text,
      timestamp: nowStr(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsChatLoading(true);
    setIsProductsLoading(true);

    sendSessionMessage(sessionIdRef.current, text, department)
      .then((result) => {
        sessionIdRef.current = result.sessionId;
        setFilters(result.filters);
        setFilteredProducts(result.products);
        setMessages((prev) => [
          ...prev,
          {
            id: nextMessageId('assistant'),
            sender: 'assistant',
            text: result.reply,
            timestamp: nowStr(),
          },
        ]);
      })
      .catch((error) => {
        console.error('Chat message failed:', error);
        setMessages((prev) => [
          ...prev,
          {
            id: nextMessageId('error'),
            sender: 'assistant',
            text: "Sorry, I'm having trouble reaching the catalog right now — please try again in a moment.",
            timestamp: nowStr(),
          },
        ]);
      })
      .finally(() => {
        setIsChatLoading(false);
        setIsProductsLoading(false);
      });
  }, [department]);

  const resetSession = useCallback(() => {
    const welcomeMessage: Message = {
      id: 'welcome',
      sender: 'assistant',
      text: `Assalam-o-Alaikum ${userName}. I am Dhaaga's AI Assistant. Tell me what celebratory moment you are dressing for, your preferred fabric, or a specific price range.`,
      timestamp: nowStr(),
    };

    if (!sessionIdRef.current) {
      // Nothing has been sent to the backend yet — just reset local UI state.
      setMessages([welcomeMessage]);
      setFilteredProducts([]);
      setFilters(DEFAULT_FILTERS);
      return;
    }

    setIsChatLoading(true);
    resetSessionApi(sessionIdRef.current)
      .then((result) => {
        setFilters(result.filters);
        setFilteredProducts(result.products);
        setMessages([{ ...welcomeMessage, text: result.reply }]);
      })
      .catch((error) => {
        console.error('Failed to reset session:', error);
      })
      .finally(() => {
        setIsChatLoading(false);
      });
  }, [userName]);

  useEffect(() => {
    // Guards against React StrictMode double-invoking this effect in dev,
    // which would otherwise submit the initial query twice.
    if (hasTriggeredInitialRef.current) return;
    hasTriggeredInitialRef.current = true;

    const initial = composeInitialQuery(initialQuery, initialFilters);
    if (initial) {
      sendMessage(initial);
    } else {
      setMessages([
        {
          id: 'welcome',
          sender: 'assistant',
          text: `Assalam-o-Alaikum ${userName}. I am Dhaaga's AI Assistant. Tell me what celebratory moment you are dressing for, your preferred fabric, or a specific price range.`,
          timestamp: nowStr(),
        },
      ]);
    }
    // Only run once on mount — this mirrors the initial-trigger effect the
    // component previously had.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { messages, filteredProducts, filters, isChatLoading, isProductsLoading, sendMessage, resetSession };
}

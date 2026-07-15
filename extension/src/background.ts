import { API_BASE_URL, SEARCH_TIMEOUT_MS, SESSION_KEY } from './config';
import type { SearchResult, SessionSnapshot, ShoppingIntent, WorkerRequest, WorkerResponse } from './shared/contracts';
import { createError, getSupportedStore, isSafeProductUrl, normalizeBackendError } from './shared/validators';

const activeRequests = new Map<string, AbortController>();

async function activeTab(): Promise<chrome.tabs.Tab> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) throw createError('UNSUPPORTED_PAGE', 'No active browser tab was found.');
  return tab;
}

async function saveSnapshot(snapshot: SessionSnapshot): Promise<void> {
  await chrome.storage.session.set({ [SESSION_KEY]: snapshot });
}

async function searchProducts(
  requestId: string,
  query: string,
  previousIntent?: ShoppingIntent | null,
): Promise<WorkerResponse> {
  const trimmed = query.trim();
  if (!trimmed) {
    return { ok: false, error: createError('EMPTY_INTENT', 'Describe what you want to find first.') };
  }

  try {
    const store = getSupportedStore((await activeTab()).url);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort('timeout'), SEARCH_TIMEOUT_MS);
    activeRequests.set(requestId, controller);
    await saveSnapshot({ requestId, query: trimmed, stage: 'searching', updatedAt: Date.now() });

    try {
      const response = await fetch(`${API_BASE_URL}/extension/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: trimmed,
          storeOrigin: store.origin,
          previousIntent: previousIntent || null,
        }),
        signal: controller.signal,
      });
      const payload: unknown = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = normalizeBackendError(response.status, payload);
        await saveSnapshot({ requestId, query: trimmed, stage: 'error', error, updatedAt: Date.now() });
        return { ok: false, error };
      }
      const result = payload as SearchResult;
      await saveSnapshot({ requestId, query: trimmed, stage: 'results', result, updatedAt: Date.now() });
      return { ok: true, data: result };
    } catch (error) {
      const cancelled = controller.signal.aborted;
      const extensionError = cancelled
        ? createError(controller.signal.reason === 'timeout' ? 'CATALOG_TIMEOUT' : 'REQUEST_CANCELLED', controller.signal.reason === 'timeout' ? 'The search took too long. Please try again.' : 'Search cancelled.', controller.signal.reason === 'timeout')
        : createError(
          'PROVIDER_UNAVAILABLE',
          API_BASE_URL.includes('localhost')
            ? 'The local Dhaaga service is not running. Start the backend on port 8000, then retry.'
            : 'Dhaaga could not reach the matching service. Check your connection, then retry.',
          true,
        );
      await saveSnapshot({ requestId, query: trimmed, stage: 'error', error: extensionError, updatedAt: Date.now() });
      return { ok: false, error: extensionError };
    } finally {
      clearTimeout(timeout);
      activeRequests.delete(requestId);
    }
  } catch (error) {
    const extensionError = error && typeof error === 'object' && 'code' in error
      ? error as ReturnType<typeof createError>
      : createError('INTERNAL_ERROR', 'The active store could not be checked.');
    return { ok: false, error: extensionError };
  }
}

async function handleMessage(message: WorkerRequest): Promise<WorkerResponse> {
  if (message.type === 'GET_ACTIVE_STORE') {
    try {
      const store = getSupportedStore((await activeTab()).url);
      return { ok: true, store: { name: store.name, domain: store.domain } };
    } catch (error) {
      return { ok: false, error: error as ReturnType<typeof createError> };
    }
  }
  if (message.type === 'SEARCH_PRODUCTS') {
    return searchProducts(message.requestId, message.query, message.previousIntent);
  }
  if (message.type === 'CANCEL_SEARCH') {
    activeRequests.get(message.requestId)?.abort('cancelled');
    return { ok: true, cancelled: true };
  }
  if (message.type === 'OPEN_PRODUCT') {
    if (!isSafeProductUrl(message.productUrl)) {
      return { ok: false, error: createError('INTERNAL_ERROR', 'That product link was not safe to open.') };
    }
    await chrome.tabs.create({ url: message.productUrl });
    return { ok: true, opened: true };
  }
  return { ok: false, error: createError('INTERNAL_ERROR', 'Unknown extension message.') };
}

chrome.runtime.onMessage.addListener((message: WorkerRequest, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) {
    sendResponse({ ok: false, error: createError('INTERNAL_ERROR', 'Untrusted message sender.') });
    return false;
  }
  void handleMessage(message).then(sendResponse);
  return true;
});

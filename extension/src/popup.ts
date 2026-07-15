import {
  API_BASE_URL,
  CONVERSATION_KEY,
  LAYOUT_KEY,
  MAX_AUDIO_BYTES,
  SESSION_KEY,
  TRANSCRIPTION_TIMEOUT_MS,
} from './config';
import type {
  ChatMessage,
  ConversationState,
  ExtensionError,
  SearchResult,
  SessionSnapshot,
  ShoppingIntent,
  WorkerRequest,
  WorkerResponse,
} from './shared/contracts';
import { createError, normalizeBackendError } from './shared/validators';
import { renderProductCard } from './ui/product-card';
import { VoiceRecorder } from './voice';

function mustElement<T extends HTMLElement = HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing popup element: ${id}`);
  return element as T;
}

const workspaceView = mustElement('workspace-view');
const blockingView = mustElement('blocking-view');
const blockingTitle = mustElement('blocking-title');
const blockingMessage = mustElement('blocking-message');
const storeContext = mustElement('store-context');
const storeName = mustElement('store-name');
const productList = mustElement('product-list');
const productsPane = mustElement('products-pane');
const productFeedControls = mustElement('product-feed-controls');
const productFeedStatus = mustElement('product-feed-status');
const loadMoreButton = mustElement<HTMLButtonElement>('load-more-products');
const loadMoreLabel = mustElement('load-more-label');
const productScrollSentinel = mustElement('product-scroll-sentinel');
const productsEmpty = mustElement('products-empty');
const productsLoading = mustElement('products-loading');
const noMatches = mustElement('no-matches');
const intentChips = mustElement('intent-chips');
const resultSummary = mustElement('result-summary');
const notice = mustElement('notice');
const chatThread = mustElement('chat-thread');
const chatForm = mustElement<HTMLFormElement>('chat-form');
const chatInput = mustElement<HTMLTextAreaElement>('chat-input');
const inputError = mustElement('input-error');
const sendButton = mustElement<HTMLButtonElement>('send-button');
const micButton = mustElement<HTMLButtonElement>('mic-button');
const inlineError = mustElement('inline-error');
const inlineErrorTitle = mustElement('inline-error-title');
const inlineErrorMessage = mustElement('inline-error-message');
const retryButton = mustElement<HTMLButtonElement>('retry-button');
const searchingStrip = mustElement('searching-strip');
const searchingLabel = mustElement('searching-label');
const recordingStrip = mustElement('recording-strip');
const recordingTime = mustElement('recording-time');
const layoutToggle = mustElement<HTMLButtonElement>('layout-toggle');
const checkStoreButton = mustElement<HTMLButtonElement>('check-store');

const welcomeMessage: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: 'Tell me what you want from this store. After the first search, keep refining with messages like “cheaper,” “blue instead,” or “more relaxed.”',
};

let messages: ChatMessage[] = [welcomeMessage];
let currentResult: SearchResult | null = null;
let currentRequestId: string | null = null;
let lastQuery = '';
let lastError: ExtensionError | null = null;
let recordingStartedAt = 0;
let recordingTimer: number | null = null;
let visibleProductCount = 0;
let loadingMoreProducts = false;
let productPaneHasScrolled = false;

const PRODUCT_BATCH_SIZE = 8;

async function sendMessage(message: WorkerRequest): Promise<WorkerResponse> {
  return chrome.runtime.sendMessage(message) as Promise<WorkerResponse>;
}

function message(role: ChatMessage['role'], text: string): ChatMessage {
  return { id: crypto.randomUUID(), role, text };
}

function setInputError(text: string | null): void {
  inputError.hidden = !text;
  inputError.textContent = text || '';
}

function renderChat(isTyping = false): void {
  chatThread.replaceChildren();
  for (const item of messages) {
    const bubble = document.createElement('div');
    bubble.className = `message ${item.role}`;
    const label = document.createElement('span');
    label.className = 'message-label';
    label.textContent = item.role === 'assistant' ? 'Dhaaga' : 'You';
    const text = document.createElement('span');
    text.textContent = item.text;
    bubble.append(label, text);
    chatThread.append(bubble);
  }
  if (isTyping) {
    const bubble = document.createElement('div');
    bubble.className = 'message assistant';
    const label = document.createElement('span');
    label.className = 'message-label';
    label.textContent = 'Dhaaga';
    const typing = document.createElement('span');
    typing.className = 'typing-message';
    typing.setAttribute('aria-label', 'Dhaaga is refining products');
    typing.append(document.createElement('span'), document.createElement('span'), document.createElement('span'));
    bubble.append(label, typing);
    chatThread.append(bubble);
  }
  chatThread.scrollTop = chatThread.scrollHeight;
}

function intentLabels(intent: ShoppingIntent): string[] {
  const labels: string[] = [];
  if (intent.category) labels.push(intent.category);
  if (intent.occasion) labels.push(intent.occasion);
  if (intent.audience) labels.push(intent.audience === 'women' ? "Women's" : "Men's");
  if (intent.wantsKids) {
    labels.push(intent.childAgeMonths !== null
      ? `Age ${Math.floor(intent.childAgeMonths / 12)}`
      : "Kids'");
  }
  if (intent.color) labels.push(intent.color);
  if (intent.size) labels.push(`Size ${intent.size.toUpperCase()}`);
  if (intent.priceMin !== null && intent.priceMax !== null) {
    labels.push(`Rs. ${intent.priceMin.toLocaleString()}–${intent.priceMax.toLocaleString()}`);
  } else if (intent.priceMax !== null) labels.push(`Under Rs. ${intent.priceMax.toLocaleString()}`);
  else if (intent.priceMin !== null) labels.push(`From Rs. ${intent.priceMin.toLocaleString()}`);
  if (intent.descriptive) labels.push(intent.descriptive);
  return labels;
}

function updateProductFeedControls(): void {
  const total = currentResult?.products.length || 0;
  const hasMore = visibleProductCount < total;
  productFeedControls.hidden = total === 0;
  loadMoreButton.hidden = !hasMore;
  loadMoreButton.disabled = loadingMoreProducts;
  loadMoreButton.classList.toggle('is-loading', loadingMoreProducts);
  loadMoreLabel.textContent = loadingMoreProducts
    ? 'Loading products…'
    : `Load ${Math.min(PRODUCT_BATCH_SIZE, total - visibleProductCount)} more`;
  productFeedStatus.textContent = hasMore
    ? `Showing ${visibleProductCount} of ${total} matches.`
    : total > 0 ? `All ${total} matches loaded.` : '';
  if (currentResult) {
    const progress = hasMore ? `Showing ${visibleProductCount} of ${total} picks` : `${total} picks`;
    resultSummary.textContent = `${progress} · ${currentResult.meta.durationMs.toLocaleString()} ms`;
  }
}

function appendNextProductBatch(immediate = false): void {
  if (!currentResult || loadingMoreProducts || visibleProductCount >= currentResult.products.length) return;
  loadingMoreProducts = true;
  updateProductFeedControls();
  const append = () => {
    if (!currentResult) return;
    const start = visibleProductCount;
    const end = Math.min(start + PRODUCT_BATCH_SIZE, currentResult.products.length);
    for (let index = start; index < end; index += 1) {
      productList.append(renderProductCard(currentResult.products[index], index, sendMessage));
    }
    visibleProductCount = end;
    loadingMoreProducts = false;
    updateProductFeedControls();
  };
  if (immediate) append();
  else window.requestAnimationFrame(append);
}

function renderResults(result: SearchResult | null): void {
  currentResult = result;
  visibleProductCount = 0;
  loadingMoreProducts = false;
  productPaneHasScrolled = false;
  productsPane.scrollTop = 0;
  productList.replaceChildren();
  intentChips.replaceChildren();
  notice.hidden = true;
  productsLoading.hidden = true;

  if (!result) {
    productList.hidden = true;
    productsEmpty.hidden = false;
    noMatches.hidden = true;
    resultSummary.textContent = 'Start with a request in the chat.';
    productFeedControls.hidden = true;
    productFeedStatus.textContent = '';
    chatInput.placeholder = 'Describe what you want…';
    return;
  }

  productsEmpty.hidden = true;
  for (const labelText of intentLabels(result.intent)) {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = labelText;
    intentChips.append(chip);
  }
  notice.hidden = !result.notice;
  notice.textContent = result.notice || '';
  appendNextProductBatch(true);
  noMatches.hidden = result.products.length > 0;
  productList.hidden = result.products.length === 0;
  chatInput.placeholder = 'Refine these results…';
}

function assistantResultSummary(result: SearchResult): string {
  if (result.products.length === 0) {
    const understood = result.intent.category ? ` for ${result.intent.category}` : '';
    return `I understood the request${understood}, but couldn’t find an exact match for that combination in Outfitters. Tell me which detail you want to change and I’ll keep digging.`;
  }
  const count = result.products.length;
  const relaxed = result.meta.relaxed
    ? ' I had to loosen one or more filters; the notice above explains which ones.'
    : '';
  return `I found ${count} ${count === 1 ? 'match' : 'matches'} in the current store.${relaxed} What would you like to refine next?`;
}

function persistConversation(): void {
  const state: ConversationState = {
    messages,
    currentResult,
    lastQuery,
    updatedAt: Date.now(),
  };
  void chrome.storage.local.set({ [CONVERSATION_KEY]: state });
}

function setSearching(searching: boolean): void {
  if (searching) searchingLabel.textContent = 'Refining products…';
  searchingStrip.hidden = !searching;
  sendButton.disabled = searching;
  micButton.disabled = searching;
  chatInput.disabled = searching;
  productsLoading.hidden = !searching || currentResult !== null;
  productList.setAttribute('aria-busy', String(searching));
  renderChat(searching);
}

function hideInlineError(): void {
  inlineError.hidden = true;
  lastError = null;
}

function showInlineError(error: ExtensionError): void {
  lastError = error;
  inlineErrorTitle.textContent = error.code === 'RATE_LIMITED' ? 'Dhaaga is busy' : 'Search interrupted';
  inlineErrorMessage.textContent = error.message;
  retryButton.hidden = !error.retriable;
  inlineError.hidden = false;
}

function showBlockingError(error: ExtensionError): void {
  workspaceView.hidden = true;
  blockingView.hidden = false;
  blockingTitle.textContent = 'Open a supported store';
  blockingMessage.textContent = error.message;
  blockingTitle.focus();
}

async function beginSearch(query: string, addUserMessage = true): Promise<void> {
  const trimmed = query.trim();
  if (!trimmed) {
    setInputError('Describe a product, style, color, size, budget, occasion, or vibe.');
    chatInput.focus();
    return;
  }

  hideInlineError();
  setInputError(null);
  lastQuery = trimmed;
  if (addUserMessage) messages.push(message('user', trimmed));
  chatInput.value = '';
  persistConversation();

  const requestId = crypto.randomUUID();
  currentRequestId = requestId;
  setSearching(true);
  let response: WorkerResponse;
  try {
    response = await sendMessage({
      type: 'SEARCH_PRODUCTS',
      requestId,
      query: trimmed,
      previousIntent: currentResult?.intent || null,
    });
  } catch {
    response = {
      ok: false,
      error: createError(
        'PROVIDER_UNAVAILABLE',
        'Dhaaga could not reach the extension service. Reload the extension and try again.',
        true,
      ),
    };
  }
  if (currentRequestId !== requestId) return;
  currentRequestId = null;
  setSearching(false);

  if (!response.ok) {
    if (response.error.code !== 'REQUEST_CANCELLED') {
      showInlineError(response.error);
      messages.push(message('assistant', `${response.error.message} Your previous products are still here, so you can retry or change the request.`));
      renderChat();
      persistConversation();
    }
    return;
  }
  if (!('data' in response)) return;
  renderResults(response.data);
  messages.push(message('assistant', assistantResultSummary(response.data)));
  renderChat();
  persistConversation();
  mustElement('products-title').focus();
}

async function cancelSearch(): Promise<void> {
  const requestId = currentRequestId;
  currentRequestId = null;
  if (requestId) await sendMessage({ type: 'CANCEL_SEARCH', requestId });
  setSearching(false);
}

function resetConversation(): void {
  void cancelSearch();
  hideInlineError();
  messages = [welcomeMessage];
  currentResult = null;
  lastQuery = '';
  renderResults(null);
  renderChat();
  void chrome.storage.local.remove(CONVERSATION_KEY);
  void chrome.storage.session.remove(SESSION_KEY);
  chatInput.focus();
}

function extensionForMime(mime: string): string {
  if (mime.includes('ogg')) return 'ogg';
  if (mime.includes('mp4') || mime.includes('m4a')) return 'm4a';
  if (mime.includes('mpeg')) return 'mp3';
  if (mime.includes('wav')) return 'wav';
  return 'webm';
}

async function transcribe(blob: Blob, mimeType: string): Promise<string> {
  if (!blob.size) throw createError('EMPTY_AUDIO', 'No audio was recorded. Please try again or type your request.');
  if (blob.size > MAX_AUDIO_BYTES) throw createError('AUDIO_TOO_LARGE', 'That recording is too long. Please keep it under 30 seconds.');
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), TRANSCRIPTION_TIMEOUT_MS);
  try {
    const form = new FormData();
    form.append('file', blob, `voice-request.${extensionForMime(mimeType)}`);
    const response = await fetch(`${API_BASE_URL}/voice/transcribe`, { method: 'POST', body: form, signal: controller.signal });
    const payload: unknown = await response.json().catch(() => ({}));
    if (!response.ok) throw normalizeBackendError(response.status, payload);
    const text = payload && typeof payload === 'object' && 'text' in payload
      ? String((payload as { text: unknown }).text).trim()
      : '';
    if (!text) throw createError('TRANSCRIPTION_FAILED', "We couldn't understand that recording. Please try again or type instead.");
    return text;
  } catch (error) {
    if (error && typeof error === 'object' && 'code' in error) throw error;
    throw createError('TRANSCRIPTION_FAILED', "We couldn't understand that recording. Please try again or type instead.", true);
  } finally {
    window.clearTimeout(timeout);
  }
}

function stopRecordingClock(): void {
  if (recordingTimer !== null) window.clearInterval(recordingTimer);
  recordingTimer = null;
}

function finishRecordingUI(): void {
  stopRecordingClock();
  recordingStrip.hidden = true;
  micButton.setAttribute('aria-pressed', 'false');
  micButton.setAttribute('aria-label', 'Start voice request');
}

const recorder = new VoiceRecorder(async (blob, mimeType) => {
  finishRecordingUI();
  searchingStrip.hidden = false;
  searchingLabel.textContent = 'Transcribing voice…';
  try {
    const transcript = await transcribe(blob, mimeType);
    await beginSearch(transcript);
  } catch (error) {
    searchingStrip.hidden = true;
    showInlineError(error as ExtensionError);
  }
});

async function startRecording(): Promise<void> {
  hideInlineError();
  const permissionState = await microphonePermissionState();
  if (permissionState !== 'granted') {
    await openMicrophoneSetup();
    setInputError('Finish microphone setup in the new tab, then reopen Dhaaga and tap the mic again.');
    return;
  }
  try {
    await recorder.start();
    recordingStrip.hidden = false;
    micButton.setAttribute('aria-pressed', 'true');
    micButton.setAttribute('aria-label', 'Stop recording');
    recordingStartedAt = Date.now();
    const update = () => {
      const seconds = Math.floor((Date.now() - recordingStartedAt) / 1000);
      recordingTime.textContent = `0:${String(seconds).padStart(2, '0')}`;
    };
    update();
    recordingTimer = window.setInterval(update, 250);
  } catch (error) {
    const errorName = error instanceof DOMException ? error.name : '';
    if (errorName === 'NotAllowedError' || errorName === 'SecurityError') {
      await openMicrophoneSetup();
      setInputError('Microphone access needs attention in the setup tab that just opened.');
      return;
    }
    const message = errorName === 'NotFoundError'
      ? 'No microphone was found. Connect or enable one in your system settings, then try again.'
      : 'Dhaaga could not start the microphone. Check your browser and system microphone settings.';
    showInlineError(createError('MIC_PERMISSION_DENIED', message));
  }
}

async function microphonePermissionState(): Promise<PermissionState | 'unknown'> {
  if (!navigator.mediaDevices?.getUserMedia) return 'unknown';
  try {
    return (await navigator.permissions.query({ name: 'microphone' as PermissionName })).state;
  } catch {
    return 'unknown';
  }
}

async function openMicrophoneSetup(): Promise<void> {
  await chrome.tabs.create({ url: chrome.runtime.getURL('microphone.html') });
}

function cancelRecording(): void {
  recorder.cancel();
  finishRecordingUI();
}

function setExpanded(expanded: boolean): void {
  document.body.classList.toggle('is-expanded', expanded);
  document.documentElement.classList.toggle('is-expanded', expanded);
  layoutToggle.setAttribute('aria-pressed', String(expanded));
  layoutToggle.setAttribute('aria-label', expanded ? 'Use compact width' : 'Use expanded width');
  layoutToggle.title = expanded ? 'Use compact width' : 'Use expanded width';
  void chrome.storage.local.set({ [LAYOUT_KEY]: expanded });
}

async function restoreState(): Promise<void> {
  const [durable, transient] = await Promise.all([
    chrome.storage.local.get([CONVERSATION_KEY, LAYOUT_KEY]),
    chrome.storage.session.get(SESSION_KEY),
  ]);
  const expanded = durable[LAYOUT_KEY] !== false;
  setExpanded(expanded);

  const conversation = durable[CONVERSATION_KEY] as ConversationState | undefined;
  if (conversation && Date.now() - conversation.updatedAt < 30 * 24 * 60 * 60_000) {
    messages = conversation.messages.length ? conversation.messages : [welcomeMessage];
    currentResult = conversation.currentResult;
    lastQuery = conversation.lastQuery;
  }
  renderResults(currentResult);
  renderChat();

  const snapshot = transient[SESSION_KEY] as SessionSnapshot | undefined;
  if (!snapshot || Date.now() - snapshot.updatedAt > 10 * 60_000) return;
  const conversationUpdatedAt = conversation?.updatedAt || 0;
  if (snapshot.stage === 'results' && snapshot.result && snapshot.updatedAt > conversationUpdatedAt) {
    renderResults(snapshot.result);
    messages.push(message('assistant', assistantResultSummary(snapshot.result)));
    renderChat();
    persistConversation();
  } else if (snapshot.stage === 'error' && snapshot.error && snapshot.error.code !== 'REQUEST_CANCELLED') {
    showInlineError(snapshot.error);
  } else if (snapshot.stage === 'searching') {
    setSearching(true);
    const poll = window.setInterval(async () => {
      const latestStored = await chrome.storage.session.get(SESSION_KEY);
      const latest = latestStored[SESSION_KEY] as SessionSnapshot | undefined;
      if (!latest || latest.requestId !== snapshot.requestId || latest.stage === 'searching') return;
      window.clearInterval(poll);
      setSearching(false);
      if (latest.stage === 'results' && latest.result) {
        renderResults(latest.result);
        messages.push(message('assistant', assistantResultSummary(latest.result)));
        renderChat();
        persistConversation();
      } else if (latest.error && latest.error.code !== 'REQUEST_CANCELLED') showInlineError(latest.error);
    }, 500);
    window.setTimeout(() => window.clearInterval(poll), 30_000);
  }
}

chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  void beginSearch(chatInput.value);
});
chatInput.addEventListener('input', () => setInputError(null));
chatInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
micButton.addEventListener('click', () => {
  if (recorder.isRecording) recorder.stop();
  else void startRecording();
});
mustElement('stop-recording').addEventListener('click', () => recorder.stop());
mustElement('cancel-recording').addEventListener('click', cancelRecording);
mustElement('cancel-search').addEventListener('click', () => void cancelSearch());
mustElement('new-search').addEventListener('click', resetConversation);
retryButton.addEventListener('click', () => {
  if (lastError?.retriable && lastQuery) void beginSearch(lastQuery, false);
});
layoutToggle.addEventListener('click', () => setExpanded(!document.body.classList.contains('is-expanded')));
checkStoreButton.addEventListener('click', () => void checkActiveStore());
loadMoreButton.addEventListener('click', () => appendNextProductBatch());
productsPane.addEventListener('scroll', () => {
  if (productsPane.scrollTop > 0) productPaneHasScrolled = true;
}, { passive: true });
new IntersectionObserver(
  (entries) => {
    if (productPaneHasScrolled && entries.some((entry) => entry.isIntersecting)) appendNextProductBatch();
  },
  { root: productsPane, rootMargin: '180px 0px' },
).observe(productScrollSentinel);
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (recorder.isRecording) cancelRecording();
  else if (currentRequestId) void cancelSearch();
});
window.addEventListener('pagehide', () => {
  if (recorder.isRecording) recorder.cancel();
  stopRecordingClock();
});

async function checkActiveStore(): Promise<void> {
  checkStoreButton.disabled = true;
  checkStoreButton.textContent = 'Checking…';
  storeContext.classList.remove('is-unsupported');
  storeName.textContent = 'Checking store…';
  let response: WorkerResponse;
  try {
    response = await sendMessage({ type: 'GET_ACTIVE_STORE' });
  } catch {
    response = {
      ok: false,
      error: createError(
        'INTERNAL_ERROR',
        'Dhaaga could not start correctly. Reload the extension from chrome://extensions, then try again.',
        true,
      ),
    };
  } finally {
    checkStoreButton.disabled = false;
    checkStoreButton.textContent = 'Check current tab';
  }

  if (response.ok && 'store' in response) {
    storeName.textContent = `Live on ${response.store.name}`;
    workspaceView.hidden = false;
    blockingView.hidden = true;
    chatInput.focus();
  } else if (!response.ok) {
    storeName.textContent = 'Unsupported store';
    storeContext.classList.add('is-unsupported');
    showBlockingError(response.error);
  }
}

void restoreState();
void checkActiveStore();

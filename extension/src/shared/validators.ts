import { SUPPORTED_HOSTS } from '../config';
import type { ErrorCode, ExtensionError } from './contracts';

export function getSupportedStore(tabUrl: string | undefined): { name: string; domain: string; origin: string } {
  if (!tabUrl) throw createError('UNSUPPORTED_PAGE', 'Open Outfitters in the active tab to use Dhaaga.');
  let url: URL;
  try {
    url = new URL(tabUrl);
  } catch {
    throw createError('UNSUPPORTED_PAGE', 'Open Outfitters in the active tab to use Dhaaga.');
  }
  const domain = url.hostname.toLowerCase().replace(/\.$/, '');
  if (url.protocol !== 'https:' || !SUPPORTED_HOSTS.has(domain)) {
    throw createError('UNSUPPORTED_STORE', 'Open Outfitters in the active tab to use this MVP.');
  }
  return { name: 'Outfitters', domain, origin: url.origin };
}

export function isSafeProductUrl(raw: string): boolean {
  try {
    const url = new URL(raw);
    return url.protocol === 'https:' && SUPPORTED_HOSTS.has(url.hostname.toLowerCase()) && url.pathname.startsWith('/products/');
  } catch {
    return false;
  }
}

export function createError(code: ErrorCode, message: string, retriable = false): ExtensionError {
  return { code, message, retriable };
}

export function normalizeBackendError(status: number, payload: unknown): ExtensionError {
  const record = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {};
  const detail = record.detail && typeof record.detail === 'object'
    ? record.detail as Record<string, unknown>
    : record;
  const rawCode = typeof detail.code === 'string' ? detail.code : '';
  const rawDetail = typeof record.detail === 'string' ? record.detail.toLowerCase() : '';
  const known: ErrorCode[] = [
    'UNSUPPORTED_PAGE', 'UNSUPPORTED_STORE', 'EMPTY_INTENT', 'CATALOG_UNAVAILABLE',
    'CATALOG_TIMEOUT', 'RATE_LIMITED', 'PROVIDER_UNAVAILABLE', 'INTERNAL_ERROR',
  ];
  const code: ErrorCode = rawDetail.includes('empty audio') ? 'EMPTY_AUDIO'
    : rawDetail.includes('too large') ? 'AUDIO_TOO_LARGE'
    : rawDetail.includes('audio format') || rawDetail.includes('transcription') ? 'TRANSCRIPTION_FAILED'
    : known.includes(rawCode as ErrorCode)
    ? rawCode as ErrorCode
    : status === 429 ? 'RATE_LIMITED' : status >= 500 ? 'PROVIDER_UNAVAILABLE' : 'INTERNAL_ERROR';
  const defaults: Record<ErrorCode, string> = {
    UNSUPPORTED_PAGE: 'Open Outfitters in the active tab to use Dhaaga.',
    UNSUPPORTED_STORE: 'Open Outfitters in the active tab to use this MVP.',
    MIC_PERMISSION_DENIED: 'Microphone access is blocked. Allow it in browser settings, or type your request.',
    EMPTY_AUDIO: 'No audio was recorded. Please try again or type your request.',
    AUDIO_TOO_LARGE: 'That recording is too long. Please keep it under 30 seconds.',
    TRANSCRIPTION_FAILED: "We couldn't understand that recording. Please try again or type instead.",
    EMPTY_INTENT: 'Add a product, style, occasion, color, size, or budget so Dhaaga knows what to find.',
    CATALOG_UNAVAILABLE: "We couldn't read this store's catalog.",
    CATALOG_TIMEOUT: 'The catalog took too long to respond. Please try again.',
    RATE_LIMITED: 'Dhaaga is busy right now. Try again in a moment.',
    PROVIDER_UNAVAILABLE: "Dhaaga's matching service is unavailable right now.",
    NO_MATCHES: "We couldn't find a close match in this catalog.",
    REQUEST_CANCELLED: 'Search cancelled.',
    INTERNAL_ERROR: 'The search could not be completed.',
  };
  const serverMessage = typeof detail.message === 'string' && detail.message.length <= 240
    ? detail.message
    : null;
  return createError(code, serverMessage || defaults[code], ['CATALOG_TIMEOUT', 'RATE_LIMITED', 'PROVIDER_UNAVAILABLE', 'INTERNAL_ERROR'].includes(code));
}

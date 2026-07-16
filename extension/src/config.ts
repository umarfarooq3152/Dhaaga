/** Update both this value and manifest host_permissions for deployment. */
export const API_BASE_URL = 'http://localhost:8000';
export const SUPPORTED_HOSTS = new Set(['outfitters.com.pk', 'www.outfitters.com.pk']);
// The API has its own 25-second safety limit. Leave enough client-side headroom
// to receive and render the API's structured recovery response instead of
// aborting the request at the exact same instant.
export const SEARCH_TIMEOUT_MS = 30_000;
export const TRANSCRIPTION_TIMEOUT_MS = 20_000;
export const MAX_RECORDING_MS = 30_000;
export const MAX_AUDIO_BYTES = 5 * 1024 * 1024;
export const SESSION_KEY = 'dhaagaCurrentSearch';
export const CONVERSATION_KEY = 'dhaagaConversation';
export const LAYOUT_KEY = 'dhaagaExpandedLayout';

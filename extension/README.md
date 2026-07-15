# Dhaaga Chrome Extension

Chrome MV3 shopping workspace for natural-language search on the current
supported Shopify store. Products stay on the left while a persistent chat on
the right carries the current intent through follow-up refinements. The MVP
allowlist contains Outfitters only.

## Development

1. Start the FastAPI backend at `http://localhost:8000` with `GROQ_API_KEY`
   configured in `backend/.env`.
2. Run `npm install`, then `npm run build` in this directory.
3. Load `extension/dist` from `chrome://extensions` in Developer mode.
4. Open an HTTPS page on `outfitters.com.pk` and click the extension action.

Useful checks:

```bash
npm run typecheck
npm test
npm run test:e2e
npm run build
```

The E2E test launches an unpacked extension using Playwright's full Chromium
channel. It may need to run outside a restricted process sandbox.

## Deployment configuration

`src/config.ts` and `manifest.json` intentionally point to the local backend.
Change the API base URL, `host_permissions`, and CSP `connect-src` together when
deploying. Never add Groq to host permissions and never bundle a Groq key.

The backend validates the store origin independently against
`EXTENSION_ALLOWED_DOMAINS`; adding a store requires updating both the product
allowlist and the extension/product-link validation allowlist.

## Data and permissions

- `activeTab`: reads the current tab URL only after the user opens the popup.
- `storage`: keeps the current in-flight/result state in session storage so a
  text search can be recovered when the popup reopens.
- Backend host permission: transcription and search API requests only.
- No content scripts, DOM access, cookies, history, checkout, or accounts.

Microphone audio is recorded only while the popup remains open, sent to the
backend/Groq for transcription, and not stored by Dhaaga. Merchant product
images load remotely with `referrerpolicy="no-referrer"`.

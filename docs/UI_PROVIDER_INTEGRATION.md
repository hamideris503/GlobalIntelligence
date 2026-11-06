# UI Provider & API Key Integration

## Capabilities exposed in new shell (via existing pages)
- Provider list / status: `pages/ai.tsx`, `pages/keys.tsx`, `pages/settings.tsx`
- Add/edit/delete provider: existing forms (unchanged, now under new shell)
- Enable/disable: existing toggles
- Model selection + default: existing
- Connection test: existing (calls backend test endpoint)
- Masked key display: backend returns masked only
- Secure storage: backend `APP_ENCRYPTION_KEY` (Fernet); never in browser

## Security guarantees (unchanged)
- Full key never returned by API
- No key in localStorage/sessionStorage/URL/console/log
- Delete/change require confirmation (existing)
- Mock stripped in production; classifier rejects mock results in prod

## Provider availability
Provider usability depends on real credentials/region/plan. Where unavailable, UI shows real reason (from backend error), not "active". No fake-active providers.

## Tests
Existing `tests/test_settings.py`, `tests/test_security.py`, provider verification docs. No new bypass introduced.
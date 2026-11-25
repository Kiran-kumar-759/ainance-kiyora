# Voice Interaction & Draft-Only Expense Capture (Phase 10)

## Browser Speech Capabilities (`frontend/src/pages/assistant/AssistantPage.tsx`)
1. **Voice Input (STT):** Uses `window.SpeechRecognition || window.webkitSpeechRecognition` (`en-IN` locale) to dictate into the editable composer input.
   - If the browser does not support Web Speech API or microphone access is denied, a clear fallback notice appears and users can type or paste transcripts manually into the same composer.
2. **Optional Read-Aloud (TTS):** Uses `window.speechSynthesis` (`en-IN` locale) when supported, with per-message Play/Stop buttons and a persisted `voice_read_aloud_enabled` preference. Bracketed citation markers (`[1]`) are cleaned before speaking.

## Safe Voice-to-Expense Draft Flow
- Clicking **Draft Expense** calls `POST /api/v1/assistant/voice/parse-expense` (`backend/app/services/assistant/voice_service.py`).
- The backend deterministically parses transaction type (`expense`/`income`), `Decimal` amount (`₹`/`Rs`/`INR`), relative dates (`today`/`yesterday`), user-owned categories, normalized merchant identity, and **only explicitly named user accounts** — leaving ambiguous fields explicit in `missing_fields` and **never writing any ledger entry**.
- The frontend opens an editable **Review & Confirm Voice Expense Draft** modal (`requires_user_confirmation = true`). Only when the user verifies the fields and clicks **Confirm & Save Expense** does the frontend invoke `financeApi.createTransaction(...)`.

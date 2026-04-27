# Token & Conversational Rules

## Availability and booking

- If user asks for availability by date/service, show available slots directly.
- If user requests an exact time (e.g. `10:00`), answer availability for that time first.
- If exact time is unavailable, offer alternatives.
- Always request explicit confirmation before creating appointment.

## Menu vs AI

- Greetings/random short messages should use guided menu (no LLM call).
- Clear direct intents can go to deterministic flow first.
- Use LLM when the request is ambiguous or requires language understanding.

## Daily limits

- Per `business_id + telegram_user_id`:
  - total daily interactions (`TG_DAILY_TOTAL_LIMIT`)
  - AI interactions (`TG_DAILY_AI_LIMIT`)
- If AI limit is reached, keep guided mode available.
- If total limit is reached, block until next UTC day.

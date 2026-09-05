# 🌅 Morning Health Bot

An automated pipeline that reads yesterday's activity and sleep data from Google Health (Fitbit), has an AI analyze it against real sleep-science benchmarks, and sends a personalized morning message via Telegram — every day, on its own.

## What it does

Every morning at 10:00 AM (Singapore time):

1. Fetches yesterday's step count and last night's sleep data (stages, efficiency, awakenings, bedtime/wake time) from the **Google Health API**
2. Summarizes the raw data into meaningful metrics (sleep efficiency %, stage percentages, awakening count)
3. Sends that summary to an **AI model (DeepSeek)**, which analyzes it against known healthy sleep ranges and writes a short, honest, specific morning message — not generic praise
4. Delivers the message via **Telegram**
5. Runs automatically via **GitHub Actions**, no server required

## Architecture
Google Health API (OAuth2)

 ▼

Fetch steps (dailyRollUp) + sleep (list + stages)

▼

Summarize → efficiency %, stage %, awakenings, bedtime/wake time

▼

DeepSeek AI → analytical morning message

▼

Telegram Bot API → delivered to phone

▼

Scheduled daily via GitHub Actions cron


## Why this exists

Most fitness trackers show you numbers. Numbers without context aren't useful — "85 minutes of deep sleep" means nothing until you know that's ~20% of total sleep, which is actually within a healthy range. This bot does that translation automatically, and flags patterns a person might miss (e.g. high sleep efficiency but frequent brief awakenings — a genuinely fragmented night that raw totals hide).

## Tech stack

- **Python** — data fetching, parsing, orchestration
- **Google Health API** — successor to the legacy Fitbit Web API (sunset Sept 2026), OAuth2 with offline refresh tokens
- **DeepSeek API** — AI-generated analysis (OpenAI-compatible chat completions)
- **Telegram Bot API** — message delivery
- **GitHub Actions** — free, serverless daily scheduling

## How AI was used (and how it wasn't)

This project uses AI in two distinct ways, worth separating:

**AI as a build assistant** — helped debug the Google Health API integration, since it's a brand-new API with real, undocumented schema quirks. Getting the `dailyRollUp` request body right took three iterations against actual error messages and official docs (`civilTimeInterval` → `range` → the correct nested `CivilDateTime` structure).

**AI as a product feature** — the DeepSeek call that generates the actual morning message. Its first output was generic cheerleading ("You crushed your steps!"); I rewrote the prompt to include explicit healthy-range benchmarks and instructed it to act like "a knowledgeable friend, not a cheerleader." The result correctly surfaced a real pattern in the data (98.2% sleep efficiency but 15 brief awakenings) instead of just praising the biggest number.

I did not blindly accept AI output at any stage — every API integration bug was diagnosed from real error responses and status codes, and the AI-generated message was evaluated and iterated on before being considered "done."

## Known limitations

- Google's OAuth refresh token expires after 7 days in "Testing" mode (this app hasn't gone through Google's production verification for sensitive health scopes). Requires periodic re-authorization for long-term use.
- The Singapore (UTC+8) timezone offset is hardcoded rather than using a timezone-aware library — a reasonable simplification for a single-user personal project.

## Setup

Requires six environment variables / GitHub Actions secrets:

- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` — Google Cloud OAuth credentials for the Health API
- `DEEPSEEK_API_KEY` — DeepSeek API access
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram bot credentials

See `get_token.py` for the one-time OAuth authorization flow needed to obtain a refresh token.

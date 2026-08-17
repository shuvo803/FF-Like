# Free Fire Auto Like Bot — Python (Flask + MongoDB + Render + Telegram-only Admin)

This is a Python (Flask) port of the original PHP project. Behavior, environment
variables, and the HL Gaming Official API integration are unchanged.

## What you configure

Only these environment variables are required:

```env
BOT_TOKEN=
ADMIN_IDS=
MONGODB_URI=
MONGODB_DATABASE=freefire_like
LOG_CHANNEL_ID=

HL_GAMING_USERUID=
LIKE_API_KEY=
NAME_CHECK_API_KEY=
```

There is no MySQL, no DB host/port/user/password, no web admin panel, no admin
password, and no Telegram Mini App.

HL Gaming endpoint URLs and the Bangladesh region are automatic; you do not
configure URL or region variables.

## Automatic settings

- Timezone is fixed to `Asia/Dhaka`.
- Render's `RENDER_EXTERNAL_URL` is detected automatically.
- Webhook URL is generated automatically from the Render URL (`/webhook`).
- Webhook secret is derived from the bot token; it is never stored in an
  environment variable.
- The app calls `setWebhook` from the `/` and `/health` routes. Render health
  checks therefore also keep the webhook configured.

## Project layout

```
app.py                 Flask entrypoint: /, /health, /webhook
config.py               env loading + small helpers
database.py              MongoDB connection + settings
api.py                   HL Gaming Official API adapter
functions.py             bot menus, handlers, admin panel
includes/security.py     UID validation, sessions, cooldowns
includes/telegram.py     Telegram Bot API wrapper
requirements.txt
Dockerfile
render.yaml
.env.example
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values
python app.py          # dev server on :8000
```

For local webhook testing you'll need a public HTTPS URL (e.g. via a tunnel)
and to set `APP_URL` in `.env` so `setWebhookIfPossible()` can register it.

## Deploy on Render

1. Push this project to GitHub.
2. Render → New → Blueprint → select the repository.
3. `render.yaml` creates the Docker web service.
4. Add the environment variables listed above.
5. Deploy.
6. Open `/health`; it should return `{"ok": true, ...}`.
7. Start the bot with `/start`.

## MongoDB Atlas

Create a MongoDB database/user and use the SRV connection string as
`MONGODB_URI`.

Example:

`mongodb+srv://USERNAME:PASSWORD@CLUSTER.mongodb.net/`

No SQL import is required. Collections and indexes are created automatically.

## Admin

Put one or more Telegram IDs in `ADMIN_IDS`, comma-separated.

Example:

`ADMIN_IDS=123456789,987654321`

Admins use `/admin`. All admin controls are inline buttons inside Telegram.

Features:
- Dashboard
- Users
- Requests
- Statistics
- Maintenance
- Block/unblock
- Broadcast text/image/video/document

## Log channel

Set:

`LOG_CHANNEL_ID=-1001234567890`

Add the bot to the channel and give it permission to post messages.

When a new user starts the bot, a log is sent with name, username, Telegram
ID, language and time. Like request, success and failure events are also
logged. Secrets are never sent to the log channel.

## HL Gaming Official API configuration

This package is wired for the HL Gaming Official formats documented for its
Free Fire APIs.

### Like API

The bot sends a server-side JSON POST to
`https://proapis.hlgamingofficial.com/main/games/freefire/likes/api`:

```json
{
  "useruid": "YOUR_HL_GAMING_DEVELOPER_UID",
  "api": "YOUR_HL_GAMING_LIKE_API_KEY",
  "region": "BD",
  "ff_uid": 123456789
}
```

The `amount` selected in the bot UI is recorded in the bot's request log
only. HL Gaming's documented Likes endpoint does not document an `amount`
request parameter, so this adapter intentionally does not invent one.

HL Gaming documents a per-player daily like limit and plan-based API quotas.
A 100/500/1000/2500 package in the bot UI does not mean the provider will
necessarily send that many likes in one API call — align the UI/package
limits with your active HL Gaming plan.

### Name Check / Player Name

The bot sends a POST to
`https://proapis.hlgamingofficial.com/main/games/freefire/account/api`:

```json
{
  "sectionName": "AllData",
  "PlayerUid": "123456789",
  "region": "bd",
  "useruid": "YOUR_HL_GAMING_DEVELOPER_UID",
  "api": "YOUR_HL_GAMING_ACCOUNT_API_KEY"
}
```

The bot reads the player name from `result.AccountInfo.AccountName`.

If your HL Gaming account uses the same developer UID/API key for both
services, you can put the same values in both places.

### Security

Never paste your real API key into GitHub, Telegram, screenshots, or source
code. Rotate/revoke any key that leaks in a screenshot before using it again.

Use only APIs and game-service integrations you are authorized to use. This
project does not implement game security bypasses, exploits, hacked
endpoints, or unauthorized access — it only calls the documented HL Gaming
Official REST API with your own credentials.

## FCIS Result Monitor

Python script to log into `myu.mans.edu.eg`, monitor the grades page, and send a Telegram notification when the status changes from **`النتيجة لم تعلن بعد`** or when grades appear.

### 1. Install dependencies

From the project root:

```bash
pip install -r requirements.txt
```

### 2. Create `.env`

Create a file named `.env` in the project root with:

```bash
MYU_USERNAME=your_username
MYU_PASSWORD=your_password
MYU_LANG=ar
MYU_STUDENT_ID=530000        # your student id parameter used in the URL
MYU_APP_ID=4                 # usually 4, as seen in the request
POLL_INTERVAL_SECONDS=120    # how often to check (in seconds)

# Telegram (optional but recommended)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789

# Discord (optional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

To get `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`:

- Create a bot with BotFather in Telegram and copy the API token.
- Start a chat with the bot and use any standard method (e.g. a small helper bot like `@userinfobot`) to discover your numeric chat ID.

### 3. Run the monitor

```bash
python monitor_results.py
```

The script will:

- Log in to `myu.mans.edu.eg`.
- Periodically call the grades endpoint.
- Detect when the message changes from `النتيجة لم تعلن بعد` or when the session expires and re-login as needed.
- Send you a Telegram and/or Discord message when the status changes, depending on which you configured.


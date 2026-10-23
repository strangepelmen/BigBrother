# Big Brother

Kufar ad monitoring in Telegram with a small settings mini app.

```
Mini app (GitHub Pages, /docs) ──RPC──►  Supabase (free Postgres)  ◄──SQL──  bot (bot/, your PC/VPS)
```

```
Big-Brother/
├── schema.sql        database (run once in Supabase)
├── docs/             mini app  -> GitHub Pages
│   ├── index.html
│   └── config.js     Supabase URL + anon key
└── bot/              Telegram bot + Kufar scraper
    ├── main.py       startup / shutdown
    ├── config.py     .env + validation
    ├── database.py   Postgres queries
    ├── kufar.py      shared headless browser scraper
    ├── watcher.py    background monitoring loop
    ├── handlers.py   commands
    ├── keyboards.py  card button
    └── utils.py      escaping + sending cards
```

## 0. Token safety
A token that was ever pasted in a chat or committed to GitHub is burned.
@BotFather → `/revoke` → choose the bot → use the NEW token, only in `bot/.env`.
Also `/setname` → "Big Brother" to change the display name.

## 1. Database (Supabase, free)
1. supabase.com → New project (save the DB password).
2. SQL Editor → paste all of `schema.sql` → Run.
3. Project Settings → API: copy **Project URL** and the **anon public** key.
4. Connect → **Session pooler** → copy the URI, put your password in it.

## 2. Mini app (GitHub Pages, free)
1. Edit `docs/config.js` (URL + anon key).
2. Push the project to a GitHub repo (`.gitignore` already protects `.env`).
3. Repo → Settings → Pages → Deploy from branch → `main`, folder `/docs`.
4. URL: `https://USER.github.io/REPO/`

## 3. Bot (PC / VPS)
```
cd bot
cp .env.example .env        # fill BOT_TOKEN, WEBAPP_URL, DATABASE_URL
pip install -r requirements.txt
playwright install chromium
python main.py
```
The bot must stay running (scraping needs a real browser, GitHub Pages can't do that).
Free always-on options: old PC / Raspberry Pi / Oracle Cloud Always Free VM.
On Linux servers also run `playwright install-deps chromium` once.

## Commands
`/search <item>` · `/track <item>` · `/untrack <item>` · `/list` · `/test` · `/stop`
The "Big Brother" menu button opens the mini app (queries, stop words, search limit).

## How it works
- First scan of a new query only memorises current ads, then you get alerts for NEW ads only
  (survives bot restarts).
- Each unique query is scraped once per cycle (default 60 s) however many users track it.
- Free Supabase projects pause after a week of inactivity; the bot's scans keep it awake.

## Security notes
- The public key can only call 2 validated functions (`bb_get`, `bb_save_settings`);
  the tables themselves are closed.
- Limitation: a static mini app can't prove who the Telegram user is, so someone who knows another
  user's numeric id could read/change that user's settings. Fine for a personal/friends tool.
  For strict security, add a Supabase Edge Function that verifies Telegram `initData`.

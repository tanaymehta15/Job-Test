# Mumbai Job Tracker

Two trackers in one repo, both running entirely on GitHub's free infrastructure — once
set up, they keep working even if you never open Claude again:

1. **Equity / Asset Management / Investment Banking tracker** (`docs/index.html`) — checks
   JPMorgan, HSBC, Morgan Stanley, Bank of America, and Deutsche Bank's own careers sites
   daily for Mumbai roles matching those three keywords.
2. **All-postings tracker** (`docs/all.html`) — same 5 banks with no keyword filter (every
   open Mumbai role), plus India's top 8 equity AMCs by AUM (SBI, ICICI Prudential, HDFC,
   Nippon India, Kotak, Aditya Birla Sun Life, UTI, Axis), searched via Naukri and Indeed,
   with LinkedIn as a manual-check link.

## How it works

- `scraper/scrape_jobs.py` (tracker 1) and `scraper/scrape_all_mumbai.py` (tracker 2) each
  run once a day via GitHub Actions (`.github/workflows/daily-check.yml` and
  `daily-check-all.yml`), call each source's own job-search backend, filter for Mumbai,
  and write results into `docs/data/` and `docs/data-all/` respectively.
- `docs/index.html` and `docs/all.html` are plain webpages that read those files and
  display them. GitHub Pages hosts the `docs/` folder for free, so you get real URLs you
  can bookmark, cross-linked to each other.
- `scraper/notify.py` optionally sends you a Telegram message from either workflow when
  something new shows up.

Nothing here depends on Claude or any paid service. It's just Python + GitHub's free tier.

### A note on tracker 2's reliability

The 5 banks are live-scraped the same reliable way as tracker 1. The AMCs are a different
story: Naukri and Indeed both actively rate-limit and fingerprint automated traffic, so
they may return zero results on some days even when postings exist — treat an empty AMC
row as "check manually," not "confirmed nothing new." LinkedIn is deliberately never
scraped (it's against LinkedIn's terms and heavily blocked either way); those rows always
link to a pre-filled manual search instead. This is the honest tradeoff of a free,
no-login, unattended setup — a paid scraping API or your own logged-in session would close
the gap, at the cost of no longer being free/fully automated.

## One-time setup (about 15 minutes)

### 1. Create a GitHub account
Go to [github.com/signup](https://github.com/signup) and create a free account.

### 2. Create a new repository
- Click the **+** icon (top right) → **New repository**.
- Name it something like `mumbai-job-tracker`.
- Set it to **Public** (required for free GitHub Pages on a free account) — the data
  here is just public job listings, nothing sensitive.
- Click **Create repository**.

### 3. Upload these files
On the new repo's page, click **Add file → Upload files**, then drag in the whole
contents of this project (keep the folder structure: `.github/`, `scraper/`, `docs/`,
`README.md`). Commit directly to `main`.

### 4. Turn on GitHub Pages
- Go to the repo's **Settings → Pages**.
- Under "Build and deployment", set **Source: Deploy from a branch**.
- Branch: `main`, folder: `/docs`. Save.
- After a minute or two, GitHub will show you a URL like
  `https://<your-username>.github.io/mumbai-job-tracker/` — that's your dashboard.

### 5. (Optional) Set up Telegram notifications
This doesn't require giving anyone your Telegram password — you're just creating a bot
that messages you.
1. In Telegram, message **@BotFather** → `/newbot` → follow the prompts. It gives you a
   **bot token** (looks like `123456789:AAExample-Token`).
2. Message your new bot anything (e.g. "hi") so it can message you back.
3. Visit `https://api.telegram.org/bot<your-token>/getUpdates` in a browser (replace
   `<your-token>`) and find `"chat":{"id":...}` in the response — that number is your
   **chat ID**.
4. In your GitHub repo, go to **Settings → Secrets and variables → Actions → New
   repository secret**, and add:
   - `TELEGRAM_BOT_TOKEN` = the bot token
   - `TELEGRAM_CHAT_ID` = the chat id
5. These secrets are only ever readable by your own GitHub Actions runs — not visible to
   me or anyone else.

If you skip this step, everything still works — you'll just check the dashboard instead
of getting a push message.

### 6. Run it once manually to check it works
Go to the **Actions** tab → pick **Daily job check** (tracker 1) or **Daily job check
(all Mumbai postings)** (tracker 2) → **Run workflow**. After it finishes (1-2 minutes),
refresh the matching dashboard URL — you should see results.

From here both run automatically every day (9:00 AM and 9:15 AM IST), no further action
needed.

## Adjusting things later

- **Change keywords or location**: edit `KEYWORDS` / `LOCATION_FILTER` at the top of
  `scraper/scrape_jobs.py`.
- **Change the schedule**: edit the `cron` line in `.github/workflows/daily-check.yml`
  (it's in UTC).
- **A company shows "couldn't check today"**: that bank's careers site likely changed
  its search backend. Check the failed run's logs under the Actions tab for the exact
  error — that usually points to what changed.
- **Bank of America**: its careers platform (Phenom People) doesn't have a documented
  public search API, so it currently just links out to a pre-filled search on their site
  rather than showing live results inline. If you ever open your browser's dev tools
  Network tab while searching their careers site and spot the actual data request, that
  can be wired in to make it fully automatic too.

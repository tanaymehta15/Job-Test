"""
Sends a Telegram message listing any new postings found in this run.

Usage:
  python notify.py                              # V1 tracker (docs/data)
  python notify.py --data-dir docs/data-all --label "Mumbai (all companies)"

Needs two GitHub Actions secrets (set once in the repo, never seen by
anyone but you and GitHub):
  TELEGRAM_BOT_TOKEN  - from @BotFather
  TELEGRAM_CHAT_ID    - your personal chat id (see README for how to get it)

If either secret is missing, this script just prints a message and exits
quietly -- the workflow doesn't fail, it just skips notifying.
"""

import argparse
import json
import os
import sys

import requests

MAX_JOBS_IN_MESSAGE = 25


def build_message(jobs, label):
    lines = [f"\U0001F4E2 {label}: {len(jobs)} new Mumbai posting(s) found:\n"]
    for job in jobs[:MAX_JOBS_IN_MESSAGE]:
        source = f" via {job['source']}" if job.get("source") and job["source"] != "Careers site" else ""
        lines.append(f"\u2022 [{job['company']}{source}] {job['title']}\n  {job['url']}")
    if len(jobs) > MAX_JOBS_IN_MESSAGE:
        lines.append(f"\n...and {len(jobs) - MAX_JOBS_IN_MESSAGE} more. Check the dashboard for the full list.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.path.join(os.path.dirname(__file__), "..", "docs", "data"))
    parser.add_argument("--label", default="Job tracker")
    args = parser.parse_args()

    new_jobs_file = os.path.join(args.data_dir, "new_jobs_latest.json")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not os.path.exists(new_jobs_file):
        print(f"No {new_jobs_file} found, nothing to notify.")
        return

    with open(new_jobs_file, "r", encoding="utf-8") as f:
        new_jobs = json.load(f)

    if not new_jobs:
        print("No new jobs this run, skipping notification.")
        return

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set - skipping notification "
              "(this is fine if you're using the dashboard only).")
        return

    message = build_message(new_jobs, args.label)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }, timeout=30)

    if resp.status_code != 200:
        print(f"Telegram API error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    print(f"Notified Telegram chat about {len(new_jobs)} new job(s).")


if __name__ == "__main__":
    main()

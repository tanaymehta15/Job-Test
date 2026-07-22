"""
Daily job-tracking run.

1. Calls every company adapter, once per keyword.
2. Keeps only postings whose location mentions Mumbai.
3. Diffs against docs/data/seen_ids.json to work out what's new since
   yesterday.
4. Writes docs/data/jobs.json (everything currently open, for the
   dashboard) and docs/data/status.json (per-company health, so a broken
   adapter is visible instead of silently empty).
5. Prints a summary new_jobs.json to stdout / a file for notify.py to pick
   up and send via Telegram.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

from adapters import ADAPTERS

KEYWORDS = ["Equity", "Asset Management", "Investment Banking"]
LOCATION_FILTER = "mumbai"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
JOBS_FILE = os.path.join(DATA_DIR, "jobs.json")
SEEN_FILE = os.path.join(DATA_DIR, "seen_ids.json")
STATUS_FILE = os.path.join(DATA_DIR, "status.json")
NEW_JOBS_FILE = os.path.join(DATA_DIR, "new_jobs_latest.json")


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def matches_keyword(job, keyword_used):
    # The adapter already searched by keyword, but some ATS "search" params
    # do fuzzy/full-text matching rather than exact filtering, so double
    # check the title actually mentions one of our real keywords too.
    text = job.get("title", "").lower()
    return any(k.lower() in text for k in KEYWORDS) or keyword_used.lower() in text


def matches_location(job):
    if job.get("manual_check"):
        return True
    return LOCATION_FILTER in job.get("location", "").lower()


def run():
    all_jobs = {}
    status = {}
    now = datetime.now(timezone.utc).isoformat()

    for company, fetch_fn in ADAPTERS.items():
        company_jobs = {}
        error = None
        for keyword in KEYWORDS:
            try:
                results = fetch_fn(keyword)
            except Exception as exc:  # noqa: BLE001 - log & continue, never crash the whole run
                error = f"{type(exc).__name__}: {exc}"
                print(f"[{company}] keyword='{keyword}' FAILED: {error}", file=sys.stderr)
                traceback.print_exc()
                time.sleep(1)
                continue

            for job in results:
                if not matches_location(job):
                    continue
                if not job.get("manual_check") and not matches_keyword(job, keyword):
                    continue
                company_jobs[job["id"]] = job
            time.sleep(1)  # be polite between requests

        status[company] = {
            "checked_at": now,
            "ok": error is None,
            "error": error,
            "matches_found": len(company_jobs),
        }
        all_jobs.update(company_jobs)
        print(f"[{company}] {len(company_jobs)} matching posting(s), ok={error is None}")

    seen_ids = set(load_json(SEEN_FILE, []))
    new_jobs = [j for jid, j in all_jobs.items() if jid not in seen_ids and not j.get("manual_check")]

    jobs_out = []
    for jid, job in all_jobs.items():
        job = dict(job)
        job["is_new"] = jid not in seen_ids
        jobs_out.append(job)
    jobs_out.sort(key=lambda j: (j["company"], not j["is_new"], j.get("title", "")))

    save_json(JOBS_FILE, {
        "generated_at": now,
        "location_filter": "Mumbai",
        "keywords": KEYWORDS,
        "jobs": jobs_out,
    })
    save_json(STATUS_FILE, status)
    save_json(NEW_JOBS_FILE, new_jobs)

    all_ids = seen_ids.union(all_jobs.keys())
    save_json(SEEN_FILE, sorted(all_ids))

    print(f"\nDone. {len(jobs_out)} total matching postings, {len(new_jobs)} new since last run.")
    return new_jobs


if __name__ == "__main__":
    run()

"""
Version 2: ALL new postings, Mumbai only, no Equity/AM/IB keyword filter.

Covers two groups of companies, fetched differently:
  1. The 5 banks -- same adapters as scrape_jobs.py, called with no keyword
     so they return their full open catalog, which we then filter down to
     Mumbai-located roles only.
  2. Top Indian equity AMCs by AUM -- these don't have individually
     reverse-engineered career-site adapters, so instead we search for each
     one by name on Naukri and Indeed (best-effort - see adapters_amc.py for
     the honest caveats on reliability), plus a direct LinkedIn search link.

Output mirrors scrape_jobs.py's format so the same dashboard style can read
it, just written to docs/data-all/ instead of docs/data/.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from adapters import ADAPTERS
from adapters_amc import fetch_naukri, fetch_indeed, fetch_linkedin_link

LOCATION_FILTER = "mumbai"

AMCS = [
    "SBI Mutual Fund",
    "ICICI Prudential Asset Management",
    "HDFC Asset Management",
    "Nippon India Mutual Fund",
    "Kotak Mahindra Asset Management",
    "Aditya Birla Sun Life Mutual Fund",
    "UTI Asset Management",
    "Axis Asset Management",
]

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "data-all")
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


def matches_location(job):
    if job.get("manual_check"):
        return True
    return LOCATION_FILTER in job.get("location", "").lower()


def run():
    all_jobs = {}
    status = {}
    now = datetime.now(timezone.utc).isoformat()

    # --- Group 1: the 5 banks, full catalog, filtered to Mumbai ---
    for company, fetch_fn in ADAPTERS.items():
        error = None
        company_jobs = {}
        try:
            results = fetch_fn()  # no keyword => full open catalog
            for job in results:
                if matches_location(job):
                    job = dict(job)
                    job["source"] = job.get("source", "Careers site")
                    company_jobs[job["id"]] = job
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            print(f"[{company}] FAILED: {error}", file=sys.stderr)
            traceback.print_exc()

        status[company] = {"checked_at": now, "ok": error is None, "error": error,
                            "matches_found": len(company_jobs)}
        all_jobs.update(company_jobs)
        print(f"[{company}] {len(company_jobs)} Mumbai posting(s), ok={error is None}")
        time.sleep(1)

    # --- Group 2: top AMCs, via Naukri + Indeed + LinkedIn (manual link) ---
    for amc in AMCS:
        amc_jobs = {}
        errors = []

        for source_name, fetch_fn in [("Naukri", fetch_naukri), ("Indeed", fetch_indeed)]:
            try:
                results = fetch_fn(amc, "Mumbai")
                for job in results:
                    if matches_location(job):
                        amc_jobs[job["id"]] = job
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{source_name}: {type(exc).__name__}: {exc}")
                print(f"[{amc}] {source_name} FAILED: {exc}", file=sys.stderr)
            time.sleep(1.5)  # be gentle with these hosts

        # LinkedIn: always add the manual-check link, never scraped.
        for job in fetch_linkedin_link(amc, "Mumbai"):
            amc_jobs[job["id"]] = job

        status[amc] = {
            "checked_at": now,
            "ok": len(errors) == 0,
            "error": "; ".join(errors) if errors else None,
            "matches_found": len(amc_jobs),
        }
        all_jobs.update(amc_jobs)
        print(f"[{amc}] {len(amc_jobs)} Mumbai posting(s) across sources")

    # --- Diff against what we've seen before ---
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
        "keywords": [],
        "note": "All open roles, no keyword filter. Banks are live-scraped; "
                 "AMCs are aggregated best-effort from Naukri/Indeed, plus a "
                 "manual LinkedIn search link.",
        "jobs": jobs_out,
    })
    save_json(STATUS_FILE, status)
    save_json(NEW_JOBS_FILE, new_jobs)

    all_ids = seen_ids.union(all_jobs.keys())
    save_json(SEEN_FILE, sorted(all_ids))

    print(f"\nDone. {len(jobs_out)} total Mumbai postings tracked, {len(new_jobs)} new since last run.")
    return new_jobs


if __name__ == "__main__":
    run()

"""
Adapters for the job-aggregator sources, used for companies (mainly the
AMCs) that don't have a bespoke careers-site adapter of their own.

Important honesty note, so this doesn't quietly give you wrong confidence:

- Naukri does have a JSON search API that its own website calls
  (jobapi/v3/search) and it's used below. It's a widely-used pattern, but
  Naukri actively rate-limits and fingerprints traffic from data-center IPs
  like GitHub Actions runners, so this may return zero results on some days
  even when postings exist. Treat empty results from Naukri as "check
  manually", not "confirmed nothing new".
- Indeed's search results page is scraped best-effort from server-rendered
  HTML. Indeed also actively blocks bot-like traffic, so the same caveat
  applies.
- LinkedIn is deliberately NOT scraped here. LinkedIn's terms explicitly
  prohibit automated scraping and it aggressively fingerprints/blocks
  non-browser traffic - building something that tries to get around that
  isn't something I'll do. Instead this adapter just returns a direct,
  pre-filled search link so you can check it yourself in one click.

None of this is a knock against the approach -- it's the honest tradeoff of
"free, no-login, runs unattended" vs. "always complete." If you want more
complete aggregator coverage, a paid scraping API (ScrapingBee, Apify, etc.)
or your own logged-in session would close the gap, at the cost of no longer
being free/fully automated.
"""

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}
TIMEOUT = 20


def fetch_naukri(company_name, location="Mumbai"):
    url = "https://www.naukri.com/jobapi/v3/search"
    params = {
        "noOfResults": 20,
        "urlType": "search_by_keyword",
        "searchType": "adv",
        "keyword": company_name,
        "location": location,
        "k": company_name,
        "l": location,
    }
    headers = {**HEADERS, "Appid": "109", "Systemid": "Naukri", "Accept": "application/json"}
    r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    jobs = []
    for jd in data.get("jobDetails", []):
        title = jd.get("title", "")
        job_location = jd.get("placeholders", {}).get("location", "") if isinstance(jd.get("placeholders"), dict) else jd.get("location", "")
        job_id = jd.get("jobId", "")
        jobs.append({
            "company": company_name,
            "source": "Naukri",
            "title": title,
            "location": job_location or location,
            "id": f"naukri-{job_id}",
            "url": jd.get("jdURL") or jd.get("staticUrl") or url,
            "posted": jd.get("createdDate", ""),
        })
    return jobs


def fetch_indeed(company_name, location="Mumbai"):
    url = "https://in.indeed.com/jobs"
    params = {"q": f'"{company_name}"', "l": location}
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()

    # Indeed server-renders a first page of results; job cards live in
    # <a> tags carrying a data-jk (job key) attribute. We deliberately keep
    # this to a light, dependency-free parse rather than a full HTML parser
    # pass, and fail closed (empty list) if the page shape doesn't match.
    import re
    jobs = []
    for m in re.finditer(r'data-jk="([a-zA-Z0-9]+)"[^>]*>.*?<span[^>]*title="([^"]+)"', r.text):
        job_key, title = m.group(1), m.group(2)
        jobs.append({
            "company": company_name,
            "source": "Indeed",
            "title": title,
            "location": location,
            "id": f"indeed-{job_key}",
            "url": f"https://in.indeed.com/viewjob?jk={job_key}",
            "posted": "",
        })
    return jobs


def fetch_linkedin_link(company_name, location="Mumbai"):
    search_url = (
        "https://www.linkedin.com/jobs/search/?keywords="
        f"{requests.utils.quote(company_name)}&location={requests.utils.quote(location + ', India')}"
    )
    return [{
        "company": company_name,
        "source": "LinkedIn",
        "title": "Manual check (LinkedIn isn't auto-scraped, see adapters_amc.py)",
        "location": location,
        "id": f"linkedin-manual-{company_name.lower().replace(' ', '-')}",
        "url": search_url,
        "posted": "",
        "manual_check": True,
    }]

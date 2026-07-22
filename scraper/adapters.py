"""
One adapter function per company. Each adapter talks to the job-search
backend that the company's own careers site uses, and returns a plain list
of dicts:

    {"company": str, "title": str, "location": str, "id": str,
     "url": str, "posted": str}

Every adapter is wrapped in try/except by the caller (scrape_jobs.py), so a
single company breaking (site redesign, API change, rate limit) never takes
down the whole run -- it just gets logged in data/status.json and shows up
on the dashboard as "couldn't check today".

Notes on reliability, so future-you (or future-Claude) knows where to look
if a company stops returning results:

- JPMorgan runs on Oracle Recruiting Cloud (Fusion). The endpoint below is
  Oracle's standard public "Candidate Experience" REST API -- the same
  shape is reused by every company on that platform, just with a different
  host/siteNumber.
- Morgan Stanley and Deutsche Bank both run on Workday. Workday's `cxs`
  (Candidate Experience Site) JSON API is extremely standardized across
  every Workday tenant, which is why the same fetch_workday() function
  works for both.
- HSBC runs on Eightfold.ai, which also exposes a consistent public JSON
  search API across its customers.
- Bank of America runs on Phenom People, which renders job search results
  client-side and does not have a stable documented public JSON endpoint.
  Rather than guess at one and silently return wrong data, this adapter
  returns a direct, pre-filled search link so the dashboard can still show
  you something actionable. If you (or I) ever capture the real network
  call from a browser's dev tools Network tab while searching BofA's site,
  it can be dropped in here to make this one fully automatic too.
"""

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

TIMEOUT = 30


def fetch_jpmorgan(keyword=""):
    url = "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    keyword_clause = f"keyword={requests.utils.quote(keyword)}," if keyword else ""
    finder = (
        "findReqs;siteNumber=CX_1001,"
        "facetsList=LOCATIONS;WORK_LOCATIONS;TITLES;CATEGORIES,"
        f"limit=100,offset=0,{keyword_clause}"
        "sortBy=POSTING_DATES_DESC"
    )
    params = {
        "onlyData": "true",
        "expand": "requisitionList.secondaryLocations,requisitionList.workLocation",
        "finder": finder,
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", [{}])
    reqs = items[0].get("requisitionList", []) if items else []

    jobs = []
    for it in reqs:
        job_id = it.get("Id") or it.get("RequisitionNumber")
        loc = it.get("PrimaryLocation", "") or ""
        secondary = it.get("SecondaryLocations")
        if secondary:
            loc = f"{loc}; {secondary}"
        jobs.append({
            "company": "JPMorgan",
            "title": it.get("Title", "").strip(),
            "location": loc,
            "id": f"jpm-{job_id}",
            "url": f"https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/{job_id}",
            "posted": it.get("PostedDate", ""),
        })
    return jobs


def fetch_workday(tenant, site, host, company_name, keyword=""):
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    # Empty searchText is a well-known way to list a Workday tenant's full
    # open catalog (used for "all roles" mode); a non-empty keyword narrows it.
    body = {"appliedFacets": {}, "limit": 100, "offset": 0, "searchText": keyword}
    r = requests.post(url, json=body, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    postings = data.get("jobPostings", [])

    jobs = []
    for p in postings:
        path = p.get("externalPath", "")
        jobs.append({
            "company": company_name,
            "title": p.get("title", "").strip(),
            "location": p.get("locationsText", ""),
            "id": f"{tenant}-{path}",
            "url": f"https://{host}{path}",
            "posted": p.get("postedOn", ""),
        })
    return jobs


def fetch_morgan_stanley(keyword=""):
    return fetch_workday("ms", "External", "ms.wd5.myworkdayjobs.com", "Morgan Stanley", keyword)


def fetch_deutsche_bank(keyword=""):
    return fetch_workday("db", "DBWebsite", "db.wd3.myworkdayjobs.com", "Deutsche Bank", keyword)


def fetch_hsbc(keyword=""):
    url = "https://hsbc.eightfold.ai/api/apply/v2/jobs"
    params = {"domain": "hsbc.com", "query": keyword, "location": "Mumbai", "start": 0, "num": 100}
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    positions = data.get("positions", [])

    jobs = []
    for p in positions:
        jobs.append({
            "company": "HSBC",
            "title": p.get("name", "").strip(),
            "location": p.get("location", ""),
            "id": f"hsbc-{p.get('id')}",
            "url": p.get("canonicalPositionUrl", ""),
            "posted": p.get("t_create", ""),
        })
    return jobs


def fetch_bank_of_america(keyword=""):
    # See module docstring: no stable public JSON API found for this platform.
    # Returning a direct search link instead of guessed/unreliable data.
    label = keyword or "Mumbai roles"
    search_url = f"https://careers.bankofamerica.com/en-us/job-search?ss=&q={requests.utils.quote(keyword)}"
    return [{
        "company": "Bank of America",
        "title": f'Manual check needed: search "{label}"',
        "location": "Mumbai (filter on site)",
        "id": f"bofa-manual-{label.lower().replace(' ', '-')}",
        "url": search_url,
        "posted": "",
        "manual_check": True,
    }]


ADAPTERS = {
    "JPMorgan": fetch_jpmorgan,
    "Morgan Stanley": fetch_morgan_stanley,
    "Deutsche Bank": fetch_deutsche_bank,
    "HSBC": fetch_hsbc,
    "Bank of America": fetch_bank_of_america,
}

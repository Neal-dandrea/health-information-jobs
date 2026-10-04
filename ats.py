"""ats.py — read job postings straight from employer career sites.

Most employers host their careers page on one of a few platforms, and each
platform has a public feed that the careers page itself reads. Given an
employer's identifier on a platform, these functions return that employer's
postings in the collector's common shape.

Every reader keeps a posting only when its title is a fit (roles.relevant) and
its location is a fit or cannot be told yet (roles.location_fits,
roles.location_unknown). A location such as "3 Locations" is resolved later,
when the posting's own page is read for its description.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Tuple

import roles

TODAY = dt.date.today()


def wanted(title: str, locations: List[str], anyloc: bool = False) -> bool:
    """`anyloc` is for an employer that only operates inside the area, where a
    location such as "Burnet Campus" names a building and not a town."""
    return roles.relevant(title) and (anyloc or roles.location_fits(locations)
                                      or roles.location_unknown(locations)
                                      or all(_STATE_ONLY.match(x or "") for x in locations))


def _date(text) -> Optional[str]:
    return (str(text)[:10] or None) if text else None


def greenhouse(token, company, fetch, listing, anyloc=False):
    doc = json.loads(fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"))
    out = []
    for j in doc.get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        if wanted(j.get("title"), [loc], anyloc):
            out.append(listing("careers", company, j["title"], j["absolute_url"],
                               location=loc,
                               posted=_date(j.get("first_published") or j.get("updated_at"))))
    return out


def lever(token, company, fetch, listing, anyloc=False):
    doc = json.loads(fetch(f"https://api.lever.co/v0/postings/{token}?mode=json"))
    out = []
    for j in doc if isinstance(doc, list) else []:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or [cat.get("location") or ""]
        if (j.get("workplaceType") or "").lower() == "remote":
            locs = locs + ["Remote"]
        if not wanted(j.get("text"), locs, anyloc):
            continue
        posted = None
        if j.get("createdAt"):
            posted = dt.datetime.fromtimestamp(
                j["createdAt"] / 1000, dt.timezone.utc).date().isoformat()
        out.append(listing("careers", company, j["text"], j["hostedUrl"],
                           location="; ".join(locs), posted=posted))
    return out


def ashby(token, company, fetch, listing, anyloc=False):
    doc = json.loads(fetch("https://api.ashbyhq.com/posting-api/job-board/"
                           + urllib.parse.quote(token)))
    out = []
    for j in doc.get("jobs", []):
        loc = j.get("location") or ""
        if j.get("isRemote") and "remote" not in loc.lower():
            loc = (loc + "; Remote").strip("; ")
        if wanted(j.get("title"), loc.split("; "), anyloc):
            out.append(listing("careers", company, j["title"], j["jobUrl"],
                               location=loc, posted=_date(j.get("publishedAt"))))
    return out


def smartrecruiters(token, company, fetch, listing, anyloc=False, max_pages: int = 10):
    out = []
    for page in range(max_pages):
        doc = json.loads(fetch("https://api.smartrecruiters.com/v1/companies/"
                               f"{token}/postings?limit=100&offset={page * 100}"))
        rows = doc.get("content", [])
        for j in rows:
            loc = j.get("location") or {}
            where = loc.get("fullLocation") or ", ".join(
                x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
            if loc.get("remote"):
                where = (where + "; Remote").strip("; ")
            if wanted(j.get("name"), where.split("; "), anyloc):
                out.append(listing("careers", company, j["name"],
                                   f"https://jobs.smartrecruiters.com/{token}/{j['id']}",
                                   location=where, posted=_date(j.get("releasedDate"))))
        if len(rows) < 100:
            break
    return out


def _workday_posted(text: str) -> Optional[str]:
    """'Posted Today' / 'Posted Yesterday' / 'Posted 3 Days Ago' -> a date.
    'Posted 30+ Days Ago' has no real date, so it stays None."""
    t = (text or "").lower()
    if "today" in t:
        return TODAY.isoformat()
    if "yesterday" in t:
        return (TODAY - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)(\+?) days? ago", t)
    if m and not m.group(2):
        return (TODAY - dt.timedelta(days=int(m.group(1)))).isoformat()
    return None


# Workday's search box works well on some sites and is ignored on others, so the
# reader walks the whole job list when it is small enough and falls back to a
# set of searches when it is not.
WORKDAY_WALK_LIMIT = 2500
WORKDAY_SEARCHES = ["health information", "coding", "clinical documentation",
                    "revenue cycle", "reimbursement", "medical records",
                    "patient access", "clinical research", "compliance",
                    "data quality", "remote", "Cincinnati"]


def workday(token, company, fetch, listing, anyloc=False):
    tenant, wd, site = token.split("/")
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    url = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    seen, out = set(), []

    def page(search: str, offset: int) -> dict:
        return json.loads(fetch(url, json_body={"appliedFacets": {}, "limit": 20,
                                                "offset": offset, "searchText": search}))

    def take(posts: List[dict]):
        for j in posts:
            path = j.get("externalPath")
            if not path or path in seen:
                continue
            seen.add(path)
            loc = j.get("locationsText") or ""
            if wanted(j.get("title"), [loc], anyloc):
                out.append(listing("careers", company, j["title"], f"{base}/{site}{path}",
                                   location=loc, posted=_workday_posted(j.get("postedOn"))))

    first = page("", 0)
    total = int(first.get("total") or 0)
    take(first.get("jobPostings") or [])
    if total <= WORKDAY_WALK_LIMIT:
        for offset in range(20, total, 20):
            take(page("", offset).get("jobPostings") or [])
    else:
        for search in WORKDAY_SEARCHES:
            for offset in range(0, 100, 20):
                doc = page(search, offset)
                posts = doc.get("jobPostings") or []
                take(posts)
                if len(posts) < 20 or offset + 20 >= int(doc.get("total") or 0):
                    break
    return out


def oracle(token, company, fetch, listing, anyloc=False, max_jobs: int = 3000):
    """Oracle Cloud career sites. The identifier is host/site."""
    host, site = token.split("/")
    out, offset = [], 0
    while offset < max_jobs:
        doc = json.loads(fetch(
            f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
            f"?onlyData=true&expand=requisitionList.secondaryLocations"
            f"&finder=findReqs;siteNumber={site},limit=100,offset={offset},"
            f"sortBy=POSTING_DATES_DESC"))
        item = (doc.get("items") or [{}])[0]
        rows = item.get("requisitionList") or []
        for j in rows:
            locs = [j.get("PrimaryLocation") or ""] + [
                x.get("Name") or "" for x in j.get("secondaryLocations") or []]
            if "remote" in (j.get("WorkplaceType") or "").lower():
                locs.append("Remote")
            locs = [x for x in locs if x]
            if wanted(j.get("Title"), locs, anyloc):
                out.append(listing(
                    "careers", company, j["Title"],
                    f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j['Id']}",
                    location="; ".join(locs), posted=_date(j.get("PostedDate"))))
        offset += 100
        if len(rows) < 100 or offset >= int(item.get("TotalJobsCount") or 0):
            break
    return out


READERS: Dict[str, Callable] = {
    "greenhouse": greenhouse, "lever": lever, "ashby": ashby,
    "smartrecruiters": smartrecruiters, "workday": workday, "oracle": oracle,
}

# A location that names a state and nothing else, as some employers post.
_STATE_ONLY = re.compile(r"^\s*(OH|KY|Ohio|Kentucky)?,?\s*(United States|USA|US)?\s*$", re.I)


def collect(companies: Dict[str, dict], fetch, listing, workers: int = 4,
            progress=None) -> Tuple[List[dict], Dict[str, str]]:
    """Read every employer in the registry. Returns (listings, failures).

    `companies` maps "platform:identifier" to {"name": ...}, with two optional
    settings. "strict": true keeps only titles specific to the field, for an
    employer that is not purely in healthcare. "home": "Cincinnati, OH" is used
    when that employer posts a state with no city. "local": true marks an
    employer that only operates inside the area, so every location it posts
    counts and gets its home town added. An employer whose feed fails
    is reported in `failures` and does not stop the others.
    """
    def one(key: str):
        platform, token = key.split(":", 1)
        try:
            entry = companies[key]
            rows = READERS[platform](token, entry["name"], fetch, listing,
                                     anyloc=bool(entry.get("local")))
            if entry.get("strict"):
                # Not purely a healthcare employer, so generic titles do not count.
                rows = [r for r in rows if roles.relevant(r["title"], broad_ok=False)]
            for r in rows:
                r["ats"] = key
                # An employer with one home area that posts "OH, United States".
                if entry.get("home") and _STATE_ONLY.match(r["location"] or ""):
                    r["location"] = entry["home"]
            return key, rows, None
        except Exception as e:                            # noqa: BLE001
            return key, [], f"{type(e).__name__}: {str(e)[:80]}"

    rows: List[dict] = []
    failures: Dict[str, str] = {}
    keys = [k for k in companies if k.split(":", 1)[0] in READERS]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (key, got, err) in enumerate(pool.map(one, keys), 1):
            rows += got
            if err:
                failures[key] = err
            if progress:
                progress(n, len(keys), companies[key]["name"], len(got), err)
    return rows, failures

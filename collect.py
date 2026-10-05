#!/usr/bin/env python3
"""collect.py — build one list of health information jobs, remote or near Cincinnati.

Two kinds of source feed the list.

  1. Employer career sites. data/companies.json names the employers to check,
     mostly hospitals, health plans, revenue cycle firms and research
     organisations. Each one's own job feed is read on every run (see ats.py).
  2. The Muse, a general job board with a public feed, for its healthcare and
     office categories in Cincinnati and remote.

What counts as a fitting role and a fitting place is decided in roles.py. The
collector then merges duplicates, tags each listing (field, level, area), reads
each posting's description, scores it against a private resume profile, and
writes

    docs/data.json         every active listing, with every field
    docs/list.json         the same listings with only what the web page shows
    docs/listings.csv      the same, flat, for a spreadsheet
    data/seen.json         id -> date first seen (the state between runs)
    data/terms.json        the skills each posting mentions, read once and kept
    out/new_<date>.md      what is new since the last run (one file per day)

USAGE

    python3 collect.py                 # everything
    python3 collect.py --no-careers    # The Muse only, a few seconds
    python3 collect.py --describe 0    # skip reading descriptions

A source that fails is reported and skipped. It never stops the run, and its
listings from earlier runs are not marked as gone.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

import ats
import match
import semantic
import roles

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DOCS = os.path.join(HERE, "docs")
OUT = os.path.join(HERE, "out")
UA = "Mozilla/5.0 (compatible; job-list/1.0; personal job search)"
TODAY = dt.date.today()


# ── fetching ────────────────────────────────────────────────────────────────
# IPv6 connections hang on some machines until they time out, and urllib tries
# IPv6 first. Asking for IPv4 addresses only avoids a minute-long stall per file.
_getaddrinfo = socket.getaddrinfo


def _ipv4_only(host, port, family=0, *args, **kwargs):
    return _getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)


socket.getaddrinfo = _ipv4_only


def fetch(url: str, timeout: int = 60, json_body: Optional[dict] = None) -> bytes:
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    data = None
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode()
    req = urllib.request.Request(url, headers=headers, data=data)
    # A site that says "too many requests" is asked again after a pause.
    for pause in (3, 8, 20, None):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or pause is None:
                raise
            time.sleep(pause)


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8-sig", errors="replace")


# ── the common shape ────────────────────────────────────────────────────────
def listing(source: str, company: str, title: str, url: str, *,
            location: str = "", posted: Optional[str] = None,
            degrees: Optional[List[str]] = None, category: str = "",
            sponsorship: str = "", pay: str = "", note: str = "") -> dict:
    return {
        "source": source,
        "company": clean(company),
        "title": clean(title),
        "url": (url or "").strip(),
        "location": clean(location),
        "posted": posted,                 # ISO date, or None when the board gives none
        "degrees": degrees or [],
        "category": clean(category),
        "sponsorship": clean(sponsorship),
        "pay": clean(pay),
        "note": clean(note),
    }


_TAG = re.compile(r"<[^>]+>")
_EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿️‍]")


def clean(text) -> str:
    text = _TAG.sub("", str(text or ""))
    text = _EMOJI.sub("", text)
    return re.sub(r"\s+", " ", text.replace("**", "")).strip(" |")


# ── sources ─────────────────────────────────────────────────────────────────
MUSE_LOCATIONS = ["Cincinnati, OH", "Flexible / Remote"]
MUSE_CATEGORIES = ["Healthcare", "Accounting and Finance", "Administration and Office",
                   "Customer Service"]
MUSE_MAX_AGE_DAYS = 120
MUSE_MAX_PAGES = 12
# Descriptions that arrive with a listing, so they need no second request.
INLINE_TEXT: Dict[str, str] = {}


def src_muse() -> List[dict]:
    """The Muse. Only titles that are specific to the field are kept, since its
    employers are not all in healthcare."""
    out = []
    oldest = (TODAY - dt.timedelta(days=MUSE_MAX_AGE_DAYS)).isoformat()
    for loc in MUSE_LOCATIONS:
        for cat in MUSE_CATEGORIES:
            for page in range(1, MUSE_MAX_PAGES + 1):
                doc = json.loads(fetch("https://www.themuse.com/api/public/jobs?"
                                       + urllib.parse.urlencode(
                                           {"location": loc, "category": cat, "page": page})))
                for j in doc.get("results", []):
                    posted = (j.get("publication_date") or "")[:10] or None
                    if posted and posted < oldest:
                        continue
                    if not roles.relevant(j.get("name"), broad_ok=False):
                        continue
                    where = "; ".join("Remote" if x["name"] == "Flexible / Remote"
                                      else x["name"] for x in j.get("locations", []))
                    url = (j.get("refs") or {}).get("landing_page") or ""
                    out.append(listing("muse", (j.get("company") or {}).get("name"),
                                       j["name"], url, location=where, posted=posted,
                                       category=cat))
                    INLINE_TEXT[url] = match.plain(j.get("contents") or "")
                if page >= int(doc.get("page_count") or 0):
                    break
                time.sleep(0.3)
    return out


SOURCES: Dict[str, Callable[[], List[dict]]] = {"muse": src_muse}


# ── merging ─────────────────────────────────────────────────────────────────
_TRACKING = re.compile(r"^(utm_|gh_src|src$|source$|ref$|s$|lever-source|microsite$)", re.I)


def canonical_url(url: str) -> str:
    """Same posting, same string: drop tracking parameters and trailing noise."""
    try:
        p = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    query = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
             if not _TRACKING.match(k)]
    path = re.sub(r"/(apply|application)/?$", "", p.path).rstrip("/")
    host = p.netloc.lower().removeprefix("www.")
    return urllib.parse.urlunsplit(("https", host, path,
                                    urllib.parse.urlencode(sorted(query)), ""))


_CO_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|group|"
                        r"holdings|technologies|technology|labs?|lp)\b\.?")


def norm_company(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    s = _CO_SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_title(title: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())
    return re.sub(r"\s+", " ", s).strip()


_PHD = re.compile(r"\b(ph\.?\s?d|doctoral|doctorate)\b", re.I)


def merge(rows: List[dict]) -> List[dict]:
    """One record per posting. Two rows are the same posting when their cleaned
    URLs match, or when they come from DIFFERENT boards and company and title
    match after normalizing.

    The name match is deliberately not applied within one board. A company that
    lists "Software Engineer Intern" 36 times on the same board has 36 separate
    postings, and folding them together would hide a new one behind an old one.
    """
    by_url: Dict[str, dict] = {}
    by_name: Dict[tuple, List[dict]] = {}
    merged: List[dict] = []
    for r in rows:
        if not r["url"] or not r["title"] or not r["company"]:
            continue
        cu = canonical_url(r["url"])
        nk = (norm_company(r["company"]), norm_title(r["title"]))
        rec = by_url.get(cu) or next(
            (c for c in by_name.get(nk, []) if r["source"] not in c["sources"]), None)
        if rec is None:
            rec = {"id": hashlib.sha1(cu.encode()).hexdigest()[:12],
                   "company": r["company"], "title": r["title"],
                   "url": r["url"], "urls": [], "locations": [],
                   "posted": None, "degrees": [], "categories": [],
                   "sponsorship": "", "pay": "", "notes": [], "sources": [],
                   "ats": []}
            merged.append(rec)
        by_url.setdefault(cu, rec)
        if rec not in by_name.setdefault(nk, []):
            by_name[nk].append(rec)
        if r["url"] not in rec["urls"]:
            rec["urls"].append(r["url"])
        for loc in filter(None, (x.strip() for x in r["location"].split(";"))):
            if loc not in rec["locations"]:
                rec["locations"].append(loc)
        if r["posted"] and (rec["posted"] is None or r["posted"] < rec["posted"]):
            rec["posted"] = r["posted"]          # earliest sighting wins
        for d in r["degrees"]:
            if d not in rec["degrees"]:
                rec["degrees"].append(d)
        if r["category"] and r["category"] not in rec["categories"]:
            rec["categories"].append(r["category"])
        rec["sponsorship"] = rec["sponsorship"] or r["sponsorship"]
        rec["pay"] = rec["pay"] or r["pay"]
        if r["note"] and r["note"] not in rec["notes"]:
            rec["notes"].append(r["note"])
        if r["source"] not in rec["sources"]:
            rec["sources"].append(r["source"])
        if r.get("ats") and r["ats"] not in rec["ats"]:
            rec["ats"].append(r["ats"])
    for rec in merged:
        # Prefer a direct employer link over an aggregator redirect.
        direct = [u for u in rec["urls"] if "themuse.com" not in u]
        rec["url"] = (direct or rec["urls"])[0]
    return merged


# ── tagging ─────────────────────────────────────────────────────────────────
# Tags describe the posting. They are not a ranking.
_US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN "
                 "MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA "
                 "WA WV WI WY DC".split())
_US_NAMES = re.compile(
    r"united states|\busa?\b|u\.s\.|alabama|alaska|arizona|arkansas|california|"
    r"colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|"
    r"iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|"
    r"minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|"
    r"new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|"
    r"oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|"
    r"texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|"
    r"bay area|san francisco|seattle|boston|chicago|nyc|silicon valley", re.I)
_STATE_CODE = re.compile(r"\b([A-Z]{2})\b")


def region_of(locations: List[str]) -> List[str]:
    """Which of US / International / Remote a posting covers. May be several.
    An empty list means the posting gave no usable location."""
    out = []
    for loc in locations:
        if re.search(r"remote", loc, re.I) and "Remote" not in out:
            out.append("Remote")
        us = bool(_US_NAMES.search(loc)) or any(
            c in _US_STATES for c in _STATE_CODE.findall(loc))
        plain = re.sub(r"remote|hybrid|multiple|locations?|\d+|[^a-z]", "", loc.lower())
        if us:
            if "US" not in out:
                out.append("US")
        elif plain and "International" not in out:
            out.append("International")
    return out


_STATE_NAMES = dict(zip(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV "
    "NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split(),
    ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
     "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
     "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
     "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
     "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
     "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
     "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
     "Washington", "West Virginia", "Wisconsin", "Wyoming", "District of Columbia"]))
_CA_PROVINCES = {"ON": "Ontario", "QC": "Quebec", "BC": "British Columbia", "AB": "Alberta",
                 "MB": "Manitoba", "SK": "Saskatchewan", "NS": "Nova Scotia",
                 "NB": "New Brunswick"}
_COUNTRIES = [
    ("Canada", r"canada|toronto|vancouver|montr[eé]al|ottawa|waterloo|calgary"),
    ("United Kingdom", r"united kingdom|\buk\b|england|scotland|london|cambridge, (uk|gb)|\bgbr?\b"),
    ("Germany", r"germany|deutschland|berlin|munich|m[uü]nchen|\bdeu?\b"),
    ("France", r"france|paris|\bfra\b"),
    ("India", r"india|bangalore|bengaluru|hyderabad|pune|mumbai|gurgaon|chennai|\bind\b"),
    ("China", r"china|shanghai|beijing|shenzhen|hangzhou|\bchn\b"),
    ("Japan", r"japan|tokyo|\bjpn\b"),
    ("Singapore", r"singapore|\bsgp\b"),
    ("Ireland", r"ireland|dublin|\birl\b"),
    ("Netherlands", r"netherlands|amsterdam|eindhoven|\bnld\b"),
    ("Switzerland", r"switzerland|z[uü]rich|geneva|\bche\b"),
    ("Israel", r"israel|tel aviv|\bisr\b"),
    ("Australia", r"australia|sydney|melbourne|\baus\b"),
    ("Poland", r"poland|warsaw|krak[oó]w|\bpol\b"),
    ("Spain", r"spain|madrid|barcelona|\besp\b"),
    ("Italy", r"italy|milan|rome\b|\bita\b"),
    ("Sweden", r"sweden|stockholm|\bswe\b(?! intern)"),
    ("Mexico", r"mexico|\bmex\b"),
    ("Brazil", r"bra[sz]il|s[aã]o paulo|\bbra\b"),
    ("South Korea", r"korea|seoul|\bkor\b"),
    ("Taiwan", r"taiwan|taipei|hsinchu|\btwn\b"),
    ("Hong Kong", r"hong kong|\bhkg\b"),
    ("Romania", r"romania|bucharest"),
    ("Hungary", r"hungary|budapest"),
    ("Malaysia", r"malaysia|kuala lumpur|penang"),
    ("Philippines", r"philippines|manila"),
    ("United Arab Emirates", r"emirates|dubai|abu dhabi|\buae\b"),
]
_COUNTRY_PATS = [(name, re.compile(pat, re.I)) for name, pat in _COUNTRIES]


def places_of(locations: List[str], regions: List[str]) -> List[str]:
    """State and country names a posting's locations imply, spelled out, so a
    search for "Ohio" finds "Cincinnati, OH" and "Canada" finds "Toronto, ON"."""
    out: List[str] = []

    def add(name: str):
        if name not in out:
            out.append(name)

    for loc in locations:
        codes = _STATE_CODE.findall(loc)
        for c in codes:
            if c in _STATE_NAMES:
                add(_STATE_NAMES[c])
            elif c in _CA_PROVINCES and not _US_NAMES.search(loc):
                add(_CA_PROVINCES[c]); add("Canada")
        for name in _STATE_NAMES.values():
            if re.search(r"\b" + re.escape(name) + r"\b", loc, re.I):
                add(name)
        for name, pat in _COUNTRY_PATS:
            if pat.search(loc):
                add(name)
    if "US" in regions:
        add("United States")
    return out


def tag(rec: dict) -> None:
    title = rec["title"]
    rec["level"] = roles.level_of(title)
    rec["tracks"] = roles.tracks_of(title)
    rec["regions"] = region_of(rec["locations"])
    rec["areas"] = roles.areas_of(rec["locations"])
    rec["places"] = places_of(rec["locations"], rec["regions"])
    # A remote role based in another country needs the right to work there, so
    # it is not counted as remote here. "Remote - Nationwide" names no country
    # and stays.
    countries = {name for name, _ in _COUNTRIES}
    abroad = any(p in countries for p in rec["places"])
    if abroad and "United States" not in rec["places"]:
        rec["areas"] = [a for a in rec["areas"] if a != "Remote"]


# ── state and output ────────────────────────────────────────────────────────
def load_json(path: str, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


PAGE_FIELDS = {"exp_note", "company", "title", "url", "locations", "places", "posted", "first_seen", "match", "match_basis", "sem", "req", "tracks", "level", "areas"}


def slim(rec: dict) -> dict:
    """The record as published. Drops what is empty or repeats another field."""
    out = {k: v for k, v in rec.items() if v not in ("", [], None, {})}
    if out.get("urls") == [rec["url"]]:
        del out["urls"]
    return out


_DEFAULTS = {"urls": None, "locations": [], "posted": None, "degrees": [],
             "categories": [], "sponsorship": "", "pay": "", "notes": [],
             "sources": [], "ats": [], "level": "", "tracks": [], "areas": [],
             "regions": [], "places": []}


def unslim(rec: dict) -> dict:
    out = dict(rec)
    for k, v in _DEFAULTS.items():
        if k not in out:
            out[k] = [rec["url"]] if k == "urls" else (list(v) if isinstance(v, list) else v)
    return out


def write_outputs(listings: List[dict], new: List[dict], report: Dict[str, str],
                  first_run: bool) -> str:
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(DOCS, "data.json"), "w") as fh:
        json.dump({"generated": dt.datetime.now(dt.timezone.utc)
                                  .isoformat(timespec="seconds"),
                   "count": len(listings), "sources": report,
                   # the day of the first build, when everything was "first seen"
                   "baseline": min((r["first_seen"] for r in listings), default=""),
                   "listings": [slim(r) for r in listings]}, fh,
                  separators=(",", ":"))
    # The page reads this smaller file. It carries only the fields the page shows.
    with open(os.path.join(DOCS, "list.json"), "w") as fh:
        json.dump({"generated": dt.datetime.now(dt.timezone.utc)
                                  .isoformat(timespec="seconds"),
                   "sources": report,
                   "baseline": min((r["first_seen"] for r in listings), default=""),
                   "listings": [{k: v for k, v in slim(r).items() if k in PAGE_FIELDS}
                                for r in listings]}, fh, separators=(",", ":"))
    cols = ["first_seen", "posted", "match", "match_basis", "sem", "years",
            "degrees_asked", "creds", "company", "title",
            "locations", "areas", "level", "tracks", "sources", "url", "id"]
    with open(os.path.join(DOCS, "listings.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in listings:
            q = r.get("req") or {}
            flat = dict(r, years=q.get("years", ""), degrees_asked=q.get("degrees", []),
                        creds=q.get("creds", []))
            w.writerow(["; ".join(flat[c]) if isinstance(flat.get(c), list)
                        else flat.get(c, "") for c in cols])
        # One report per day. A second run on the same day adds a section to it and
    # never replaces what an earlier run found.
    path = os.path.join(OUT, f"new_{TODAY.isoformat()}.md")
    exists = os.path.exists(path)
    if exists and not new:
        return path
    with open(path, "a") as fh:
        if not exists:
            fh.write(f"# New listings, {TODAY.isoformat()}\n\n")
        else:
            fh.write(f"\n## Later run at {dt.datetime.now().strftime('%H.%M')}\n\n")
        if first_run:
            fh.write("First run, so every listing counts as new. Later runs "
                     "show only what appeared since the run before.\n\n")
        fh.write(f"{len(new)} new of {len(listings)} active.\n\n")
        fh.write("| Posted | Match | Employer | Title | Location | Area |\n")
        fh.write("|---|---|---|---|---|---|\n")
        for r in new:
            loc = "; ".join(r["locations"][:2]) + (" +" + str(len(r["locations"]) - 2)
                                                  if len(r["locations"]) > 2 else "")
            title = r["title"].replace("|", "/")
            fh.write(f"| {r['posted'] or ''} | {r.get('match', '')} | "
                     f"{r['company'].replace('|', '/')} | "
                     f"[{title}]({r['url']}) | {loc.replace('|', '/')} | "
                     f"{', '.join(r['areas'])} |\n")
    return path


def keep(rec: dict) -> bool:
    """True when the listing is in a place this list covers and its employer is
    not one left off by choice. A listing whose location is still unknown is
    held back until its own page has been read."""
    # The title is checked again here, so a listing carried over from an earlier
    # run is dropped when the rules in roles.py change.
    return (bool(rec["areas"]) and not roles.blocked(rec["company"])
            and roles.relevant(rec["title"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-careers", action="store_true",
                    help="skip the employer career sites")
    ap.add_argument("--describe", type=int, default=600, metavar="N",
                    help="read at most N new posting descriptions this run "
                         "(default 600, 0 to skip)")
    a = ap.parse_args()

    rows: List[dict] = []
    report: Dict[str, str] = {}
    failed: List[str] = []
    for n in SOURCES:
        t0 = time.time()
        try:
            got = SOURCES[n]()
            rows += got
            report[n] = f"{len(got)} listings"
        except Exception as e:                            # noqa: BLE001
            failed.append(n)
            report[n] = f"FAILED: {type(e).__name__}: {e}"
        print(f"  {n:14s} {report[n]}  ({time.time() - t0:.1f}s)", flush=True)

    os.makedirs(DATA, exist_ok=True)
    companies = load_json(os.path.join(DATA, "companies.json"), {})
    failed_sites: Dict[str, str] = {}
    careers_ran = not a.no_careers
    if careers_ran:
        t0 = time.time()

        def progress(n, total, name, count, err):
            print(f"    {n:3d}/{total} {name[:38]:38s} "
                  + (f"unreachable ({err})" if err else f"{count} fitting"), flush=True)

        got, failed_sites = ats.collect(
            companies, lambda url, json_body=None: fetch(url, 25, json_body), listing,
            progress=progress)
        for r in got:                 # a description that came with the listing
            if r.get("_text"):
                INLINE_TEXT[r["url"]] = match.plain(r["_text"])
            r.pop("_text", None)
        rows += got
        report["careers"] = (f"{len(got)} listings from {len(companies)} employer "
                             f"sites, {len(failed_sites)} unreachable")
        print(f"  {'careers':14s} {report['careers']}  ({time.time() - t0:.1f}s)",
              flush=True)

    listings = merge(rows)

    seen = load_json(os.path.join(DATA, "seen.json"), {})
    first_run = not seen
    prev = {r["id"]: unslim(r) for r in load_json(os.path.join(DOCS, "data.json"),
                                                  {}).get("listings", [])}
    # Keep earlier listings from any source that failed or was not run, so an
    # unreachable career site does not make its postings vanish.
    have = {r["id"] for r in listings}
    for pid, p in prev.items():
        if pid in have:
            continue
        boards = set(p.get("sources", [])) - {"careers"}
        sites = set(p.get("ats", []))
        if (boards & set(failed)) or (sites and not careers_ran) or (sites & set(failed_sites)):
            listings.append(p)

    # Read descriptions. This also finds the real location of a posting that
    # only said "3 Locations", so tagging and the location filter come after.
    t0 = time.time()
    m = match.enrich(listings, lambda url, json_body=None: fetch(url, 20, json_body),
                     a.describe, inline=INLINE_TEXT,
                     progress=lambda n, total: print(f"    descriptions {n}/{total}",
                                                     flush=True))
    for r in listings:
        # An employer that only operates in the area names buildings, not towns.
        entry = next((companies[k] for k in r.get("ats", []) if k in companies), {})
        if entry.get("local") and entry.get("home") and not roles.location_fits(r["locations"]):
            named = [x for x in r["locations"]
                     if not roles.VAGUE.match(x) and not ats._STATE_ONLY.match(x)]
            r["locations"] = [f"{x}, {entry['home']}" for x in named] or [entry["home"]]
        tag(r)
    held = sum(1 for r in listings if roles.location_unknown(r["locations"]))
    listings = [r for r in listings if keep(r)]
    in_range = len(listings)
    report["match"] = (f"{m['described']} descriptions read"
                       + (f", {held} postings waiting for their location" if held else "")
                       + ("" if m["scored"] else ", no resume profile so no scores"))
    print(f"  {'match':14s} {report['match']}  ({time.time() - t0:.1f}s)", flush=True)

    # Score by meaning with a small open-source embedding model. On the machine
    # that keeps the description text, anything still unscored is filled in.
    t0 = time.time()
    stored = match._load_texts() if os.path.exists(match.TEXTS) else None
    sem = semantic.enrich(listings, match.FRESH, stored)
    report["meaning"] = (f"{sem['scored']} listings scored, {sem.get('new', 0)} new"
                         if sem["scored"] else f"skipped, {sem.get('note', '')}")
    print(f"  {'meaning':14s} {report['meaning']}  ({time.time() - t0:.1f}s)", flush=True)

    # Keep only roles a recent graduate can go for: those asking for a few years
    # at most, judged from the stated years or, failing that, from the wording.
    fitting = []
    for r in listings:
        ok, why = roles.experience_fit((r.get("req") or {}).get("years"),
                                       r.pop("entry_lean", None), r["title"])
        # A role that needs a coding credential and takes no other is out too.
        if ok and roles.credential_fit((r.get("req") or {}).get("creds")):
            r["exp_note"] = why
            fitting.append(r)
    report["experience"] = (f"{len(fitting)} of {in_range} roles ask for "
                            f"{roles.MAX_YEARS} years or less and no coding credential")
    print(f"  {'experience':14s} {report['experience']}", flush=True)
    listings = fitting

    new = []
    for r in listings:
        if r["id"] not in seen:
            seen[r["id"]] = TODAY.isoformat()
            new.append(r)
        r["first_seen"] = seen[r["id"]]
    # Newest first. A listing with no posting date sorts by the day it was first
    # seen, except on the first run, where that day says nothing about its age.
    key = lambda r: (r["posted"] or ("" if first_run else r["first_seen"]),
                     r["company"].lower())
    listings.sort(key=key, reverse=True)
    new.sort(key=key, reverse=True)

    path = write_outputs(listings, new, report, first_run)
    with open(os.path.join(DATA, "seen.json"), "w") as fh:
        json.dump(seen, fh, separators=(",", ":"), sort_keys=True)

    count = lambda area: sum(1 for r in listings if area in r["areas"])
    print(f"\n  {len(rows)} raw rows -> {len(listings)} listings in range")
    print(f"  {count('Cincinnati area')} Cincinnati area, {count('Remote')} remote, "
          f"{count('Dayton area')} Dayton area")
    print(f"  {len(new)} new" + (" (first run)" if first_run else ""))
    print(f"  wrote {os.path.relpath(path, HERE)}, docs/data.json, docs/listings.csv")
    if failed:
        print(f"  check these sources: {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

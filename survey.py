#!/usr/bin/env python3
"""survey.py — find which of many candidate employers have a fitting job.

data/candidates.json holds tens of thousands of company career sites gathered
from public lists. Most have nothing to do with healthcare. This script reads
each one lightly, and an employer is added to data/companies.json when it has at
least one opening right now that is plainly a healthcare job of the kind this
list covers, in a place this list covers.

Employers added this way are marked "scope": "health". The collector then keeps
only their plainly healthcare titles, because nothing else is known about them:
a "Compliance Analyst" there may be at a bank.

    python3 survey.py                  # every candidate not yet in the registry
    python3 survey.py --slice 3 7      # only the 4th seventh, for a daily rotation
    python3 survey.py --limit 500      # a quick test
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import ats
import collect
import roles

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = os.path.join(HERE, "data", "candidates.json")
REGISTRY = os.path.join(HERE, "data", "companies.json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slice", nargs=2, type=int, metavar=("N", "OF"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()

    candidates = collect.load_json(CANDIDATES, {})
    companies = collect.load_json(REGISTRY, {})
    todo = [k for k in candidates
            if k not in companies and k.split(":", 1)[0] in ats.READERS
            and not roles.blocked(candidates[k])]
    if a.slice:
        n, of = a.slice
        todo = [k for k in todo
                if int(hashlib.sha1(k.encode()).hexdigest(), 16) % of == n]
    if a.limit:
        todo = todo[:a.limit]
    print(f"  {len(todo)} candidates to read ({len(candidates)} known, "
          f"{len(companies)} already in the registry)", flush=True)

    def fetch(url, json_body=None):
        return collect.fetch(url, 15, json_body)

    def one(key):
        platform, token = key.split(":", 1)
        try:
            if platform in ats.LIGHT_READERS:
                rows = ats.READERS[platform](token, candidates[key], fetch,
                                             collect.listing, light=True)
            else:
                rows = ats.READERS[platform](token, candidates[key], fetch, collect.listing)
            fit = [r for r in rows if roles.relevant_health(r["title"])
                   and roles.location_fits([x.strip() for x in r["location"].split(";")])]
            return key, fit[:2], None
        except Exception as e:                            # noqa: BLE001
            return key, [], type(e).__name__

    t0, found, dead, done = time.time(), 0, 0, 0
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for key, fit, err in pool.map(one, todo):
            done += 1
            if err:
                dead += 1
            elif fit:
                found += 1
                companies[key] = {"name": candidates[key], "scope": "health", "fails": 0,
                                  "added": dt.date.today().isoformat(), "from": "survey"}
                print(f"    + {candidates[key][:34]:34s} {fit[0]['title'][:52]}", flush=True)
            if done % 2000 == 0:
                print(f"    {done}/{len(todo)}  {found} added, {dead} did not answer  "
                      f"({time.time() - t0:.0f}s)", flush=True)
                with open(REGISTRY, "w") as fh:
                    json.dump(companies, fh, indent=0, sort_keys=True)
    with open(REGISTRY, "w") as fh:
        json.dump(companies, fh, indent=0, sort_keys=True)
    print(f"  read {done} candidates in {time.time() - t0:.0f}s: {found} have a fitting "
          f"healthcare role now and were added, {dead} did not answer")
    print(f"  the registry now holds {len(companies)} employer sites")
    return 0


if __name__ == "__main__":
    sys.exit(main())

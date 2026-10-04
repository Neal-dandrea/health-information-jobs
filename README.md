# Health Information Job List

One searchable list of health information, coding, revenue cycle and clinical
research jobs that are remote or near Cincinnati, Ohio.

**The list is at https://neal-dandrea.github.io/health-information-jobs/**

It refreshes four times a day. You can filter by area, level, field, how
recently a role was posted and match score, and you can search by city, state
or country.

## What gets listed

A role is listed when its title fits the field and it is in one of these places.

- **Cincinnati area.** Within about 45 minutes of the north side of Cincinnati. That covers
  Cincinnati and its suburbs, Mason, West Chester, Hamilton, Middletown,
  Lebanon, and Northern Kentucky.
- **Remote.**
- **Dayton area.** About an hour away. It is hidden unless you ask for it.

Licensed clinical roles (nursing, pharmacy, therapy and the like), engineering
roles, executive roles and student roles are left out. All of this is decided in
`roles.py`.

## Where the listings come from

**Employer career sites.** `data/companies.json` names the employers to check.
They are hospitals and health systems in the region, health plans, revenue
cycle firms, health information companies and clinical research organisations.
Each employer's own job feed is read on every run. Five platforms are
supported, which are Workday, Oracle Cloud, Greenhouse, Ashby and
SmartRecruiters.

**The Muse.** A general job board with a public feed, read for its healthcare
and office categories in Cincinnati and remote.

Employers whose career sites use other platforms, such as iCIMS, are not read
yet.

## The match score

Each listing carries a score from 0 to 100 that compares the posting with the
resume of the person this list was made for. It is personal to them, so treat
it as their view of the list and not as a rating of the job.

1. The posting's description is read once and reduced to the credentials,
   skills and topics it mentions, using the vocabulary in `skills.py`.
2. The resume is reduced the same way.
3. The score is how much of what the posting mentions is on the resume. Rare,
   specific items count for more than common ones, and a posting that says very
   little is pulled toward the middle.

When a description cannot be read, the score comes from the title alone and is
shown with a dashed outline.

The resume is not in this repository. The scoring run reads a private profile
from a repository secret, and only the number is published.

## Running it yourself

It needs Python 3 and nothing else.

```bash
python3 collect.py                 # everything, a few minutes
python3 collect.py --no-careers    # The Muse only
python3 collect.py --describe 0    # skip reading descriptions

python3 match.py --build-profile Resume=resume.docx
python3 match.py --gaps            # what postings ask for that the resume lacks
```

A profile lives in `private/profile.json`, which git ignores. To score in the
scheduled run, store the same JSON as a repository secret named
`RESUME_PROFILE`. A resume can be a Word file or a PDF, and a PDF needs
`pdftotext`.

| File | What it holds |
|---|---|
| `docs/data.json` | Every active listing. The page reads this |
| `docs/listings.csv` | The same list for a spreadsheet |
| `data/companies.json` | The employer career sites to check |
| `data/seen.json` | The day each listing was first seen |
| `data/terms.json` | What each posting mentions, read once and kept |
| `roles.py` | Which titles and places belong on the list |
| `skills.py` | The vocabulary used for the match score |

## Adding an employer

Add one line to `data/companies.json`. The key is the platform and the
employer's identifier on it, such as `workday:tenant/wd5/site`, and the value
holds the employer's name. Two optional settings exist. `"strict": true` keeps
only titles specific to the field, for an employer that is not purely in
healthcare. `"home": "Cincinnati, OH"` is used when an employer posts a state
with no city.

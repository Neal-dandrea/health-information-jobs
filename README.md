# Health Information Job List

One searchable list of health information jobs and the work around it: quality
and compliance, reimbursement and revenue analysis, project and program
management, clinical documentation and patient services. Roles are remote or
near Cincinnati, Ohio.

**The list is at https://neal-dandrea.github.io/health-information-jobs/**

It refreshes four times a day, at 8 AM, 12 PM, 4 PM and 8 PM Eastern. You can filter by area, level, field, how
recently a role was posted and match score, and you can search by city, state
or country.

## What gets listed

A role is listed when its title fits the field and it is in one of these places.

- **Cincinnati area.** Within about 45 minutes of the north side of Cincinnati. That covers
  Cincinnati and its suburbs, Mason, West Chester, Hamilton, Middletown,
  Lebanon, and Northern Kentucky.
- **Remote.**
- **Dayton area.** About an hour away. It is hidden unless you ask for it.

The list is for someone early in their career, so a role is kept only when it
asks for three years of experience or less. When a posting states a number of
years, that number decides. When it states none, the embedding model compares
its wording with example sentences from entry-level and senior postings, and the
role is kept when it reads as entry level. On postings that do state years, that
comparison separated "two years or less" from "five years or more" about nine
times in ten. Both rules are in `roles.py` (`experience_fit`).

Licensed clinical roles (nursing, pharmacy, therapy and the like), medical
coding roles, engineering roles, executive roles and student roles are left out. Contract research
organisations are also left out as employers, by choice. All of this is decided in
`roles.py`.

## Where the listings come from

**Employer career sites.** `data/companies.json` names the employers to check.
They are hospitals and health systems in the region, health plans, revenue
cycle firms, health information companies and clinical research organisations.
Each employer's own job feed is read on every run. The supported platforms
are Workday, Oracle Cloud, iCIMS, Eightfold, UKG, Greenhouse, Lever, Ashby and
SmartRecruiters.

**The Muse.** A general job board with a public feed, read for its healthcare
and office categories in Cincinnati and remote.

Employers whose career sites use other platforms, such as Taleo,
SuccessFactors or Avature, are not read yet.

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

## The meaning score

The keyword score only sees words from a fixed vocabulary. A second score reads
meaning. It uses a small open-source embedding model (BAAI/bge-small-en-v1.5,
run on the CPU through the fastembed library), which places sentences with
similar meaning close together. So "experience training robot policies from
human demonstrations" lands next to a resume line about imitation learning,
although the two share no keywords.

1. The resume is split into its statements, such as each bullet and each skills
   line.
2. The posting is split into sentences, with boilerplate such as the equal
   opportunity notice and the benefits list removed.
3. Each posting sentence is paired with the closest resume statement. The score
   blends how strong the best dozen pairings are with how well the requirement
   sentences are covered on average.

Nothing is sent to any service. The page shows the mean of the keyword score
and the meaning score unless you pick one. A posting with too little text gets
no meaning score.

## Requirements read from the posting

A similarity score cannot read a number, so "5+ years" and "1 year" look alike
to it. `requirements.py` reads those details by pattern matching. It looks for
years of experience asked, degrees named, a minimum GPA, citizenship and
clearance rules, a statement that the employer will not sponsor a visa,
graduation years, and named credentials. These are facts about the posting. They
show as tags and drive the experience filter. Nothing about the reader is stored
or compared, and the patterns can miss or misread a requirement.

## Running it yourself

It needs Python 3, plus fastembed for the meaning score.

```bash
python3 collect.py                 # everything, a few minutes
python3 collect.py --no-careers    # The Muse only
python3 collect.py --describe 0    # skip reading descriptions

python3 match.py --build-profile Resume=resume.docx
python3 match.py --gaps            # what postings ask for that the resume lacks
```

The keyword profile lives in `private/profile.json` and the resume statements
for the meaning score in `private/statements.json`. Git ignores both. To score
in the scheduled run, store them as repository secrets named `RESUME_PROFILE`
and `RESUME_STATEMENTS`. A resume can be a Word file or a PDF, a PDF needs
`pdftotext`, and the meaning score needs `pip install fastembed`.

```bash
python3 semantic.py --build-statements Resume=resume.docx
python3 semantic.py --rescore      # after the resume changes
```

| File | What it holds |
|---|---|
| `docs/list.json` | Every active listing, with the fields the page shows |
| `docs/data.json` | The same listings with every field |
| `data/semantic.json` | The meaning score of each posting |
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
with no city. `"local": true` marks an employer that only operates inside the
area, so every location it posts counts. `"state": "OH"` is added to a location
that names a town with no state.

| Platform | Identifier | Example |
|---|---|---|
| Workday | tenant, server, site | `workday:tenant/wd5/site` |
| Oracle Cloud | host and site number | `oracle:host.oraclecloud.com/CX_1` |
| iCIMS | subdomain | `icims:careers-example` |
| iCIMS, newer front end | careers host | `jibe:careers.example.com` |
| Eightfold | host and domain | `eightfold:example.eightfold.ai|example.com` |
| UKG | host, tenant, board id | `ukg:recruiting.ultipro.com/TENANT/board-id` |
| Greenhouse, Lever, Ashby, SmartRecruiters | board name | `greenhouse:example` |

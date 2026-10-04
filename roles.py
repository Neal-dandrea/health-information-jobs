"""roles.py — which postings belong on this list, and how they are tagged.

This list is for health information management and the work around it, for
someone early in their career, in two places: remote, or within about 45
minutes of the north side of Cincinnati. Everything that decides "is this posting relevant"
lives here, so changing the target is a matter of editing this one file.
"""
from __future__ import annotations

import re
from typing import List

# ── what kind of work ───────────────────────────────────────────────────────
# A title needs one of these to be kept. STRICT terms are specific to the field.
# BROAD terms are generic job titles that only mean something at a healthcare
# employer, so they are used for company career sites and not for general boards.
STRICT = re.compile(
    r"health information|\bHIMS?\b|medical records?|release of information|\bROI specialist|"
    r"records (retrieval|specialist|analyst|coordinator|clerk|management)|"
    r"\bcod(er|ing)\b|\bCDI\b|clinical documentation|\bDRG\b|\bHCC\b|risk adjustment|"
    r"revenue (cycle|integrity|recovery)|reimbursement|denials?\b|appeals?\b|"
    r"charge ?(master|capture|integrity|description)|\bCDM\b|pricing transparency|"
    r"medical billing|billing (specialist|analyst|coordinator|representative)|"
    r"claims? (analyst|specialist|examiner|processor|resolution|auditor)|"
    r"patient (access|financial|accounts?|concierge|registration)|"
    r"prior authori[sz]ation|pre.?cert|insurance verification|credentialing|"
    r"(cancer|tumor|trauma|clinical) regist(rar|ry)|health data|"
    r"clinical (research|trials?|data|informatics|operations|study)|"
    r"study (coordinator|start.?up)|regulatory (coordinator|specialist|affairs)|"
    r"(healthcare|health care|hospital) (analyst|data|compliance|operations|finance)|"
    r"compliance (analyst|specialist|coordinator|auditor)|privacy (analyst|specialist|officer)|"
    r"\bHIPAA\b|\bEpic\b|\bEHR\b|\bEMR\b|informatics|payer (contract|relations|enrollment)|"
    r"managed care|utilization (review|management) (coordinator|specialist|analyst)|"
    r"quality (improvement|assurance)? ?(analyst|specialist|coordinator|auditor)|"
    r"data (quality|integrity|governance)", re.I)
BROAD = re.compile(
    r"(business|data|reporting|financial|operations|quality|contracts?|pricing|audit) analyst|"
    r"(project|program|account|operations|office|administrative) coordinator|"
    r"\bauditor\b|operations specialist|account (specialist|representative)", re.I)

# Titles that are never a fit: licensed clinical work, engineering, executives,
# and student roles (this list is for someone who has graduated).
EXCLUDE = re.compile(
    r"\bRN\b|\bLPN\b|\bAPRN\b|\bCRNA\b|\bNP\b|nurse|nursing|physician|\bMD\b|\bDO\b|surgeon|"
    r"hospitalist|pharmac|therapist|therapy|technologist|technician|\btech\b|phlebot|"
    r"medical assistant|\bCNA\b|\bSTNA\b|sonograph|radiolog|paramedic|\bEMT\b|dentist|"
    r"dental|psycholog|psychiatr|social worker|counselor|dietitian|respiratory|"
    r"anesthe|midwife|patient care (assistant|associate|tech)|"
    r"engineer|developer|architect|scientist|programmer|devops|"
    r"attorney|\bcounsel\b|chief|president|\bVP\b|\bAVP\b|\bSVP\b|\bEVP\b|director|"
    r"\bintern\b|internship|co-?op\b|fellow(ship)?\b|resident\b|student|"
    r"sales|driver|housekeep|food service|cook\b|security officer|maintenance", re.I)

# Employers left off this list by choice: contract research organisations, which
# run clinical trials on behalf of drug and device companies. A listing from any
# source is dropped when its employer matches. Clinical research roles at
# hospitals, universities and drug companies themselves are not affected.
BLOCKED_EMPLOYERS = re.compile(
    r"\bICON\b|\bIQVIA\b|syneos|parexel|fortrea|\bPPD\b|thermo fisher|"
    r"\bCTI\b|clinical trial and consulting|worldwide clinical trials|premier research|"
    r"precision (for medicine|medicine group)|science 37|\bPRA health|covance|"
    r"charles river|\bPSI CRO\b|catalyst clinical research|\bemmes\b|allucent|ergomed|"
    r"\bTFS healthscience|novotech|propharma|caidya|\brho\b,? inc|alimentiv|\bKCR\b|"
    r"advanced clinical|veristat|\bcytel\b|\blinical\b|george clinical|frontage|"
    r"altasciences|celerion|\bQPS\b|pharm-olam|clinipace|medpace research", re.I)


def blocked(company: str) -> bool:
    return bool(BLOCKED_EMPLOYERS.search(company or ""))


SENIOR = re.compile(r"\bsenior\b|\bsr\b\.?|\blead\b|principal|manager|supervisor|"
                    r"\bIII\b|\bIV\b|\bV\b|expert|\bhead\b|consultant", re.I)
ENTRY = re.compile(r"associate|assistant|coordinator|representative|\bI\b|\b1\b|"
                   r"entry|junior|\bjr\b|trainee|new grad|apprentice|clerk", re.I)


def relevant(title: str, broad_ok: bool = True) -> bool:
    title = title or ""
    if EXCLUDE.search(title):
        return False
    return bool(STRICT.search(title)) or (broad_ok and bool(BROAD.search(title)))


def level_of(title: str) -> str:
    if SENIOR.search(title or ""):
        return "Senior"
    if ENTRY.search(title or ""):
        return "Entry"
    return ""


TRACKS = [
    ("Health Information", re.compile(
        r"health information|\bHIMS?\b|medical records?|release of information|"
        r"regist(rar|ry)|data (quality|integrity|governance)|\bEpic\b|\bEHR\b|\bEMR\b", re.I)),
    ("Coding and CDI", re.compile(
        r"\bcod(er|ing)\b|\bCDI\b|clinical documentation|\bDRG\b|\bHCC\b|risk adjustment", re.I)),
    ("Revenue Cycle", re.compile(
        r"revenue|reimbursement|denials?\b|appeals?\b|charge|\bCDM\b|pricing|billing|"
        r"claims?\b|payer|managed care|contracts?\b|financial|insurance verification|"
        r"prior authori|pre.?cert", re.I)),
    ("Clinical Research", re.compile(
        r"clinical (research|trials?|study|operations)|study (coordinator|start)|"
        r"regulatory|patient concierge|site (activation|management)", re.I)),
    ("Data and Analytics", re.compile(
        r"analyst|analytics|informatics|reporting|health data|clinical data", re.I)),
    ("Compliance and Quality", re.compile(
        r"compliance|privacy|\bHIPAA\b|audit|quality|credentialing|utilization", re.I)),
    ("Patient Services", re.compile(
        r"patient (access|financial|accounts?|concierge|registration|services)|"
        r"account coordinator|scheduling", re.I)),
]


def tracks_of(title: str) -> List[str]:
    return [name for name, pat in TRACKS if pat.search(title or "")]


# ── where ───────────────────────────────────────────────────────────────────
# Towns within about 45 minutes of the north side of Cincinnati. Each needs its state next to it,
# because Mason, Hamilton, Florence, Loveland and West Chester all exist
# elsewhere. "Cincinnati" alone is enough.
_OH_TOWNS = (
    "Blue Ash|Mason|West Chester|Sharonville|Montgomery|Loveland|Milford|Fairfield|"
    "Hamilton|Springdale|Norwood|Evendale|Kenwood|Madeira|Lebanon|Monroe|Middletown|"
    "Liberty Township|Liberty Twp|Batavia|Harrison|Forest Park|Anderson|Mariemont|"
    "Reading|Springboro|Franklin|Maineville|Deerfield|Symmes|Oakley|Hyde Park|"
    "Westwood|Cheviot|Colerain|Finneytown|Glendale|Wyoming|Woodlawn|Fairfax|"
    "Mount Healthy|Mt\\.? Healthy|Delhi|Amelia|Eastgate|South Lebanon|Trenton|"
    "Indian Hill|Deer Park|Silverton|Rossmoyne|Landen|Kings Mills|Miami Township")
_KY_TOWNS = (
    "Florence|Covington|Newport|Erlanger|Edgewood|Fort Thomas|Ft\\.? Thomas|"
    "Fort Mitchell|Ft\\.? Mitchell|Fort Wright|Crestview Hills|Highland Heights|"
    "Hebron|Union|Independence|Cold Spring|Burlington|Bellevue|Dayton|Alexandria|"
    "Walton|Northern Kentucky")
_IN_TOWNS = "Lawrenceburg|Greendale|Aurora"
_OH = r"(?:\bOH\b|Ohio)"
_KY = r"(?:\bKY\b|Kentucky)"
_IN = r"(?:\bIN\b|Indiana)"
LOCAL = re.compile(
    rf"cincinnati|greater cincinnati|\b(?:{_OH_TOWNS})\b[^;|]{{0,25}}{_OH}|"
    rf"{_OH}[^;|]{{0,6}}\b(?:{_OH_TOWNS})\b|"
    rf"\b(?:{_KY_TOWNS})\b[^;|]{{0,25}}{_KY}|{_KY}[^;|]{{0,6}}\b(?:{_KY_TOWNS})\b|"
    rf"\b(?:{_IN_TOWNS})\b[^;|]{{0,25}}{_IN}", re.I)
# About an hour away. Shown, and tagged as such, so it can be filtered out.
_DAYTON_TOWNS = ("Dayton|Kettering|Beavercreek|Miamisburg|Centerville|Fairborn|"
                 "Huber Heights|Vandalia|Oxford|Moraine|West Carrollton|Englewood|"
                 "Xenia|Troy|Wilmington")
NEARBY = re.compile(rf"\b(?:{_DAYTON_TOWNS})\b[^;|]{{0,25}}{_OH}|"
                    rf"{_OH}[^;|]{{0,6}}\b(?:{_DAYTON_TOWNS})\b", re.I)
REMOTE = re.compile(r"\bremote\b|work from home|work.at.home|\bWFH\b|virtual|telecommut|"
                    r"\banywhere\b|home.based|nationwide", re.I)
# A location that hides the detail, such as "3 Locations". These are looked up.
VAGUE = re.compile(r"^\s*(\d+\s+locations?|multiple( locations)?|various|see (job )?description)?\s*$",
                   re.I)


def areas_of(locations: List[str]) -> List[str]:
    """Which of Cincinnati area / Dayton area / Remote the locations cover."""
    out = []
    for loc in locations:
        if LOCAL.search(loc):
            out.append("Cincinnati area")
        elif NEARBY.search(loc):
            out.append("Dayton area")
        if REMOTE.search(loc):
            out.append("Remote")
    return sorted(set(out), key=["Cincinnati area", "Remote", "Dayton area"].index)


def location_fits(locations: List[str]) -> bool:
    return bool(areas_of(locations))


def location_unknown(locations: List[str]) -> bool:
    return not locations or all(VAGUE.match(loc or "") for loc in locations)

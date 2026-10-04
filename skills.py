"""skills.py — the vocabulary used to compare a posting with a resume.

A posting and a resume are both reduced to the set of vocabulary terms they
mention. Matching then works on those sets, so "ICD-10" in a posting lines up
with "ICD-10" on a resume no matter how either sentence is worded.

Each entry is  canonical name -> regular expression.  Patterns ignore case,
except that a short acronym written in capitals (CDI, ROI, CMS) only counts when
it is capitalised in the text. To teach the matcher a new skill, add one line.
"""
from __future__ import annotations

import re
from typing import Dict, Set

VOCAB: Dict[str, str] = {
    # ── credentials ──
    "RHIA": r"\bRHIA\b",
    "RHIT": r"\bRHIT\b",
    "CCS": r"\bCCS(-P)?\b|certified coding specialist",
    "CPC": r"\bCPC\b|certified professional coder|\bAAPC\b",
    "CCA": r"\bCCA\b",
    "CDIP/CCDS": r"\bCDIP\b|\bCCDS\b",
    "CHDA": r"\bCHDA\b",
    "CHPS": r"\bCHPS\b|\bCHC\b",
    "AHIMA": r"\bAHIMA\b",
    "HFMA": r"\bHFMA\b|\bCRCR\b|healthcare financial management association",
    "CTR": r"\bCTR\b|certified tumor registrar|\bODS\b",
    "bachelor's degree": r"bachelor'?s?( degree)?|\bB\.?[AS]\.?\b(?= (degree|in))|undergraduate degree",
    "HIM degree": r"degree in health information|health information management (degree|program)|\bCAHIIM\b",
    # ── health information ──
    "health information management": r"health information management|\bHIMS?\b|health information",
    "medical records": r"medical records?|health records?|patient records?|chart (review|abstraction)|abstract(ing|ion)",
    "release of information": r"release of information|\bROI\b(?= (request|specialist|process))|records requests?",
    "record retention": r"record(s)? (retention|management|retrieval)|document (management|imaging)|scanning|indexing",
    "data quality": r"data (quality|integrity|accuracy|validation|governance)|quality of data",
    "master patient index": r"master patient index|\bMPI\b|duplicate (records|medical)",
    "registry": r"(cancer|tumor|trauma) regist(rar|ry)|registry data",
    # ── coding and CDI ──
    "medical coding": r"medical cod(ing|er)|\bcod(ing|ers?)\b|code assignment",
    "ICD-10": r"\bICD.?(10|9|11)(.?(CM|PCS))?\b",
    "CPT": r"\bCPT\b|\bHCPCS\b|\bE/M\b|evaluation and management",
    "DRG": r"\bDRGs?\b|\bMS-DRG\b|\bAPR-DRG\b|\bAPC\b",
    "HCC": r"\bHCCs?\b|risk adjustment|hierarchical condition",
    "inpatient coding": r"inpatient (cod|record|account)|facility coding",
    "outpatient coding": r"outpatient (cod|record|account)|profee|professional fee|ambulatory cod",
    "coding guidelines": r"coding (guidelines|conventions|compliance|policies|standards)|official guidelines",
    "coding audits": r"coding (audit|quality|review|accuracy)|audit(s|ing)? (of )?cod|audits?[^.\n]{0,60}coding",
    "clinical documentation improvement": r"clinical documentation|\bCDI\b|documentation (improvement|integrity)|physician quer",
    "encoder": r"\bencoder\b|\b3M\b|\b360\b(?= encompass)|\bcomputer.assisted coding\b|\bCAC\b|solventum",
    "medical terminology": r"medical terminology|anatomy|physiology|pathophysiology|pharmacology",
    # ── revenue cycle ──
    "revenue cycle": r"revenue (cycle|integrity|recovery)|\bRCM\b",
    "reimbursement": r"reimbursement",
    "denials": r"denials?\b|appeals?\b|denial (management|letters?)",
    "claims": r"\bclaims?\b|remittance|\bEOBs?\b|\bUB-?04\b|\bCMS-?1500\b",
    "medical billing": r"medical billing|\bbilling\b|charge entry|patient accounts?|accounts receivable|\bA/R\b|collections",
    "charge master": r"charge ?(master|description|capture)|\bCDM\b",
    "pricing transparency": r"pric(e|ing) transparency|machine.readable|shoppable",
    "payer contracts": r"payer (contract|agreement)|contract (management|modeling|changes|review|analysis)|managed care|fee schedule",
    "insurance": r"\binsurance\b|\bpayers?\b|health plans?|commercial (payer|insurance)",
    "Medicare/Medicaid": r"medicare|medicaid",
    "CMS regulations": r"\bCMS\b|centers for medicare|regulatory requirements|federal regulations",
    "prior authorization": r"prior authori[sz]ation|pre.?cert|pre.?authori[sz]ation|insurance verification|eligibility",
    "patient access": r"patient (access|registration|scheduling|financial)|\bregistration\b|admitting|front.end",
    "healthcare finance": r"healthcare financ|health care financ|hospital financ|cost report|financial analysis|\bbudget(s|ing)?\b",
    "work queues": r"work ?queues?|\bWQs?\b|worklists?",
    # ── systems ──
    "Epic": r"\bEpic\b",
    "Cerner/Meditech": r"\bcerner\b|\bmeditech\b|oracle health|\ballscripts\b|athena(health)?",
    "EHR": r"\bEHRs?\b|\bEMRs?\b|electronic (health|medical) records?",
    "Excel": r"\bexcel\b|spreadsheets?|pivot tables?|vlookup",
    "Microsoft Office": r"microsoft office|\bMS office\b|\bword\b(?=,| and|/)|powerpoint|outlook|office 365",
    "SQL": r"\bSQL\b",
    "Tableau/Power BI": r"\btableau\b|power\s?bi|\bqlik\b|data visuali[sz]ation|dashboards?",
    "portal administration": r"\bportals?\b|\bsharepoint\b|content management",
    "CTMS/eTMF": r"\bCTMS\b|\beTMF\b|\bTMF\b|\bEDC\b|\bveeva\b|\bmedidata\b",
    # ── analysis ──
    "data analysis": r"data analy(sis|tics|st)|analy[sz]e data|\banalytics\b|statistical analysis",
    "reporting": r"\breport(s|ing)\b|metrics|\bKPIs?\b|scorecards?",
    "auditing": r"\baudit(s|ing|or)?\b",
    "trend analysis": r"trends?( and patterns)?|patterns|root cause",
    "process improvement": r"process improvement|workflow (improvement|redesign|optimization)|lean\b|six sigma|quality improvement",
    # ── compliance ──
    "HIPAA": r"\bHIPAA\b|protected health information|\bPHI\b",
    "privacy": r"privacy|confidential(ity)?|information security",
    "compliance": r"\bcompliance\b|regulatory",
    "policy development": r"polic(y|ies) (development|and procedures?)|develop[^.\n]{0,60}polic|standard operating|\bSOPs?\b",
    "accreditation": r"joint commission|\bTJC\b|accreditation|\bNCQA\b|\bHEDIS\b|\bURAC\b",
    "legislation review": r"legislation|regulations|statut|legal requirements",
    # ── clinical research ──
    "clinical research": r"clinical (research|trials?|stud(y|ies))|\bCRO\b",
    "GCP": r"\bGCP\b|good clinical practice|\bICH\b",
    "IRB": r"\bIRBs?\b|institutional review|ethics committee|informed consent",
    "protocols": r"\bprotocols?\b|schedule of events",
    "study operations": r"study (start.?up|management|coordination|team)|site (management|activation|staff|contacts?)|\bCRAs?\b|\bCTMs?\b|clinical trial manager",
    "sponsor relations": r"\bsponsors?\b",
    "patient travel and reimbursement": r"patient (concierge|travel|stipend)|travel and reimbursement|expense report",
    "regulatory documents": r"regulatory (documents|submissions|binder)|essential documents",
    # ── working with people ──
    "client communication": r"client (communication|relationship|facing|service)|stakeholders?|liais(e|on|ing)",
    "account management": r"account (management|coordinat|executive)",
    "project coordination": r"project (management|coordinat|timelines?)|deliverables|timelines",
    "training": r"\btrain(ing)?\b|onboard(ing)?|educat(e|ion|ing) (staff|providers|physicians)",
    "customer service": r"customer service|patient experience|service excellence",
    "cross-functional": r"cross.functional|interdisciplinary|collaborat",
    "marketing": r"marketing|campaigns?|brand",
    "vendor management": r"vendor",
    "provider relations": r"physicians?|providers?|clinicians?",
    "written communication": r"written (and verbal )?communication|correspondence|letters",
    "attention to detail": r"attention to detail|detail.oriented|accuracy",
    # ── settings ──
    "hospital setting": r"\bhospitals?\b|medical center|health system|acute care|inpatient",
    "payer setting": r"health plan|managed care organization|insurance company",
    "pharma/CRO setting": r"pharmaceutical|biotech|\bCRO\b|life sciences|medical device",
    "healthcare industry": r"healthcare|health care",
}

# These are bare words that are ordinary English in lowercase.
_STRICT: Set[str] = set()
_ACRONYM = re.compile(r"\\b([A-Z][A-Z0-9/-]{1,6}(?:s\?)?)\\b")


def _compile(name: str, pattern: str) -> "re.Pattern":
    if name in _STRICT:
        return re.compile(pattern)
    return re.compile(_ACRONYM.sub(lambda m: "(?-i:\\b" + m.group(1) + "\\b)", pattern), re.I)


# A term on the left, when it is on the RESUME, also counts as the terms on the
# right. A resume with the RHIA credential has health information management,
# even if a posting only says "HIM". This is applied to the resume side only.
IMPLIES: Dict[str, list] = {
    "RHIA": ["health information management", "HIM degree", "bachelor's degree",
             "AHIMA", "HIPAA", "privacy", "medical terminology", "medical coding",
             "data quality", "medical records", "EHR", "compliance"],
    "HIM degree": ["health information management", "bachelor's degree"],
    "ICD-10": ["medical coding", "coding guidelines"],
    "coding guidelines": ["medical coding"],
    "coding audits": ["medical coding", "auditing"],
    "inpatient coding": ["medical coding", "hospital setting"],
    "Epic": ["EHR"],
    "HFMA": ["healthcare finance", "revenue cycle"],
    "denials": ["revenue cycle", "claims", "insurance"],
    "pricing transparency": ["CMS regulations", "charge master", "reimbursement"],
    "payer contracts": ["insurance", "reimbursement"],
    "reimbursement": ["revenue cycle"],
    "patient travel and reimbursement": ["clinical research"],
    "study operations": ["clinical research", "pharma/CRO setting"],
    "clinical documentation improvement": ["medical records"],
    "work queues": ["EHR"],
}

_COMPILED = {name: _compile(name, pat) for name, pat in VOCAB.items()}


def extract(text: str) -> Set[str]:
    """Every vocabulary term mentioned in `text`."""
    if not text:
        return set()
    return {name for name, pat in _COMPILED.items() if pat.search(text)}


def expand(terms: Set[str]) -> Set[str]:
    """Add what the terms imply. Used for the resume, never for a posting."""
    out = set(terms)
    grew = True
    while grew:
        grew = False
        for t in list(out):
            for extra in IMPLIES.get(t, []):
                if extra not in out:
                    out.add(extra)
                    grew = True
    return out

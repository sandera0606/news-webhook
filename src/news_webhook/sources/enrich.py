from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import requests

from .base import Article

UNPAYWALL = "https://api.unpaywall.org/v2"
PMC_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "news-webhook/0.1"


def _unpaywall_email() -> str | None:
    return os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("NCBI_EMAIL")


def find_oa_pdf_url(doi: str) -> str | None:
    """Use Unpaywall to find a legal open-access copy of a paywalled DOI."""
    email = _unpaywall_email()
    if not email or not doi:
        return None
    try:
        r = requests.get(
            f"{UNPAYWALL}/{doi}",
            params={"email": email},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        best = data.get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url")
    except requests.RequestException:
        return None


def fetch_pmc_fulltext(pmid: str) -> str | None:
    """If a PubMed article has an open PMC counterpart, fetch its plain text."""
    try:
        # Map PMID -> PMC ID
        r = requests.get(
            f"{PMC_EUTILS}/elink.fcgi",
            params={
                "dbfrom": "pubmed",
                "db": "pmc",
                "id": pmid,
                "retmode": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        linksets = r.json().get("linksets", [])
        pmcid = None
        for ls in linksets:
            for db in ls.get("linksetdbs", []):
                if db.get("dbto") == "pmc" and db.get("links"):
                    pmcid = db["links"][0]
                    break
            if pmcid:
                break
        if not pmcid:
            return None

        r2 = requests.get(
            f"{PMC_EUTILS}/efetch.fcgi",
            params={"db": "pmc", "id": pmcid, "retmode": "xml"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if r2.status_code != 200:
            return None
        return _pmc_xml_to_text(r2.text)
    except requests.RequestException:
        return None


def _pmc_xml_to_text(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    body = root.find(".//body")
    if body is None:
        return None
    chunks: list[str] = []
    for p in body.iter("p"):
        text = "".join(p.itertext()).strip()
        if text:
            chunks.append(text)
    return "\n\n".join(chunks) if chunks else None


def enrich(article: Article) -> Article:
    """Attach `full_text` from PMC (if available) or skip silently."""
    if article.full_text:
        return article
    if article.pmid:
        text = fetch_pmc_fulltext(article.pmid)
        if text:
            article.full_text = text
            return article
    # We don't auto-download PDFs from Unpaywall (binary, fragile),
    # but expose the URL so logs can show it if useful.
    return article

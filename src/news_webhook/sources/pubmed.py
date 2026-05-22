from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from typing import Iterable

import requests

from .base import Article

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "news-webhook/0.1 (+https://github.com/)"


def _params(extra: dict[str, str]) -> dict[str, str]:
    p = {"tool": "news-webhook", "email": os.environ.get("NCBI_EMAIL", "")}
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        p["api_key"] = api_key
    p.update(extra)
    return {k: v for k, v in p.items() if v}


def esearch(query: str, retmax: int, sort: str) -> list[str]:
    sort_param = "relevance" if sort == "relevance" else "pub+date"
    r = requests.get(
        f"{EUTILS}/esearch.fcgi",
        params=_params({
            "db": "pubmed",
            "term": query,
            "retmax": str(retmax),
            "sort": sort_param,
            "retmode": "json",
        }),
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def efetch(pmids: Iterable[str]) -> list[Article]:
    pmids = list(pmids)
    if not pmids:
        return []
    r = requests.get(
        f"{EUTILS}/efetch.fcgi",
        params=_params({
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }),
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    r.raise_for_status()
    return _parse_pubmed_xml(r.text)


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _parse_pubmed_xml(xml_text: str) -> list[Article]:
    root = ET.fromstring(xml_text)
    out: list[Article] = []
    for art in root.findall(".//PubmedArticle"):
        pmid = _text(art.find(".//PMID")) or ""
        title = _text(art.find(".//ArticleTitle"))
        abstract_parts = [_text(p) for p in art.findall(".//Abstract/AbstractText")]
        abstract = "\n".join(p for p in abstract_parts if p)

        doi = ""
        for aid in art.findall(".//ArticleId"):
            if aid.attrib.get("IdType") == "doi":
                doi = (aid.text or "").strip()
                break

        authors: list[str] = []
        for a in art.findall(".//Author"):
            last = _text(a.find("LastName"))
            initials = _text(a.find("Initials"))
            if last:
                authors.append(f"{last} {initials}".strip())

        pub_year = _text(art.find(".//PubDate/Year")) or _text(art.find(".//PubDate/MedlineDate"))[:4]
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else "")

        out.append(
            Article(
                id=f"pmid:{pmid}" if pmid else f"doi:{doi}",
                title=title,
                url=url,
                summary=abstract,
                source="PubMed",
                authors=authors,
                published=pub_year or None,
                doi=doi or None,
                pmid=pmid or None,
            )
        )
    return out


def fetch_pubmed(query: str, max_articles: int, sort: str) -> list[Article]:
    pmids = esearch(query, retmax=max(max_articles * 3, max_articles), sort=sort)
    # Be polite to NCBI between the two calls.
    time.sleep(0.34)
    return efetch(pmids[: max_articles * 3])

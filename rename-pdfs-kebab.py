#!/usr/bin/env python3
# all-kebab-case pdf renamer with metadata-first, first-page fallback, doi->crossref,
# joint-first-author handling, and body-area/condition tags.
# matt: defaults tuned for clinical research libraries.

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Dict

try:
    import fitz  # pymupdf
except Exception:
    print(
        "Missing dependency 'pymupdf' (import name 'fitz'). Install it with: pip install pymupdf",
        file=sys.stderr,
    )
    sys.exit(1)
from urllib import request, parse, error as urlerror


# ---------- text utils ----------

def to_kebab(text: str) -> str:
    if text is None:
        return ""
    s = text.lower()
    s = re.sub(r"[^\w\s\-]+", " ", s)   # drop punctuation (keep hyphens)
    s = re.sub(r"[_]+", " ", s)         # underscores -> spaces
    s = re.sub(r"\s+", "-", s.strip())  # spaces -> hyphen
    s = re.sub(r"-{2,}", "-", s)        # collapse multiple hyphens
    return s.strip("-")


def surname_from_author(a: str) -> str:
    a = a.strip()
    if "," in a:  # "last, first"
        return a.split(",")[0].strip()
    tokens = a.split()
    return tokens[-1] if tokens else a


def pick_year_from_text(text: str) -> Optional[str]:
    m = re.findall(r"(19|20)\d{2}", text)
    return m[0] if m else None


# ---------- body-area / condition tagging (simple keyword map) ----------

BODY_AREA_MAP: Dict[str, List[str]] = {
    "shoulder": ["shoulder", "rotator cuff", "supraspinatus", "infraspinatus"],
    "hip-groin": ["hip", "groin", "fai", "labral", "adductor"],
    "hand-wrist": ["wrist", "carpal", "hand", "de quervain", "tfcc"],
    "lsp": ["lumbar", "low back", "lumbosacral", "lbp"],
    "csp": ["cervical", "neck"],
    "tsp": ["thoracic", "mid back"],
    "headaches": ["headache", "migraine", "cervicogenic"],
    "metacognition": ["metacognition", "bias", "heuristic", "reflective", "cognitive"],
}

CONDITION_MAP: Dict[str, List[str]] = {
    "tendinopathy": ["tendinopathy", "tendinitis", "tendon"],
    "osteoarthritis": ["osteoarthritis", "oa"],
    "acl": ["acl", "anterior cruciate"],
    "instability": ["instability"],
    "adhesive-capsulitis": ["adhesive capsulitis", "frozen shoulder"],
    "radiculopathy": ["radiculopathy", "radicular"],
    "disc-herniation": ["disc herniation", "herniated disc", "disc prolapse"],
    "concussion": ["concussion", "mild traumatic brain injury", "mtbi"],
    "whiplash": ["whiplash"],
    "tmd": ["temporomandibular", "tmd"],
    "headache": ["headache", "migraine", "tension-type"],
}


def infer_tags(text: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    t = text.lower()
    body_area = None
    condition = None

    for area, kws in BODY_AREA_MAP.items():
        if any(k in t for k in kws):
            body_area = area
            break
    for cond, kws in CONDITION_MAP.items():
        if any(k in t for k in kws):
            condition = cond
            break

    extra = []
    if body_area:
        extra.append(body_area)
    if condition:
        extra.append(condition)
    return body_area, condition, extra


# ---------- pdf parsing ----------

def parse_pdf_metadata(doc: fitz.Document):
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip() or None
    author = (meta.get("author") or "").strip() or None
    year = None
    for key in ("creationDate", "modDate"):
        v = meta.get(key) or ""
        m = re.search(r"(19|20)\d{2}", v)
        if m:
            year = m.group(0)
            break

    authors_list = None
    if author:
        parts = re.split(r"[;,]| and ", author, flags=re.IGNORECASE)
        authors_list = [p.strip() for p in parts if p.strip()]

    return title, authors_list, year


def extract_first_pages(doc: fitz.Document, pages: int = 3) -> str:
    chunks = []
    for i in range(min(len(doc), pages)):
        try:
            chunks.append(doc[i].get_text())
        except Exception:
            pass
    return "\n".join(chunks)


def infer_from_first_page(doc: fitz.Document):
    # try structured spans first to find a plausible title
    try:
        page = doc[0]
    except Exception:
        return None, None, None, False

    d = page.get_text("dict")
    spans = []
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = (span.get("text") or "").strip()
                if txt:
                    spans.append((span.get("size", 0.0), txt, span.get("origin", (0, 0))[1]))

    title = None
    if spans:
        spans_sorted = sorted(spans, key=lambda x: x[0], reverse=True)
        top_sizes = sorted({s for s, _, _ in spans_sorted[:60]}, reverse=True)[:3]
        candidates = [(s, t, y) for (s, t, y) in spans if s in top_sizes and len(t) > 10]
        candidates.sort(key=lambda x: (x[2], -len(x[1])))
        title = candidates[0][1] if candidates else None

    # authors: look lines near the title y with commas/initials
    authors = None
    joint_first = False
    if spans and title:
        title_y = next(y for (s, t, y) in candidates if t == title)
        near = [t for (s, t, y) in spans if y > title_y and (y - title_y) < 220]
        for line in near:
            if looks_like_authors(line):
                authors = split_authors(line)
                break

    # year and joint-first phrases from first 3 pages
    text3 = extract_first_pages(doc, pages=3)
    year = pick_year_from_text(text3)
    joint_first = bool(re.search(r"(contributed equally|co[-\s]?first author)", text3, re.IGNORECASE))

    # clean
    if title:
        title = re.sub(r"\s+", " ", title).strip()

    return title or None, authors, year, joint_first


def looks_like_authors(line: str) -> bool:
    if len(line) > 200:
        return False
    comma_count = line.count(",")
    has_initials = bool(re.search(r"\b[A-Z]\.", line))
    has_and = " and " in line.lower()
    return (comma_count >= 1 or has_initials or has_and)


def split_authors(line: str) -> List[str]:
    parts = re.split(r"[;,]| and ", line, flags=re.IGNORECASE)
    out = []
    for p in parts:
        p = re.sub(r"\(.*?\)|\[.*?\]|\<.*?\>", "", p).strip()
        if p:
            out.append(p)
    # dedupe
    seen = set()
    keep = []
    for a in out:
        key = a.lower()
        if key not in seen:
            keep.append(a)
            seen.add(key)
    return keep


# ---------- doi + crossref ----------

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)

def find_doi(text: str) -> Optional[str]:
    m = DOI_RE.search(text)
    if not m:
        return None
    return m.group(0).strip().strip(".")


def fetch_crossref(doi: str) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
    """return title, authors, year from crossref; all raw (not kebab)."""
    try:
        url = f"https://api.crossref.org/works/{parse.quote(doi)}"
        req = request.Request(url, headers={"User-Agent": "uon-pdf-renamer/1.0 (mailto:unknown@example.com)"})
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data.get("message", {})
        title = None
        if isinstance(msg.get("title"), list) and msg["title"]:
            title = msg["title"][0]
        # authors: family, given
        authors = []
        for a in msg.get("author", []) or []:
            family = a.get("family") or ""
            given = a.get("given") or ""
            if family and given:
                authors.append(f"{family}, {given}")
            elif family:
                authors.append(family)
        year = None
        # prefer issued.year
        for key in ("issued", "published-print", "published-online"):
            d = msg.get(key, {})
            if isinstance(d.get("date-parts"), list) and d["date-parts"]:
                cand = d["date-parts"][0]
                if cand and len(cand) > 0:
                    year = str(cand[0])
                    break
        return title or None, authors or None, year or None
    except Exception:
        return None, None, None


# ---------- filename assembly ----------

def build_filename(authors: Optional[List[str]], year: Optional[str], title: Optional[str],
                   joint_first: bool, style: str) -> Optional[str]:
    if not title:
        return None

    # author piece
    if authors and len(authors) > 0:
        first_surname = to_kebab(surname_from_author(authors[0]))
        author_piece = first_surname
        if joint_first and len(authors) >= 2:
            second_surname = to_kebab(surname_from_author(authors[1]))
            author_piece = f"{first_surname}-{second_surname}"
        elif len(authors) > 1:
            author_piece = f"{first_surname}-et-al"
    else:
        author_piece = "unknown-author"

    year_piece = year if year else "unknown-year"
    title_piece = to_kebab(title)

    if style == "author-year-title":
        base = f"{author_piece}-{year_piece}-{title_piece}"
    elif style == "year-author-title":
        base = f"{year_piece}-{author_piece}-{title_piece}"
    else:
        base = f"{author_piece}-{year_piece}-{title_piece}"

    if len(base) > 180:
        base = base[:180].rstrip("-")
    return base + ".pdf"


def update_metadata(doc: fitz.Document, title: Optional[str], authors: Optional[List[str]],
                    year: Optional[str], tags: List[str], force_overwrite: bool) -> Dict[str, Tuple[Optional[str], str]]:
    meta = doc.metadata or {}
    changed = {}

    def set_field(k, v):
        nonlocal meta, changed
        if v is None:
            return
        if not meta.get(k) or force_overwrite:
            old = meta.get(k)
            meta[k] = v
            changed[k] = (old, v)

    title_k = to_kebab(title) if title else None
    author_k = to_kebab("; ".join(authors)) if authors else None
    kw_set = [to_kebab(t) for t in tags if t]
    keywords_k = ", ".join(kw_set) if kw_set else None

    set_field("title", title_k)
    set_field("author", author_k)
    set_field("keywords", keywords_k)

    doc.set_metadata(meta)
    return changed


def unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    i = 2
    while True:
        cand = target.with_name(f"{stem}-{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1


# ---------- main processing ----------

def process_pdf(path: Path, style: str, apply: bool, force_overwrite: bool) -> dict:
    res = {
        "old_path": str(path),
        "new_path": "",
        "title_source": "",
        "authors_source": "",
        "year_source": "",
        "doi": "",
        "tags": "",
        "status": "ok",
        "error": "",
        "format_used": style
    }

    try:
        with fitz.open(path) as doc:
            # metadata
            m_title, m_authors, m_year = parse_pdf_metadata(doc)

            # first pages text
            text3 = extract_first_pages(doc, pages=3)

            # doi + crossref
            doi = find_doi(text3)
            res["doi"] = doi or ""
            c_title = c_authors = c_year = None
            if doi:
                c_title, c_authors, c_year = fetch_crossref(doi)

            # first-page inference
            f_title = f_authors = f_year = None
            joint_first = False
            if not (m_title and m_authors and m_year):
                f_title, f_authors, f_year, joint_first = infer_from_first_page(doc)

            # choose best
            title = c_title or m_title or f_title
            authors = c_authors or m_authors or f_authors
            year = c_year or m_year or f_year

            res["title_source"] = "crossref" if c_title else ("metadata" if m_title else ("first-page" if f_title else ""))
            res["authors_source"] = "crossref" if c_authors else ("metadata" if m_authors else ("first-page" if f_authors else ""))
            res["year_source"] = "crossref" if c_year else ("metadata" if m_year else ("first-page" if f_year else ""))

            # tags
            body_area, condition, extra = infer_tags(text3)
            tags = []
            # base tags from authors/year/title for findability
            if authors:
                tags.append(to_kebab(surname_from_author(authors[0])))
                if len(authors) > 1:
                    tags.append("et-al")
            if year:
                tags.append(year)
            # clinical tags
            tags.extend(extra)
            res["tags"] = ";".join(sorted(set(tags)))

            # filename
            new_name = build_filename(authors, year, title, joint_first, style)
            if not new_name:
                res["status"] = "skipped"
                res["error"] = "could-not-build-filename"
                return res

            new_path = path.with_name(new_name)
            new_path = unique_path(new_path)
            res["new_path"] = str(new_path)

            # write metadata (kebab-case), add tags
            changes = update_metadata(doc, title, authors, year, tags, force_overwrite)

            if apply:
                if changes:
                    # incremental save will keep xref clean
                    doc.saveIncr()
                if str(new_path) != str(path):
                    os.replace(path, new_path)

    except Exception as e:
        res["status"] = "error"
        res["error"] = to_kebab(str(e))

    return res


def main():
    parser = argparse.ArgumentParser(
        description="rename research pdfs using metadata-first + first-page fallback + doi->crossref; write kebab-case metadata and tags."
    )
    parser.add_argument("--root", required=True, help="root-folder to scan (recursively)")
    parser.add_argument("--apply", action="store_true", help="actually write changes (default: dry-run)")
    parser.add_argument("--force-overwrite-metadata", action="store_true", help="overwrite non-empty metadata fields")
    parser.add_argument("--style", choices=["author-year-title", "year-author-title"], default="author-year-title",
                        help="filename style (default: author-year-title)")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"root-not-found: {root}", file=sys.stderr)
        sys.exit(1)

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = root / f"rename-log-{ts}.csv"

    rows = []
    count = 0
    for p in root.rglob("*"):
        # case-insensitive PDF detection (handles .PDF, .Pdf, etc.)
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue
        res = process_pdf(p, style=args.style, apply=args.apply, force_overwrite=args.force_overwrite_metadata)
        rows.append(res)
        count += 1
        if count % 25 == 0:
            print(f"processed: {count} files...", file=sys.stderr)
        # print a short dry-run preview for quick verification
        if not args.apply and res.get("status") == "ok" and res.get("new_path"):
            print(f"DRY-RUN: {res['old_path']} -> {res['new_path']} (source={res.get('title_source')})", file=sys.stderr)

    # csv
    fields = ["old_path", "new_path", "title_source", "authors_source", "year_source", "doi", "tags", "format_used", "status", "error"]
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    changed = sum(1 for r in rows if r["status"] == "ok" and r["new_path"])
    errors = sum(1 for r in rows if r["status"] == "error")
    skipped = sum(1 for r in rows if r["status"] == "skipped")
    mode = "apply" if args.apply else "dry-run"
    print(f"log-written: {log_path}")
    print(f"summary: mode={mode} total={len(rows)} changed-or-would-change={changed} skipped={skipped} errors={errors}")


if __name__ == "__main__":
    main()

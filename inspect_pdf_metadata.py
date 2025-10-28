#!/usr/bin/env python3
"""Inspect PDFs using improved heuristics without mutating files.

Usage: run this script to print embedded metadata, inferred values from text,
and heuristic improvements (author from keywords, title plausibility, body-area/condition mapping).
"""
import re
import sys
try:
    import fitz
except Exception:
    fitz = None


def is_plausible_title(t: str) -> bool:
    if not t:
        return False
    t = t.strip()
    if len(t) < 8:
        return False
    # reject short codes like CJSM-22-275 or similar
    if re.search(r'^[A-Z]{2,}[-_]?\d', t):
        return False
    # reject strings that are mostly punctuation or numbers
    letters = len(re.findall(r'[A-Za-z]', t))
    if letters < 4:
        return False
    return True


def normalize_author_to_lastname(author_str: str) -> str:
    if not author_str:
        return 'unknown'
    s = re.sub(r'[\(\)\[\],;]', ' ', author_str)
    parts = [p for p in s.replace('-', ' ').split() if p]
    if not parts:
        return 'unknown'
    lastname = parts[-1].lower()
    lastname = re.sub(r'[^a-z0-9\-]', '', lastname)
    return lastname or 'unknown'


def extract_author_from_keywords(kw: str) -> str:
    if not kw:
        return ''
    parts = [p.strip() for p in re.split('[,;]', kw) if p.strip()]
    # look for parts that look like a surname (contains letters and maybe hyphen)
    for p in parts:
        # common pattern van-meer or van meer
        clean = p.replace('-', ' ').strip()
        tokens = clean.split()
        if len(tokens) <= 3 and any(len(t) > 2 for t in tokens):
            # return last token as probable surname
            return normalize_author_to_lastname(clean)
    return ''


BODY_MAP = {
    'knee': ['knee','acl','anterior cruciate','tibiofemoral','patellofemoral'],
    'hip-groin': ['hip','groin','iliopsoas','femoroacetabular','fai'],
    'lumbar': ['lumbar','spine','back'],
}

CONDITION_MAP = {
    'tendinopathy': ['tendinopathy','tendon','tendinous','tendinous'],
    'acl': ['acl','anterior cruciate','anterior cruciate ligament'],
    'osteoporosis': ['osteoporosis','bone stress','bone stress injury','nonunited defect'],
}


def map_tag(text: str, mapping: dict) -> str:
    t = text.lower()
    for key, kws in mapping.items():
        for k in kws:
            if k in t:
                return key
    return ''


def inspect(path: str) -> None:
    print('\n===', path)
    if fitz is None:
        print('PyMuPDF (fitz) not available')
        return
    try:
        doc = fitz.open(path)
    except Exception as e:
        print('ERROR opening:', e)
        return
    meta = doc.metadata or {}
    print('embedded metadata:')
    for k in ('title','author','keywords','creationDate'):
        print(' ',k,':', repr(meta.get(k)))
    # read text
    text = ''
    for i in range(min(3, doc.page_count)):
        try:
            text += '\n' + doc.load_page(i).get_text('text')
        except Exception:
            pass
    text_snip = text[:1200].replace('\n','\\n')
    print('\ntext-snippet:', text_snip[:1000])

    inferred_title = ''
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        inferred_title = lines[0]
    inferred_author = ''
    if len(lines) > 1:
        inferred_author = lines[1]

    # heuristics
    title_use_meta = meta.get('title') if is_plausible_title(meta.get('title') or '') else None
    title_final = title_use_meta or inferred_title or ''

    author_use_meta = meta.get('author') or ''
    if not author_use_meta:
        # try keywords
        author_from_kw = extract_author_from_keywords(meta.get('keywords') or '')
        author_use_meta = author_from_kw or ''
    author_final = author_use_meta or inferred_author or ''

    body_area = map_tag((meta.get('keywords') or '') + '\n' + text, BODY_MAP)
    condition = map_tag((meta.get('keywords') or '') + '\n' + text, CONDITION_MAP)

    print('\nProposed:')
    print(' title_final:', repr(title_final))
    print(' author_final (lastname):', normalize_author_to_lastname(author_final))
    print(' body_area:', body_area)
    print(' condition:', condition)
    doc.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        print('Usage: inspect_pdf_metadata.py <pdf1> <pdf2> ...')
        sys.exit(1)
    for f in files:
        inspect(f)

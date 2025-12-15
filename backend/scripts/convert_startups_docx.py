import re
import csv
import sys
from pathlib import Path
from typing import List, Dict, Optional

from docx import Document

ATS_PATTERNS = {
    "lever": re.compile(r"lever\.co", re.I),
    "greenhouse": re.compile(r"greenhouse\.io|boards\.greenhouse\.io", re.I),
    "workday": re.compile(r"workday|myworkdayjobs", re.I),
}

STATE_ABBR = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"
}

URL_RE = re.compile(r"https?://[^\s)]+", re.I)
CITY_STATE_RE = re.compile(r"([A-Za-z .'-]+),\s*([A-Z]{2})\b")


def detect_scraper_type(url: str) -> str:
    for name, pattern in ATS_PATTERNS.items():
        if pattern.search(url or ""):
            return name
    return "unknown"


def normalize_line(text: str) -> str:
    return (text or "").strip().replace("\u00a0", " ")


def parse_docx(docx_path: Path) -> List[Dict[str, str]]:
    doc = Document(str(docx_path))
    rows: List[Dict[str, str]] = []

    current: Dict[str, str] = {}

    def flush_current():
        nonlocal current
        if any(current.get(k) for k in ("name", "website", "careers_url")):
            # deduce scraper if careers_url present
            if current.get("careers_url") and not current.get("scraper_type"):
                current["scraper_type"] = detect_scraper_type(current["careers_url"])
            # defaults
            current.setdefault("scraper_type", "unknown")
            current.setdefault("city", "")
            current.setdefault("state", "")
            current.setdefault("country", "")
            current.setdefault("role_keywords", "")
            current.setdefault("enabled", "1")
            current.setdefault("notes", "")
            rows.append(current)
        current = {}

    for para in doc.paragraphs:
        line = normalize_line(para.text)
        if not line:
            continue

        urls = URL_RE.findall(line)
        # If line has URLs, assign to careers/website appropriately
        if urls:
            for url in urls:
                if detect_scraper_type(url) != "unknown":
                    current["careers_url"] = url
                    current["scraper_type"] = detect_scraper_type(url)
                else:
                    # if it's likely homepage
                    if not current.get("website"):
                        current["website"] = url
                    else:
                        # if website already set and careers empty, treat as careers
                        current.setdefault("careers_url", url)
            # keep scanning for location on same line
            m = CITY_STATE_RE.search(line)
            if m and m.group(2) in STATE_ABBR:
                current["city"] = m.group(1).strip()
                current["state"] = m.group(2)
            # move on
            continue

        # No URLs: treat as name or location or note
        m = CITY_STATE_RE.search(line)
        if m and m.group(2) in STATE_ABBR:
            current["city"] = m.group(1).strip()
            current["state"] = m.group(2)
            continue

        # Heuristic: a line with 2-4 words likely a company name
        word_count = len([w for w in re.split(r"\s+", line) if w])
        if 1 <= word_count <= 6 and not current.get("name"):
            # If there's an existing record partially filled, flush
            if any(current.get(k) for k in ("name", "website", "careers_url")):
                flush_current()
            current["name"] = line
        else:
            # treat as notes if we already have a name
            if current.get("name"):
                current["notes"] = (current.get("notes", "") + " | " + line).strip(" |")
            else:
                # start a new name anyway
                current["name"] = line

    flush_current()
    return rows


def write_csv(rows: List[Dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "name","website","careers_url","scraper_type","city","state","country","role_keywords","enabled","notes"
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow({h: r.get(h, "") for h in headers})


def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_startups_docx.py <input_docx> <output_csv>")
        sys.exit(1)
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    if not in_path.exists():
        print(f"Input not found: {in_path}")
        sys.exit(1)

    rows = parse_docx(in_path)
    write_csv(rows, out_path)
    print(f"Converted {len(rows)} entries → {out_path}")


if __name__ == "__main__":
    main()


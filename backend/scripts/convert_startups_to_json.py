import re
import json
import sys
from pathlib import Path
from typing import Dict, List

from docx import Document

URL_RE = re.compile(r"https?://[^\s)]+", re.I)
ATS = {
    "lever": re.compile(r"lever\.co", re.I),
    "greenhouse": re.compile(r"greenhouse|boards\.greenhouse\.io", re.I),
    "workday": re.compile(r"workday|myworkdayjobs", re.I),
}

SECTION_REMOTE = re.compile(r"remote", re.I)
SECTION_SF = re.compile(r"\bSF\b|San\s*Francisco|Bay\s*Area", re.I)
SECTION_NY = re.compile(r"\bNY\b|New\s*York", re.I)


def detect_scraper(url: str) -> str:
    for name, rx in ATS.items():
        if rx.search(url or ""):
            return name
    return "unknown"


def make_item(name: str, website: str = "", careers: str = "", notes: str = "") -> Dict:
    return {
        "name": name.strip(),
        "website": website or "",
        "careers_url": careers or "",
        "scraper_type": detect_scraper(careers or website),
        "location_type": "",
        "city": "",
        "state": "",
        "country": "",
        "role_keywords": [],
        "enabled": True,
        "notes": notes.strip(),
    }


def parse_docx(docx_path: Path) -> Dict[str, List[Dict]]:
    doc = Document(str(docx_path))
    sections = {"remote": [], "sf": [], "ny": []}
    current_section = None

    # Heuristics: company lines often start with digits or bullets; otherwise treat first non-empty line after number as name
    buffer = None  # temp collector for current company

    def flush():
        nonlocal buffer
        if buffer and buffer.get("name"):
            if current_section in sections:
                sections[current_section].append(buffer)
        buffer = None

    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if not text:
            continue

        # Section detection
        if SECTION_REMOTE.search(text):
            flush()
            current_section = "remote"
            continue
        if SECTION_SF.search(text):
            flush()
            current_section = "sf"
            continue
        if SECTION_NY.search(text):
            flush()
            current_section = "ny"
            continue

        # Skip if no active section yet
        if current_section is None:
            continue

        # Detect start of a company entry
        starts_company = bool(re.match(r"^(\d+[.)]|[-•])\s+", text)) or (buffer is None)

        urls = URL_RE.findall(text)
        # If new item
        if starts_company:
            flush()
            # strip numbering/bullet
            name_part = re.sub(r"^(\d+[.)]|[-•])\s+", "", text)
            # remove trailing dash phrases commonly used as taglines
            name_only = name_part.split(" – ")[0].split(" — ")[0].split(" - ")[0].strip()
            website = ""
            careers = ""
            if urls:
                # First non-ATS URL as website, ATS URL as careers
                for u in urls:
                    if detect_scraper(u) == "unknown" and not website:
                        website = u
                    elif detect_scraper(u) != "unknown" and not careers:
                        careers = u
                if not website and urls:
                    website = urls[0]
            buffer = make_item(name_only or name_part, website, careers, "")
            buffer["location_type"] = current_section
        else:
            # continuation line: add URLs/notes
            if buffer is None:
                continue
            if urls:
                for u in urls:
                    if detect_scraper(u) != "unknown" and not buffer.get("careers_url"):
                        buffer["careers_url"] = u
                        buffer["scraper_type"] = detect_scraper(u)
                    elif not buffer.get("website"):
                        buffer["website"] = u
            else:
                buffer["notes"] = (buffer.get("notes", "") + " | " + text).strip(" |")

    flush()
    return sections


def write_json(sections: Dict[str, List[Dict]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, items in sections.items():
        out_path = out_dir / f"startups_{key}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"{key}: {len(items)} → {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_startups_to_json.py <input_docx> <output_dir>")
        sys.exit(1)
    docx_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    if not docx_path.exists():
        print(f"Not found: {docx_path}")
        sys.exit(1)

    sections = parse_docx(docx_path)
    write_json(sections, out_dir)


if __name__ == "__main__":
    main()


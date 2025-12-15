import csv
import json
import sys
from pathlib import Path
from typing import Dict

US_STATES = {"MA","RI","CT"}


def parse_city_state(value: str):
    if not value:
        return "", ""
    v = value.replace("/", ",").replace("  ", " ").strip()
    parts = [p.strip() for p in v.split(",") if p.strip()]
    if not parts:
        # try last token as state abbr
        tokens = v.split()
        if tokens and tokens[-1].upper() in US_STATES:
            return " ".join(tokens[:-1]), tokens[-1].upper()
        return v, ""
    # If last token looks like a state abbr
    last = parts[-1].split()[-1].upper()
    if last in US_STATES:
        city = ", ".join(parts)  # keep original
        # try to isolate the last 2-letter token
        city_tokens = parts[-1].split()
        if len(city_tokens) > 1 and city_tokens[-1].upper() in US_STATES:
            parts[-1] = " ".join(city_tokens[:-1]).strip()
        city = ", ".join(parts).strip().rstrip(",")
        state = last
        return city, state
    return v, ""


def convert(csv_path: Path, out_path: Path) -> int:
    items = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Company") or "").strip()
            city_raw = (row.get("City/Region") or "").strip()
            industry = (row.get("Industry") or "").strip()
            desc = (row.get("Description") or "").strip()
            city, state = parse_city_state(city_raw)
            item: Dict = {
                "name": name,
                "website": "",
                "careers_url": "",
                "scraper_type": "unknown",
                "location_type": "boston",
                "city": city,
                "state": state or ("MA" if "MA" in city_raw else ""),
                "country": "USA",
                "role_keywords": [],
                "enabled": True,
                "notes": "; ".join([x for x in [industry, desc] if x]),
            }
            if name:
                items.append(item)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return len(items)


def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_boston_csv_to_json.py <input_csv> <output_json>")
        sys.exit(1)
    count = convert(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"wrote {count} items")


if __name__ == "__main__":
    main()


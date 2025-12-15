import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

SCHEMA_KEYS = [
    "name","website","careers_url","scraper_type","location_type","city","state","country","role_keywords","enabled","notes"
]

LOCATION_MAP = {
    "remote": "remote",
    "sf": "sf",
    "san francisco": "sf",
    "bay area": "sf",
    "ny": "ny",
    "new york": "ny",
}


def normalize_location(loc: str) -> str:
    if not loc:
        return "remote"
    s = loc.strip().lower()
    return LOCATION_MAP.get(s, s)


def row_to_item(row: Dict[str, str]) -> Dict:
    name = (row.get("Startup") or row.get("name") or "").strip()
    desc = (row.get("Description") or row.get("notes") or "").strip()
    loc = normalize_location(row.get("location_type", ""))
    return {
        "name": name,
        "website": "",
        "careers_url": "",
        "scraper_type": "unknown",
        "location_type": loc,
        "city": "",
        "state": "",
        "country": "",
        "role_keywords": [],
        "enabled": True,
        "notes": desc,
    }


def convert(csv_path: Path, out_dir: Path) -> Dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    buckets: Dict[str, List[Dict]] = {"remote": [], "sf": [], "ny": []}

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = row_to_item(row)
            lt = item["location_type"]
            if lt.startswith("sf"):
                lt = "sf"
            elif lt in ("ny", "new york"):
                lt = "ny"
            elif lt == "remote" or lt == "":
                lt = "remote"
            else:
                # default unknown location types to remote for now
                lt = "remote"
            item["location_type"] = lt
            buckets[lt].append(item)

    counts: Dict[str, int] = {}
    for key, items in buckets.items():
        out_path = out_dir / f"startups_{key}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        counts[key] = len(items)
    return counts


def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_startups_csv_to_json.py <input_csv> <output_dir>")
        sys.exit(1)
    csv_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    if not csv_path.exists():
        print(f"Not found: {csv_path}")
        sys.exit(1)
    counts = convert(csv_path, out_dir)
    for k, v in counts.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()


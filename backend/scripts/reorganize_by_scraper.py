#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reorganize startup JSONs by scraper_type instead of location.
Creates new files: ashby_startups.json, greenhouse_startups.json, lever_startups.json, workday_startups.json
"""

import json
import os
from collections import defaultdict

# Path to data directory
data_dir = os.path.join(os.path.dirname(__file__), '../../data')

# Load all existing JSON files
all_startups = []
json_files = [
    'startups_sf.json',
    'startups_boston.json',
    'startups_ny.json',
    'startups_remote.json',
    'startups_mixed.json'
]

print("="*70)
print("REORGANIZING STARTUPS BY SCRAPER TYPE")
print("="*70)
print()

# Load all startups from existing files
for json_file in json_files:
    file_path = os.path.join(data_dir, json_file)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            startups = json.load(f)
            all_startups.extend(startups)
            print(f"Loaded {len(startups):3d} startups from {json_file}")

print(f"\nTotal startups loaded: {len(all_startups)}")
print()

# Group by scraper_type
by_scraper = defaultdict(list)
scraper_counts = defaultdict(int)

for startup in all_startups:
    scraper_type = startup.get('scraper_type', 'unknown')
    by_scraper[scraper_type].append(startup)
    scraper_counts[scraper_type] += 1

# Display statistics
print("Breakdown by scraper type:")
for scraper_type, count in sorted(scraper_counts.items(), key=lambda x: -x[1]):
    print(f"  {scraper_type:15s}: {count:4d} companies")

print()
print("="*70)
print("Creating new JSON files by scraper type...")
print("="*70)
print()

# Save each scraper type to its own file
scraper_files_created = []

for scraper_type, startups_list in by_scraper.items():
    if scraper_type == 'unknown':
        output_file = 'unknown_startups.json'
    else:
        output_file = f'{scraper_type}_startups.json'
    
    output_path = os.path.join(data_dir, output_file)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(startups_list, f, indent=2, ensure_ascii=False)
    
    print(f"Created: {output_file:25s} ({len(startups_list):4d} companies)")
    scraper_files_created.append(output_file)

print()
print("="*70)
print("[SUCCESS] Reorganization complete!")
print("="*70)
print()
print("New JSON files created in data/:")
for filename in scraper_files_created:
    print(f"  + {filename}")

print()
print("Old location-based files preserved:")
for filename in json_files:
    print(f"  - {filename}")

print()
print("Now you can use scraper-specific files for crawling:")
print("  python scripts/crawl_ashby.py    # Uses ashby_startups.json")
print("  python scripts/crawl_greenhouse.py # Uses greenhouse_startups.json")
print("  python scripts/crawl_lever.py      # Uses lever_startups.json")
print("  python scripts/crawl_workday.py    # Uses workday_startups.json")











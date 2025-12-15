#!/usr/bin/env python3
"""Show which Ashby companies were added from SF and NY files"""

import json
import os

data_dir = os.path.join(os.path.dirname(__file__), '../../data')

# Load ashby file
with open(os.path.join(data_dir, 'ashby_startups.json'), 'r', encoding='utf-8') as f:
    ashby_companies = json.load(f)

print("="*80)
print("ASHBY COMPANIES BREAKDOWN")
print("="*80)
print()
print(f"Total Ashby Companies: {len(ashby_companies)}")
print()

# Group by location
by_location = {}
for company in ashby_companies:
    location = company.get('location_type', 'no_location')
    if location not in by_location:
        by_location[location] = []
    by_location[location].append(company['name'])

# Display by location
for location in ['sf', 'ny', 'boston', 'remote', 'no_location', '']:
    if location in by_location:
        companies_list = by_location[location]
        loc_display = location if location else 'no_location'
        print(f"{loc_display.upper()} ({len(companies_list)} companies):")
        for idx, name in enumerate(companies_list, 1):
            print(f"  {idx:2d}. {name}")
        print()

print("="*80)
print("NEWLY ADDED FROM SF/NY FILES (12 new companies):")
print("="*80)

# Show SF additions
print("\nFrom SF file:")
sf_companies = [c for c in ashby_companies if c.get('location_type') == 'sf']
for company in sf_companies:
    print(f"  + {company['name']:30s} - {company['careers_url']}")

print(f"\nTotal SF Ashby companies: {len(sf_companies)}")











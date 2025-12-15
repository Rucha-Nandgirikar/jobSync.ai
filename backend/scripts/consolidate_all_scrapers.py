#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consolidate ALL companies by scraper type from ALL location files.
Identifies scraper type from careers_url and adds to appropriate file without duplicates.
"""

import json
import os
from collections import defaultdict

# Path to data directory
data_dir = os.path.join(os.path.dirname(__file__), '../../data')

# Load all existing JSON files
location_files = [
    'startups_sf.json',
    'startups_boston.json',
    'startups_ny.json',
    'startups_remote.json',
    'startups_mixed.json'
]

print("="*80)
print("CONSOLIDATING ALL COMPANIES BY SCRAPER TYPE")
print("="*80)
print()

# Collect all companies from location files
all_companies = []
for json_file in location_files:
    file_path = os.path.join(data_dir, json_file)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            companies = json.load(f)
            all_companies.extend(companies)
            print(f"Loaded {len(companies):3d} companies from {json_file}")

print(f"\nTotal companies from location files: {len(all_companies)}")
print()

# Identify scraper type from careers_url
scraper_identified = defaultdict(list)
scraper_counts = defaultdict(int)

for company in all_companies:
    careers_url = company.get('careers_url', '').lower()
    name = company.get('name', 'Unknown')
    
    # Identify scraper type from URL
    identified_type = None
    if 'ashbyhq.com' in careers_url:
        identified_type = 'ashby'
    elif 'greenhouse.io' in careers_url or 'greenhouse.com' in careers_url:
        identified_type = 'greenhouse'
    elif 'lever.co' in careers_url:
        identified_type = 'lever'
    elif 'myworkdayjobs.com' in careers_url or 'workday' in careers_url:
        identified_type = 'workday'
    else:
        identified_type = 'unknown'
    
    # Update scraper_type in company data
    company['scraper_type'] = identified_type
    
    scraper_identified[identified_type].append(company)
    scraper_counts[identified_type] += 1

# Display statistics
print("Companies identified by scraper type:")
for scraper_type, count in sorted(scraper_counts.items(), key=lambda x: -x[1]):
    print(f"  {scraper_type:15s}: {count:4d} companies")

print()
print("="*80)
print("Consolidating into scraper-specific files (removing duplicates)...")
print("="*80)
print()

# Function to check if company already exists (by name or URL)
def company_exists(company, existing_list):
    name = company.get('name', '').strip().lower()
    url = company.get('careers_url', '').strip().lower()
    
    for existing in existing_list:
        existing_name = existing.get('name', '').strip().lower()
        existing_url = existing.get('careers_url', '').strip().lower()
        
        # Match by name or URL
        if name and name == existing_name:
            return True
        if url and url == existing_url and url != '':
            return True
    
    return False

# Load existing scraper files
scraper_files = {
    'ashby': 'ashby_startups.json',
    'greenhouse': 'greenhouse_startups.json',
    'lever': 'lever_startups.json',
    'workday': 'workday_startups.json',
    'unknown': 'unknown_startups.json'
}

# Process each scraper type
for scraper_type, filename in scraper_files.items():
    file_path = os.path.join(data_dir, filename)
    
    # Load existing companies
    existing_companies = []
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_companies = json.load(f)
    
    # Get new companies to add
    new_companies = scraper_identified.get(scraper_type, [])
    
    # Add only non-duplicates
    added_count = 0
    for company in new_companies:
        if not company_exists(company, existing_companies):
            existing_companies.append(company)
            added_count += 1
    
    # Save consolidated file
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_companies, f, indent=2, ensure_ascii=False)
    
    duplicates_removed = len(new_companies) - added_count
    print(f"{filename:30s}: {len(existing_companies):4d} total ({added_count:3d} new, {duplicates_removed:3d} duplicates removed)")

print()
print("="*80)
print("[SUCCESS] Consolidation complete!")
print("="*80)
print()
print("Scraper-specific files updated:")
for scraper_type, filename in scraper_files.items():
    file_path = os.path.join(data_dir, filename)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            count = len(json.load(f))
        print(f"  {filename:30s}: {count:4d} companies")

print()
print("Note: All companies preserve their original 'location_type' field.")
print("You can update the database with correct locations later!")











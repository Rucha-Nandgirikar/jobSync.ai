#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update company locations in database from JSON files.
Reads location_type from scraper JSON files and updates the database.
"""

import sys
import os
import asyncio
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.database import get_db
from sqlalchemy import text

async def update_locations():
    """Update company locations from JSON files"""
    
    # Load scraper files
    data_dir = os.path.join(os.path.dirname(__file__), '../../data')
    scraper_files = [
        'ashby_startups.json',
        'greenhouse_startups.json',
        'lever_startups.json',
        'workday_startups.json'
    ]
    
    print("="*80)
    print("UPDATING COMPANY LOCATIONS IN DATABASE")
    print("="*80)
    print()
    
    all_companies = []
    for filename in scraper_files:
        file_path = os.path.join(data_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                companies = json.load(f)
                all_companies.extend(companies)
                print(f"Loaded {len(companies):3d} companies from {filename}")
    
    print(f"\nTotal companies to update: {len(all_companies)}")
    print()
    
    # Get database session
    db = next(get_db())
    
    updated_count = 0
    not_found_count = 0
    no_location_count = 0
    
    print("Updating locations...")
    print("-"*80)
    
    for company in all_companies:
        name = company.get('name')
        location_type = company.get('location_type', '')
        
        if not name:
            continue
        
        if not location_type:
            no_location_count += 1
            continue
        
        try:
            # Update company location in database
            query = text("""
                UPDATE companies 
                SET location = :location_type
                WHERE name = :name
            """)
            
            result = db.execute(query, {
                'name': name,
                'location_type': location_type
            })
            
            if result.rowcount > 0:
                updated_count += 1
                print(f"  Updated: {name:40s} -> {location_type}")
            else:
                not_found_count += 1
                print(f"  Not found: {name}")
        
        except Exception as e:
            print(f"  Error updating {name}: {e}")
    
    db.commit()
    db.close()
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total companies processed: {len(all_companies)}")
    print(f"  Updated in database:     {updated_count}")
    print(f"  Not found in database:   {not_found_count}")
    print(f"  No location in JSON:     {no_location_count}")
    print()
    print("Note: Companies not found in database will be added when you crawl them.")

if __name__ == '__main__':
    asyncio.run(update_locations())











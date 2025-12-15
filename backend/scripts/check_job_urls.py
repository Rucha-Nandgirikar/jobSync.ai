#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check job URLs in database
"""

import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import execute_query

def check_urls():
    """Check URLs in jobs table"""
    print("\n🔍 Checking job URLs in database...\n")
    
    # Check for URLs with /jobs/ in them
    query = """
    SELECT id, title, company, url, external_id
    FROM jobs
    WHERE url LIKE '%/jobs/%'
    LIMIT 10
    """
    
    results = execute_query(query)
    
    if results:
        print(f"❌ Found {len(results)} jobs with '/jobs/' in URL:\n")
        for job in results:
            print(f"ID: {job['id']}")
            print(f"Title: {job['title']}")
            print(f"Company: {job['company']}")
            print(f"External ID: {job['external_id']}")
            print(f"URL: {job['url']}")
            print("-" * 80)
    else:
        print("✅ No jobs with '/jobs/' in URL found")
    
    # Check all URLs
    print("\n📊 Sample of current job URLs:\n")
    query2 = """
    SELECT id, title, company, url, external_id
    FROM jobs
    ORDER BY id DESC
    LIMIT 5
    """
    
    results2 = execute_query(query2)
    for job in results2:
        print(f"✅ {job['title']}")
        print(f"   URL: {job['url']}")
        print()

if __name__ == '__main__':
    try:
        check_urls()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
















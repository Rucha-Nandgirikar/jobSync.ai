#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check specific job in database
"""

import sys
import os

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import execute_query

target_id = "3cf7c15b-760d-44ca-a464-e2e5a364b19b"

print(f"\n🔍 Searching for job with ID: {target_id}\n")

# Check if this job exists in database
query = """
SELECT id, external_id, title, company, url, crawled_at, last_updated
FROM jobs
WHERE external_id = :external_id OR url LIKE :url_pattern
"""

results = execute_query(query, {
    "external_id": target_id,
    "url_pattern": f"%{target_id}%"
})

if results:
    print(f"✅ FOUND IN DATABASE!\n")
    for job in results:
        print(f"Database ID: {job['id']}")
        print(f"External ID: {job['external_id']}")
        print(f"Title: {job['title']}")
        print(f"Company: {job['company']}")
        print(f"URL: {job['url']}")
        print(f"Crawled at: {job['crawled_at']}")
        print(f"Last updated: {job['last_updated']}")
        print("\n❌ This is OLD DATA - the job no longer exists on the website!")
        print("   The URL has the old format with //jobs/ in it.")
else:
    print(f"❌ NOT FOUND in database")
















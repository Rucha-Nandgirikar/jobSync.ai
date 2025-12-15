#!/usr/bin/env python3
"""
Script to display all jobs in the Engineering department
Usage:
    python show_engineering_jobs.py
    python show_engineering_jobs.py --department "Product"
"""

import sys
import os
import argparse

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import execute_query

def show_jobs_by_department(department: str = "engineering"):
    """Display all jobs for a specific department"""
    print(f"\n🔍 Searching for jobs in '{department}' department...\n")
    
    try:
        # Query jobs with department filter (case-insensitive)
        query = """
        SELECT 
            j.id,
            j.title,
            j.company,
            j.location,
            j.department,
            j.job_type,
            j.url,
            j.posting_date,
            j.crawled_at,
            js.name as source_name
        FROM jobs j
        LEFT JOIN job_sources js ON j.source_id = js.id
        WHERE LOWER(j.department) LIKE LOWER(:department)
        ORDER BY j.posting_date DESC, j.crawled_at DESC
        """
        
        results = execute_query(query, {"department": f"%{department}%"})
        
        if not results:
            print(f"❌ No jobs found in '{department}' department")
            print("\n💡 Tip: Check available departments with --list-departments")
            return
        
        print(f"✅ Found {len(results)} jobs in '{department}' department:\n")
        print("=" * 100)
        
        for i, job in enumerate(results, 1):
            print(f"\n{i}. {job['title']}")
            print(f"   🏢 Company: {job['company']}")
            print(f"   📍 Location: {job['location']}")
            print(f"   🏷️  Department: {job['department']}")
            print(f"   💼 Job Type: {job['job_type']}")
            print(f"   📅 Posted: {job['posting_date'] or 'N/A'}")
            print(f"   🔗 URL: {job['url']}")
            print(f"   📥 Source: {job['source_name']}")
            print("-" * 100)
        
        print(f"\n📊 Total: {len(results)} jobs")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def list_all_departments():
    """List all unique departments in the database"""
    print("\n📋 Available departments:\n")
    
    try:
        query = """
        SELECT DISTINCT department, COUNT(*) as job_count
        FROM jobs
        WHERE department IS NOT NULL AND department != ''
        GROUP BY department
        ORDER BY job_count DESC, department
        """
        
        results = execute_query(query)
        
        if not results:
            print("❌ No departments found")
            return
        
        print("=" * 60)
        for dept in results:
            print(f"  • {dept['department']:<30} ({dept['job_count']} jobs)")
        print("=" * 60)
        print(f"\n📊 Total: {len(results)} departments")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    parser = argparse.ArgumentParser(description='Display jobs by department')
    parser.add_argument('--department', '-d', type=str, default='engineering',
                       help='Department name to filter (default: engineering)')
    parser.add_argument('--list-departments', '-l', action='store_true',
                       help='List all available departments')
    
    args = parser.parse_args()
    
    if args.list_departments:
        list_all_departments()
    else:
        show_jobs_by_department(args.department)

if __name__ == '__main__':
    main()
















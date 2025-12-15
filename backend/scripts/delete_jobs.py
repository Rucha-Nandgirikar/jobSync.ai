#!/usr/bin/env python3
"""
Script to delete job records from the database.
Usage:
    python delete_jobs.py --all              # Delete all jobs
    python delete_jobs.py --source-id 1        # Delete jobs from specific source
    python delete_jobs.py --source-type ashby  # Delete jobs from specific source type
"""

import sys
import os
import argparse
import logging

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import execute_delete, execute_query
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_all_jobs():
    """Delete all jobs from the database"""
    logger.info("Deleting all jobs...")
    try:
        # Delete all applications first (due to foreign key constraints)
        applications_deleted = execute_delete("DELETE FROM applications")
        logger.info(f"Deleted {applications_deleted} applications")
        
        # Delete all cover letters (references jobs)
        cover_letters_deleted = execute_delete("DELETE FROM cover_letters")
        logger.info(f"Deleted {cover_letters_deleted} cover letters")
        
        # Delete all jobs
        jobs_deleted = execute_delete("DELETE FROM jobs")
        logger.info(f"✅ Deleted {jobs_deleted} jobs")
        
        return jobs_deleted
    except Exception as e:
        logger.error(f"Error deleting all jobs: {e}")
        raise

def delete_jobs_by_source_id(source_id: int):
    """Delete jobs from a specific source"""
    logger.info(f"Deleting jobs from source_id={source_id}...")
    try:
        # Get source info
        source = execute_query(
            "SELECT name, scraper_type FROM job_sources WHERE id = :source_id",
            {"source_id": source_id}
        )
        if not source:
            logger.error(f"Source ID {source_id} not found")
            return 0
        
        source_name = source[0]['name']
        logger.info(f"Found source: {source_name}")
        
        # Delete applications for these jobs first
        applications_deleted = execute_delete(
            """
            DELETE FROM applications 
            WHERE job_id IN (SELECT id FROM jobs WHERE source_id = :source_id)
            """,
            {"source_id": source_id}
        )
        logger.info(f"Deleted {applications_deleted} applications")
        
        # Delete cover letters for these jobs
        cover_letters_deleted = execute_delete(
            """
            DELETE FROM cover_letters 
            WHERE job_id IN (SELECT id FROM jobs WHERE source_id = :source_id)
            """,
            {"source_id": source_id}
        )
        logger.info(f"Deleted {cover_letters_deleted} cover letters")
        
        # Delete jobs
        jobs_deleted = execute_delete(
            "DELETE FROM jobs WHERE source_id = :source_id",
            {"source_id": source_id}
        )
        logger.info(f"✅ Deleted {jobs_deleted} jobs from {source_name}")
        
        return jobs_deleted
    except Exception as e:
        logger.error(f"Error deleting jobs by source_id: {e}")
        raise

def delete_jobs_by_source_type(scraper_type: str):
    """Delete jobs from sources with a specific scraper type"""
    logger.info(f"Deleting jobs from source_type={scraper_type}...")
    try:
        # Get source IDs
        sources = execute_query(
            "SELECT id, name FROM job_sources WHERE scraper_type = :scraper_type",
            {"scraper_type": scraper_type}
        )
        if not sources:
            logger.error(f"No sources found with type {scraper_type}")
            return 0
        
        source_ids = [s['id'] for s in sources]
        logger.info(f"Found {len(source_ids)} sources: {[s['name'] for s in sources]}")
        
        total_deleted = 0
        for source_id in source_ids:
            deleted = delete_jobs_by_source_id(source_id)
            total_deleted += deleted
        
        logger.info(f"✅ Total deleted: {total_deleted} jobs from {scraper_type} sources")
        return total_deleted
    except Exception as e:
        logger.error(f"Error deleting jobs by source_type: {e}")
        raise

def show_stats():
    """Show current job statistics"""
    try:
        stats = execute_query("""
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(DISTINCT source_id) as total_sources,
                scraper_type,
                COUNT(*) as count
            FROM jobs j
            JOIN job_sources js ON j.source_id = js.id
            GROUP BY scraper_type
        """)
        
        total = execute_query("SELECT COUNT(*) as total FROM jobs")
        logger.info(f"\n📊 Current Job Statistics:")
        logger.info(f"Total jobs: {total[0]['total'] if total else 0}")
        logger.info(f"\nBy scraper type:")
        for stat in stats:
            logger.info(f"  {stat['scraper_type']}: {stat['count']} jobs")
    except Exception as e:
        logger.error(f"Error getting stats: {e}")

def main():
    parser = argparse.ArgumentParser(description='Delete job records from database')
    parser.add_argument('--all', action='store_true', help='Delete all jobs')
    parser.add_argument('--source-id', type=int, help='Delete jobs from specific source ID')
    parser.add_argument('--source-type', type=str, help='Delete jobs from specific source type (ashby, lever, greenhouse, etc.)')
    parser.add_argument('--stats', action='store_true', help='Show job statistics before deletion')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
        return
    
    if not any([args.all, args.source_id, args.source_type]):
        parser.print_help()
        logger.error("\n❌ Please specify --all, --source-id, or --source-type")
        return
    
    # Show stats before deletion
    show_stats()
    
    # Confirmation
    if not args.confirm:
        if args.all:
            response = input("\n⚠️  Are you sure you want to delete ALL jobs? (yes/no): ")
        elif args.source_id:
            response = input(f"\n⚠️  Are you sure you want to delete jobs from source_id={args.source_id}? (yes/no): ")
        elif args.source_type:
            response = input(f"\n⚠️  Are you sure you want to delete jobs from source_type={args.source_type}? (yes/no): ")
        else:
            response = "no"
        
        if response.lower() != 'yes':
            logger.info("Cancelled.")
            return
    
    # Perform deletion
    try:
        if args.all:
            delete_all_jobs()
        elif args.source_id:
            delete_jobs_by_source_id(args.source_id)
        elif args.source_type:
            delete_jobs_by_source_type(args.source_type)
        
        # Show final stats
        logger.info("\n📊 Final Statistics:")
        show_stats()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

















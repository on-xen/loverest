#!/usr/bin/env python
"""
Migration diagnostic tool for the Love Restaurant bot.
This script checks alembic migration status and helps diagnose issues.
"""

import sys
import os
import argparse
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
import sqlalchemy as sa
from sqlalchemy import create_engine

def get_database_url():
    """Get database URL from environment or use default for local development."""
    return os.environ.get('DATABASE_URL', 'postgresql+asyncpg://user:password@localhost:5432/love_restaurant')

def check_migration_history(verbose=False):
    """Check migration history and compare with available migration scripts."""
    # Setup Alembic configuration
    alembic_cfg = Config("./alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    
    # Get available revisions from migration scripts
    available_revisions = sorted(
        [(s.revision, s.down_revision, s.doc) for s in script.walk_revisions()],
        key=lambda x: x[0]
    )
    
    print("Available migrations:")
    for rev, down_rev, doc in available_revisions:
        print(f"  • {rev} - {doc} (parent: {down_rev})")
    
    # Check current database state
    db_url = get_database_url()
    db_url = db_url.replace('+asyncpg', '') # Use synchronous driver for simplicity
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            
            print(f"\nCurrent database revision: {current_rev}")
            
            if current_rev is None:
                print("Database has no alembic_version table or it's empty.")
            else:
                head_revision = script.get_current_head()
                if current_rev == head_revision:
                    print("Database is up-to-date with all migrations.")
                else:
                    print(f"Database is NOT up-to-date. Head revision is: {head_revision}")
                    
                    # Show pending migrations
                    if verbose:
                        print("\nPending migrations:")
                        for rev in script.iterate_revisions(current_rev, head_revision):
                            print(f"  • {rev.revision} - {rev.doc}")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Check migration status for Love Restaurant bot')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed information')
    args = parser.parse_args()
    
    success = check_migration_history(args.verbose)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 
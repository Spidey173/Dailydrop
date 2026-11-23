#!/usr/bin/env python3
"""
Script to reinitialize database with migrations and seed data.
"""
import os
import sys

# Ensure workspace is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from migrations.runner import run_migrations
from seed import seed_database

def main():
    print("Running database migrations...")
    try:
        run_migrations()
        print("✓ Migrations applied successfully!")
        print("Seeding database...")
        seed_database()
        print("✓ Database seeded successfully!")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

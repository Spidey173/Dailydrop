#!/usr/bin/env python3
"""
Script to reinitialize Neon PostgreSQL database with schema and catalog products.
"""
import os
import sys

# Ensure workspace is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, get_db_connection

def main():
    print("Reinitializing Neon PostgreSQL database...")
    try:
        init_database()
        print("✓ Database initialized successfully on Neon PostgreSQL!")
    except Exception as e:
        print(f"✗ Error initializing Neon PostgreSQL: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

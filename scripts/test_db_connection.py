#!/usr/bin/env python3
"""Test database connection with different credentials."""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.factory import get_repository

async def test_connection(database_url, label):
    """Test a database connection."""
    print(f"\n🔍 Testing: {label}")
    print(f"   URL: {database_url.split('@')[0]}@***")
    
    try:
        repo = get_repository()
        # Override the database URL
        repo.database_url = database_url
        repo.engine = None  # Force reconnection
        
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        repo.engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )
        repo.session_factory = async_sessionmaker(
            repo.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        practices = await repo.get_practices()
        print(f"   ✅ SUCCESS! Found {len(practices)} practices")
        await repo.close()
        return True
    except Exception as e:
        error_msg = str(e)
        if "password authentication failed" in error_msg:
            print(f"   ❌ Password authentication failed")
        else:
            print(f"   ❌ Error: {error_msg[:100]}")
        try:
            await repo.close()
        except:
            pass
        return False

async def main():
    """Test multiple credential combinations."""
    print("🧪 Testing Database Connections\n")
    
    # Common credential combinations to test
    credentials = [
        ("postgresql+asyncpg://postgres:postgres@localhost:5432/tebra_dw", "postgres/postgres"),
        ("postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw", "tebra_user/tebra_password"),
        ("postgresql+asyncpg://postgres:password@localhost:5432/tebra_dw", "postgres/password"),
        ("postgresql+asyncpg://postgres:@localhost:5432/tebra_dw", "postgres (no password)"),
    ]
    
    # Add custom credentials if provided
    if len(sys.argv) > 1:
        custom_url = sys.argv[1]
        credentials.append((custom_url, "Custom"))
    
    results = []
    for url, label in credentials:
        result = await test_connection(url, label)
        results.append((label, result))
        if result:
            print(f"\n✅ Working credentials found: {label}")
            print(f"   Use: DATABASE_URL=\"{url}\"")
            return 0
    
    print("\n❌ None of the tested credentials worked.")
    print("\nPlease:")
    print("1. Verify your PostgreSQL password")
    print("2. Or run: python scripts/test_db_connection.py 'postgresql+asyncpg://user:password@localhost:5432/tebra_dw'")
    return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


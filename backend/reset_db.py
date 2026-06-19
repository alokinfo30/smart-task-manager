import os
import sys
import asyncio

# Add backend to path to import database properly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import engine, Base, init_db

async def reset_database():
    print("Dropping all existing tables to clear records...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("Recreating tables with the latest schema...")
    await init_db()
    print("Database has been successfully updated and all records are zeroed.")

if __name__ == "__main__":
    asyncio.run(reset_database())
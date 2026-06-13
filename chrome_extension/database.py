import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# You get these for free by creating a project at supabase.com
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

def get_db() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials not found in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)
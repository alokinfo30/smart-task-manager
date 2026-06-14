import json
import os
import sys
import argparse
import asyncio

# 1. Get absolute paths
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")

# 2. Temporarily change to the backend directory so SQLite connects to the REAL database
os.chdir(backend_dir)
sys.path.append(root_dir)

# 3. Import database and auth modules
from backend.database import init_db
from auth import PasswordHandler, PasswordDB

# 4. Ensure tables are created (prevents 'no such table' errors)
asyncio.run(init_db())

# 5. Change back to root directory to save raw_pins.json in the right place
os.chdir(root_dir)

file_path = os.path.join(os.path.dirname(__file__), "raw_pins.json")

parser = argparse.ArgumentParser(description="Update a user's PIN manually.")
parser.add_argument("--mobile", required=True, help="User's mobile number")
parser.add_argument("--pin", required=True, help="New 6-digit PIN")
args = parser.parse_args()

mobile = args.mobile
new_pin = args.pin

data = {}
if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

data[mobile] = new_pin

with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

user_data = PasswordDB.get_user(mobile)
if not user_data:
    print(f"User {mobile} not found in database. Forcing account creation...")
    from datetime import datetime
    ans_hash, ans_salt = PasswordHandler.hash_password("admin")
    user_data = {"attempts": 0, "registered_at": datetime.now().isoformat(), "security_question": "What was the name of your first pet?", "security_answer_hash": ans_hash, "security_answer_salt": ans_salt, "name": "Master User", "email": "", "avatar": "👤"}

pwd_hash, salt = PasswordHandler.hash_password(new_pin)
user_data["hash"] = pwd_hash
user_data["salt"] = salt
user_data["attempts"] = 0

PasswordDB.update_user(mobile, user_data)
print("Successfully updated both raw_pins.json and the Secure Database! You can now log in.")
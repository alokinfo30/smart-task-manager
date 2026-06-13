import os
import sys
import json

# Add backend to path to import database properly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import SyncSessionLocal, UserDB, SessionDB, TaskDB, ExpenseDB

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTINES_FILE = os.path.join(ROOT_DIR, "routines.json")
RECURRING_EXPENSES_FILE = os.path.join(ROOT_DIR, "recurring_expenses.json")

def clear_real_users():
    deleted_count = 0
    deleted_mobiles = []
    
    # 1. Clean Database Records
    with SyncSessionLocal() as session:
        users = session.query(UserDB).all()
        for user in users:
            mobile = str(user.mobile)
            # Skip guest and demo accounts
            if not mobile.startswith('demo_') and not mobile.startswith('guest') and mobile != 'demo_user':
                session.delete(user)
                session.query(SessionDB).filter(SessionDB.mobile == mobile).delete(synchronize_session=False)
                session.query(TaskDB).filter(TaskDB.owner == mobile).delete(synchronize_session=False)
                session.query(ExpenseDB).filter(ExpenseDB.owner == mobile).delete(synchronize_session=False)
                deleted_mobiles.append(mobile)
                deleted_count += 1
        session.commit()

    # 2. Clean JSON Configuration Files
    for filepath in [ROUTINES_FILE, RECURRING_EXPENSES_FILE]:
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                changed = False
                for mobile in deleted_mobiles:
                    if mobile in data:
                        del data[mobile]
                        changed = True
                        
                if changed:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

    # 3. Clean left-over text files (Resumes and Persistent Archives)
    for mobile in deleted_mobiles:
        resume_file = os.path.join(ROOT_DIR, f"resume_profile_{mobile}.txt")
        safe_id = "".join(c for c in mobile if c.isalnum() or c in ("_", "-", "@", "."))
        archive_file = os.path.join(ROOT_DIR, "backend", "archives", f"daily_summary_{safe_id}.txt")
        
        for p in [resume_file, archive_file]:
            if os.path.exists(p):
                os.remove(p)

    print(f"Successfully deleted {deleted_count} real user(s) and their associated records.")

if __name__ == "__main__":
    clear_real_users()
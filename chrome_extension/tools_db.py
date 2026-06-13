from database import get_db
from datetime import datetime

def add_task(task: str, priority: str, owner: str) -> str:
    """Adds a task to the Supabase PostgreSQL database."""
    try:
        db = get_db()
        data = {
            "task": task,
            "priority": priority,
            "owner": owner,
            "status": "Pending",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        db.table("tasks").insert(data).execute()
        return f"Success: Task '{task}' added."
    except Exception as e:
        return f"Error adding task: {str(e)}"

def read_todo_list(owner: str) -> str:
    """Reads tasks concurrently without thread locking."""
    try:
        db = get_db()
        res = db.table("tasks").select("*").eq("owner", owner).execute()
        if not res.data:
            return "No tasks found."
        
        return "Date | Task | Status | Priority\n" + "\n".join([f"{t['date']} | {t['task']} | {t['status']} | {t['priority']}" for t in res.data])
    except Exception as e:
        return f"Error reading tasks: {str(e)}"
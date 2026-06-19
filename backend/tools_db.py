from database import get_db
from datetime import datetime

def add_task(task: str, priority: str, owner: str, comment: str = "") -> str:
    """Adds a task to the Supabase PostgreSQL database."""
    try:
        db = get_db()
        data = {
            "task": task,
            "priority": priority,
            "owner": owner,
            "status": "Pending",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "comment": comment
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

def get_tasks_json(owner: str) -> list:
    """Returns tasks as a list of dictionaries for the frontend UI."""
    try:
        db = get_db()
        res = db.table("tasks").select("*").eq("owner", owner).order("id", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"Error reading tasks: {str(e)}")
        return []

def update_task_status_by_id(task_id: int, status: str, owner: str) -> str:
    """Updates a task's status directly from the UI."""
    try:
        db = get_db()
        db.table("tasks").update({"status": status}).eq("id", task_id).eq("owner", owner).execute()
        return "Success"
    except Exception as e:
        return str(e)

def delete_task_by_id(task_id: int, owner: str) -> str:
    """Deletes a task directly from the UI."""
    try:
        db = get_db()
        db.table("tasks").delete().eq("id", task_id).eq("owner", owner).execute()
        return "Success"
    except Exception as e:
        return str(e)

def add_expense(amount: float, category: str, description: str, owner: str) -> str:
    """Adds an expense to the Supabase PostgreSQL database."""
    try:
        db = get_db()
        data = {
            "amount": amount,
            "category": category,
            "description": description,
            "owner": owner,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        db.table("expenses").insert(data).execute()
        return f"Success: Expense of ${amount} added."
    except Exception as e:
        return f"Error adding expense: {str(e)}"

def get_expenses_json(owner: str) -> list:
    """Returns expenses as a list of dictionaries for the frontend UI."""
    try:
        db = get_db()
        res = db.table("expenses").select("*").eq("owner", owner).order("id", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"Error reading expenses: {str(e)}")
        return []

def delete_expense_by_id(expense_id: int, owner: str) -> str:
    """Deletes an expense directly from the UI."""
    try:
        db = get_db()
        db.table("expenses").delete().eq("id", expense_id).eq("owner", owner).execute()
        return "Success"
    except Exception as e:
        return str(e)

def clear_done_tasks(owner: str) -> str:
    """Clears all completed tasks directly from the UI or AI Agent."""
    try:
        db = get_db()
        db.table("tasks").delete().eq("status", "Done").eq("owner", owner).execute()
        return "Success"
    except Exception as e:
        return str(e)
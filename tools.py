# tools.py
import datetime
import os
import threading
import json
import pusher
from auth import PasswordDB
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.database import SyncSessionLocal, TaskDB, ExpenseDB


PUSHER_APP_ID = os.environ.get("PUSHER_APP_ID")
if PUSHER_APP_ID:
    pusher_client = pusher.Pusher(
        app_id=PUSHER_APP_ID,
        key=os.environ.get("NEXT_PUBLIC_PUSHER_KEY", ""),
        secret=os.environ.get("PUSHER_SECRET", ""),
        cluster=os.environ.get("NEXT_PUBLIC_PUSHER_CLUSTER", ""),
        ssl=True
    )
else:
    pusher_client = None

def trigger_pusher_update():
    if pusher_client:
        try:
            pusher_client.trigger('task-board', 'update', {'event': 'data_changed'})
        except:
            pass

# Thread-local storage to keep track of the current user session for the agent
context = threading.local()
file_lock = threading.RLock()

def get_current_user():
    """Helper to get the current authenticated user from thread context."""
    return getattr(context, 'user', 'guest')

def get_archive_file_path(user_id: str):
    """Determines the file path for a user's persistent task archive."""
    if str(user_id).startswith("guest") or str(user_id).startswith("demo_"):
        return None # Guests don't have persistent archives
    safe_id = "".join(c for c in str(user_id) if c.isalnum() or c in ("_", "-", "@", "."))
    return f"daily_summary_{safe_id}.txt"

def read_todo_list() -> str:
    """
    Reads the current user's daily pending TODO tasks from the local CSV file.
    Returns the raw content of the task list, including Date, Task, Status, Priority, and Completion info.
    Use this when the user asks to see their tasks, analyze their workload, or search for items.
    """
    try:
        user = get_current_user()
        with SyncSessionLocal() as session:
            tasks = session.query(TaskDB).all()
            
            visible_tasks = []
            now = datetime.datetime.now()
            tasks_deleted = False
            for t in tasks:
                # Auto clear done tasks after 24 hours
                if t.status == "Done" and t.completed_at:
                    try:
                        completed_time = datetime.datetime.strptime(t.completed_at, "%Y-%m-%d %H:%M:%S")
                        if (now - completed_time).total_seconds() > 24 * 3600:
                            session.delete(t)
                            tasks_deleted = True
                            continue
                    except ValueError:
                        pass
                if t.owner == user or (not str(user).startswith('guest') and not str(user).startswith('demo_') and user in [s.strip() for s in str(t.shared_with or "").split(',')]):
                    visible_tasks.append(t)
            if tasks_deleted:
                session.commit()
                trigger_pusher_update()

        if not visible_tasks:
            return "The task list is currently empty or no tasks found for you."

        output = "id,Date,Task,Status,Priority,CompletedAt,Owner,SharedWith,Comment\n"
        for t in visible_tasks:
            output += f"{t.id},{t.date},{t.task},{t.status},{t.priority},{t.completed_at},{t.owner},{t.shared_with},{t.comment or ''}\n"
        return output
    except Exception as e:
        print(f"Error reading tasks: {e}")
        return "Error reading tasks due to an internal database issue."

def read_routines() -> str:
    """
    Reads the current user's daily routines and schedule.
    Use this to understand their daily schedule, punctuality, and suggest productivity strategies.
    """
    try:
        routines_file = "routines.json"
        if not os.path.exists(routines_file):
            return "No routines configured."
        with open(routines_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        user = get_current_user()
        if user not in data or not data[user].get("settings"):
            return "No routines configured for this user."
            
        settings = data[user]["settings"]
        out = "User's Daily Routines:\n"
        for r in settings:
            days = ", ".join(r.get("days", ["Everyday"]))
            out += f"- {r['name']}: {r['start']} to {r['end']} ({days})\n"
        return out
    except Exception as e:
        print(f"Error reading routines: {e}")
        return "Error reading routines due to an internal issue."

def add_task(task: str = "test task", priority: str = "High", date: str = None, shared_with_accounts: str = "", owner: str = None, comment: str = "") -> str:
    """
    Appends a new task to the todo list.
    
    Args:
        task: A clear description of the task.
        priority: The urgency level. Defaults to 'High'. Always use 'High' for new tasks.
        date: The scheduled date in YYYY-MM-DD format. Defaults to current date if not provided.
        shared_with_accounts: Comma-separated user accounts (mobile/email) to share this task with.
        comment: An optional comment for the task.
    Returns a success message or error string.
    """
    if shared_with_accounts:
        accounts = [acc.strip() for acc in shared_with_accounts.split(",") if acc.strip()]
        valid_accounts = []
        current_user = owner if owner else get_current_user()
        for acc in accounts:
            if acc == current_user:
                return f"Error: You cannot share a task with yourself ({acc})."
            if "@" not in acc:
                acc = "".join(filter(str.isdigit, acc))
                if len(acc) != 10:
                    return f"Error: Mobile number '{acc}' must be exactly 10 digits."
                if not PasswordDB.get_user(acc):
                    return f"Error: Account '{acc}' does not exist."
            valid_accounts.append(acc)
        shared_with_accounts = ",".join(valid_accounts)

    if not date:
        date = datetime.date.today().strftime("%Y-%m-%d")
    try:
        with SyncSessionLocal() as session:
            new_task = TaskDB(
                date=date,
                task=task,
                status="Pending",
                priority=priority,
                completed_at="",
                owner=owner if owner else get_current_user(),
                shared_with=shared_with_accounts,
                comment=comment
            )
            session.add(new_task)
            session.commit()
        trigger_pusher_update()
        return f"Success: Task '{task}' added successfully."
    except Exception as e:
        print(f"Error adding task: {e}")
        return "Error adding task due to an internal issue."

def delete_task(task_identifier: str, owner: str = None) -> str:
    """
    Deletes tasks from the todo list based on a keyword match in the task description.
    
    Args:
        task_identifier: A string or keyword to search for in the task descriptions to identify which one to delete.
    Returns a summary of deleted tasks or a 'not found' message.
    """
    try:
        user = owner if owner else get_current_user()
        with SyncSessionLocal() as session:
            tasks = session.query(TaskDB).filter(TaskDB.owner == user).all()
            deleted_count = 0
            deleted_summaries = []
            for t in tasks:
                if task_identifier.lower() in t.task.lower():
                    session.delete(t)
                    deleted_count += 1
                    deleted_summaries.append(f"- {t.task}")
                    
            if deleted_count == 0:
                all_tasks = session.query(TaskDB).all()
                if any(task_identifier.lower() in t.task.lower() for t in all_tasks):
                    return f"Permission Denied: Task '{task_identifier}' exists but you are not the owner."
                return f"No tasks found matching '{task_identifier}'."
            session.commit()
        
        trigger_pusher_update()
        return f"Success: Deleted {deleted_count} task(s) matching '{task_identifier}':\n{deleted_summaries}"
    except Exception as e:
        print(f"Error deleting task: {e}")
        return "Error deleting task due to an internal issue."

def update_task(task_identifier: str, updates: dict, owner: str = None) -> str:
    """
    Updates multiple fields of tasks matching the identifier.
    
    Args:
        task_identifier: A keyword to search for in the task descriptions.
        updates: A dictionary of fields to update (e.g., {'Date': '2026-07-01', 'Priority': 'Medium', 'Comment': 'new comment'}).
        owner: Optional owner override.
    """
    try:
        user = owner if owner else get_current_user()
        with SyncSessionLocal() as session:
            tasks = session.query(TaskDB).all()
            target_tasks = [t for t in tasks if task_identifier.lower() in t.task.lower() and 
                            (t.owner == user or (not str(user).startswith('guest') and not str(user).startswith('demo_') and user in [s.strip() for s in str(t.shared_with or "").split(',')]))]
            
            if not target_tasks:
                return f"No tasks found matching '{task_identifier}' that you have permission to edit."
        
        if "SharedWith" in updates:
            accounts = [s.strip() for s in str(updates["SharedWith"]).split(',') if s.strip()]
            valid_accounts = []
            current_user = owner if owner else get_current_user()
            for acc in accounts:
                if acc == current_user:
                    return f"Error: You cannot share a task with yourself ({acc})."
                if "@" not in acc:
                    acc = "".join(filter(str.isdigit, acc))
                    if len(acc) != 10:
                        return f"Error: Mobile number '{acc}' must be exactly 10 digits."
                    if not PasswordDB.get_user(acc):
                        return f"Error: Account '{acc}' does not exist."
                valid_accounts.append(acc)
            updates["SharedWith"] = ",".join(valid_accounts)

            allowed_mapping = {"Date": "date", "Task": "task", "Status": "status", "Priority": "priority", "SharedWith": "shared_with", "Comment": "comment"}
            for t in target_tasks:
                for field, value in updates.items():
                    if field in allowed_mapping:
                        setattr(t, allowed_mapping[field], value)
                        if field == "Status":
                            t.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if value == "Done" else ""
            session.commit()
            
        trigger_pusher_update()
        return f"Success: Updated {list(updates.keys())} for tasks matching '{task_identifier}'."
    except Exception as e:
        print(f"Error updating task: {e}")
        return "Error updating task due to an internal issue."

def update_task_status(task_identifier: str, new_status: str, owner: str = None) -> str:
    """
    Updates the status of tasks matching the identifier (e.g., from 'Pending' to 'Done').
    
    Args:
        task_identifier: A keyword to search for in the task descriptions to identify which one to update.
        new_status: The new status string. Usually 'Pending', 'Working', or 'Done'.
    Returns a success message or error string.
    """
    try:
        user = owner if owner else get_current_user()
        
        with SyncSessionLocal() as session:
            tasks = session.query(TaskDB).all()
            target_tasks = [t for t in tasks if task_identifier.lower() in t.task.lower() and 
                            (t.owner == user or (not str(user).startswith('guest') and not str(user).startswith('demo_') and user in [s.strip() for s in str(t.shared_with or "").split(',')]))]
            
            if not target_tasks:
                if any(task_identifier.lower() in t.task.lower() for t in tasks):
                    return f"Permission Denied: Task '{task_identifier}' exists but you are not the owner."
                return f"No tasks found matching '{task_identifier}' to update."
            
            for t in target_tasks:
                t.status = new_status
                if new_status == 'Done':
                    t.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    t.completed_at = ""
            session.commit()
            
        trigger_pusher_update()
        return f"Success: Updated status to '{new_status}' for tasks matching '{task_identifier}'."
    except Exception as e:
        print(f"Error updating task: {e}")
        return "Error updating task due to an internal issue."

def log_report(report_content: str) -> str:
    """
    Saves the provided content (e.g., chat history, analysis, or report) to a user-specific archive file for permanent storage.
    Use this to archive information that should persist even after the current chat session is cleared.
    Args:
        report_content: The string content (e.g., formatted chat history) to be saved.
    """
    try:
        user = get_current_user()
        archive_file = get_archive_file_path(user)
        if not archive_file:
            return "Error: Cannot archive in guest mode."
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(archive_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n# Persistent Archive: {timestamp}\n")
            f.write(report_content)
            f.write("\n" + "-"*40)
        return f"Success: Response has been archived in the secure storage for user {user}."
    except Exception as e:
        print(f"Error archiving response: {e}")
        return "Error archiving response due to an internal issue."

def add_expense(amount: float, category: str, description: str, date: str = None, owner: str = None) -> str:
    """
    Adds a new daily expense to the tracker.
    """
    if not date:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        with SyncSessionLocal() as session:
            new_exp = ExpenseDB(
                date=date,
                amount=amount,
                category=category,
                description=description,
                owner=owner if owner else get_current_user()
            )
            session.add(new_exp)
            session.commit()
        trigger_pusher_update()
        return f"Success: Expense of {amount} added for '{category}'."
    except Exception as e:
        print(f"Error adding expense: {e}")
        return "Error adding expense due to an internal issue."

def read_expenses() -> str:
    """
    Reads the current user's expenses to analyze spending habits, daily totals, and monthly budgets.
    """
    try:
        user = get_current_user()
        with SyncSessionLocal() as session:
            expenses = session.query(ExpenseDB).filter(ExpenseDB.owner == user).all()
            
        if not expenses:
            return "No expenses found for you."
            
        output = "id,Date,Amount,Category,Description,Owner\n"
        for e in expenses:
            output += f"{e.id},{e.date},{e.amount},{e.category},{e.description},{e.owner}\n"
        return output
    except Exception as e:
        print(f"Error reading expenses: {e}")
        return "Error reading expenses due to an internal database issue."

def clear_done_tasks(owner: str = None) -> str:
    """
    Deletes all tasks with the status 'Done' for the current user.
    """
    try:
        user = owner if owner else get_current_user()
        with SyncSessionLocal() as session:
            tasks = session.query(TaskDB).filter(TaskDB.owner == user, TaskDB.status == "Done").all()
            cleared_count = len(tasks)
            if cleared_count == 0:
                return "No 'Done' tasks found to clear."
            for t in tasks:
                session.delete(t)
            session.commit()
        
        trigger_pusher_update()
        return f"Success: Cleared {cleared_count} completed tasks from your board."
    except Exception as e:
        print(f"Error clearing done tasks: {e}")
        return "Error clearing done tasks due to an internal issue."

def delete_expense(description_keyword: str, owner: str = None) -> str:
    """
    Deletes expenses based on a keyword match in the description.
    """
    try:
        user = owner if owner else get_current_user()
        with SyncSessionLocal() as session:
            expenses = session.query(ExpenseDB).filter(ExpenseDB.owner == user).all()
            deleted_count = 0
            for e in expenses:
                if description_keyword.lower() in e.description.lower():
                    session.delete(e)
                    deleted_count += 1
            if deleted_count == 0:
                return f"No expenses found with description matching '{description_keyword}'."
            session.commit()
            
        trigger_pusher_update()
        return f"Success: Deleted {deleted_count} expense(s) matching '{description_keyword}'."
    except Exception as e:
        print(f"Error deleting expense: {e}")
        return "Error deleting expense due to an internal issue."
# tools.py
import datetime
import os
import pandas as pd # Required for delete_task
import csv
import threading

# Constants for file paths (could be moved to .env)
TODO_FILE = os.getenv("TODO_FILE_PATH", "todo.txt")
ARCHIVE_DIR = "archives"

# Thread-local storage to keep track of the current user session for the agent
context = threading.local()

def get_current_user():
    """Helper to get the current authenticated user from thread context."""
    return getattr(context, 'user', 'guest')

def get_archive_file_path(user_id: str):
    """Determines the file path for a user's persistent task archive."""
    if user_id == "guest":
        return None # Guests don't have persistent archives
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    return os.path.join(ARCHIVE_DIR, f"daily_summary_{user_id}.txt")

def read_todo_list() -> str:
    """
    Reads the current user's daily pending TODO tasks from the local CSV file.
    Returns the raw content of the task list, including Date, Task, Status, Priority, and Completion info.
    Use this when the user asks to see their tasks, analyze their workload, or search for items.
    """
    try:
        if not os.path.exists(TODO_FILE):
            return f"Error: Task file '{TODO_FILE}' not found. Please create it first."
        
        df = pd.read_csv(TODO_FILE)
        # Ensure 'SharedWith' column exists for filtering
        if 'SharedWith' not in df.columns:
            df['SharedWith'] = ""
        if df.empty:
            return "The task list is currently empty."
            
        user = get_current_user()
        
        # Visibility logic: must be owner OR explicitly shared with mobile number.
        def check_visibility(row):
            if row['Owner'] == user: return True
            if user == 'guest': return False # Guests don't see shared tasks
            shared_list = [s.strip() for s in str(row.get('SharedWith', '')).split(',') if s.strip()]
            return user in shared_list

        visible_df = df[df.apply(check_visibility, axis=1)]
        
        return visible_df.to_csv(index=False) if not visible_df.empty else "No tasks found for you."
    except Exception as e:
        return f"Error reading tasks: {str(e)}"

def add_task(task: str = "test task", priority: str = "High", date: str = None, shared_with_mobiles: str = "") -> str:
    """
    Appends a new task to the todo list.
    
    Args:
        task: A clear description of the task.
        priority: The urgency level. Defaults to 'High'. Always use 'High' for new tasks.
        date: The scheduled date in YYYY-MM-DD format. Defaults to current date if not provided.
        shared_with_mobiles: Comma-separated mobile numbers of users to share this task with.
    Returns a success message or error string.
    """
    if not date:
        date = datetime.date.today().strftime("%Y-%m-%d")
    try:
        fieldnames = ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]
        file_exists = os.path.exists(TODO_FILE)
        is_empty = not file_exists or os.path.getsize(TODO_FILE) == 0
        
        with open(TODO_FILE, "a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if is_empty:
                writer.writeheader()
            writer.writerow({
                "Date": date,
                "Task": task,
                "Status": "Pending",
                "Priority": priority,
                "CompletedAt": "",
                "Owner": get_current_user(),
                "SharedWith": shared_with_mobiles
            })
        return f"Success: Task '{task}' added successfully."
    except Exception as e:
        return f"Error adding task: {str(e)}"

def delete_task(task_identifier: str) -> str:
    """
    Deletes tasks from the todo list based on a keyword match in the task description.
    
    Args:
        task_identifier: A string or keyword to search for in the task descriptions to identify which one to delete.
    Returns a summary of deleted tasks or a 'not found' message.
    """
    try:
        if not os.path.exists(TODO_FILE):
            return f"Error: Task file '{TODO_FILE}' not found."
        
        df = pd.read_csv(TODO_FILE)
        initial_rows = len(df)
        user = get_current_user()
        
        # Match task keyword AND check ownership
        mask = (df['Task'].str.contains(task_identifier, case=False, na=False)) & (df['Owner'] == user)
        
        if not mask.any():
            # Check if it exists but is owned by someone else
            if df['Task'].str.contains(task_identifier, case=False, na=False).any():
                return f"Permission Denied: Task '{task_identifier}' exists but you are not the owner."
            return f"No tasks found matching '{task_identifier}'."
        
        deleted_tasks_df = df[mask]
        remaining_df = df[~mask]
        
        remaining_df.to_csv(TODO_FILE, index=False)
        
        deleted_count = len(deleted_tasks_df)
        deleted_summaries = "\n".join([f"- {row['Task']}" for index, row in deleted_tasks_df.iterrows()])
        
        return f"Success: Deleted {deleted_count} task(s) matching '{task_identifier}':\n{deleted_summaries}"
    except Exception as e:
        return f"Error deleting task: {str(e)}"

def update_task_status(task_identifier: str, new_status: str) -> str:
    """
    Updates the status of tasks matching the identifier (e.g., from 'Pending' to 'Done').
    
    Args:
        task_identifier: A keyword to search for in the task descriptions to identify which one to update.
        new_status: The new status string. Usually 'Pending', 'Working', or 'Done'.
    Returns a success message or error string.
    """
    try:
        if not os.path.exists(TODO_FILE):
            return f"Error: Task file '{TODO_FILE}' not found."
        
        df = pd.read_csv(TODO_FILE)
        user = get_current_user()
        
        # Ensure 'SharedWith' column exists for filtering
        if 'SharedWith' not in df.columns:
            df['SharedWith'] = ""

        # Match task keyword AND (check ownership OR if task is shared with the current user)
        mask = (df['Task'].str.contains(task_identifier, case=False, na=False)) & \
               ((df['Owner'] == user) | (df['SharedWith'].apply(lambda x: user in str(x).split(',') if pd.notna(x) else False)))
        
        if not mask.any():
            if df['Task'].str.contains(task_identifier, case=False, na=False).any():
                return f"Permission Denied: Task '{task_identifier}' exists but you are not the owner."
            return f"No tasks found matching '{task_identifier}' to update."
        
        df.loc[mask, 'Status'] = new_status
        if new_status == 'Done':
            df.loc[mask, 'CompletedAt'] = datetime.datetime.now().replace(microsecond=0)
        else:
            df.loc[mask, 'CompletedAt'] = None
            
        df.to_csv(TODO_FILE, index=False)
        return f"Success: Updated status to '{new_status}' for tasks matching '{task_identifier}'."
    except Exception as e:
        return f"Error updating task: {str(e)}"

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
        return f"Error archiving response: {str(e)}"
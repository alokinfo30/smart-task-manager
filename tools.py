# tools.py
import datetime
import os
import pandas as pd # Required for delete_task
import csv

# Constants for file paths (could be moved to .env)
TODO_FILE = os.getenv("TODO_FILE_PATH", "todo.txt")

def read_todo_list() -> str:
    """
    Reads the current user's daily pending TODO tasks from the local CSV file.
    Returns the raw content of the task list, including Date, Task, Status, Priority, and Completion info.
    Use this when the user asks to see their tasks, analyze their workload, or search for items.
    """
    try:
        if not os.path.exists(TODO_FILE):
            return f"Error: Task file '{TODO_FILE}' not found. Please create it first."
        
        with open(TODO_FILE, "r", encoding="utf-8") as file:
            content = file.read().strip()
            return content if content else "The task list is currently empty."
    except Exception as e:
        return f"Error reading tasks: {str(e)}"

def add_task(task: str = "test task", priority: str = "High", date: str = None) -> str:
    """
    Appends a new task to the todo list.
    
    Args:
        task: A clear description of the task.
        priority: The urgency level. Must be one of: 'High', 'Medium', 'Low'.
        date: The scheduled date in YYYY-MM-DD format. Defaults to today if not provided.
    Returns a success message or error string.
    """
    if not date:
        date = datetime.date.today().strftime("%Y-%m-%d")
    try:
        fieldnames = ["Date", "Task", "Status", "Priority", "CompletedAt"]
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
                "CompletedAt": ""
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
        
        # Filter out rows that contain the task_identifier (case-insensitive)
        # We'll search in 'Task' column
        mask = df['Task'].str.contains(task_identifier, case=False, na=False)
        
        if not mask.any():
            return f"No tasks found matching '{task_identifier}' to delete."
        
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
        mask = df['Task'].str.contains(task_identifier, case=False, na=False)
        
        if not mask.any():
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
    Saves a specific response, analysis, or report to the 'daily_summary.txt' file for permanent storage.
    Use this to archive information that should persist even after the chat history is cleared.
    Args:
        report_content: The formatted string content of the report to be saved.
    """
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("daily_summary.txt", "a", encoding="utf-8") as f:
            f.write(f"\n\n# Persistent Archive: {timestamp}\n")
            f.write(report_content)
            f.write("\n" + "-"*40)
        return "Success: Response has been archived in daily_summary.txt."
    except Exception as e:
        return f"Error archiving response: {str(e)}"
# agent.py
import os
from dotenv import load_dotenv
from google import genai
import tools
from datetime import datetime
import json

load_dotenv()

# Use Gemma 4 models for lifetime-free conversation (available on this API)
MODEL_FALLBACKS = ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]

# Configure AI client (uses Gemma models)
# Ensure GOOGLE_API_KEY is set in your environment variables
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

def get_history_file_path(user_id):
    if user_id == "guest":
        return None # Guests don't have persistent chat history
    return f"chat_history_{user_id}.json"

SYSTEM_INSTRUCTION = """
You are a highly capable Personal Task Assistant. Your goal is to help the user manage their professional and personal life efficiently.

Capabilities:
1. Manage tasks (add, update status, delete) using your tools.
2. Provide insights and analysis on the current workload.
3. Categorize tasks and suggest priorities based on user context.
4. Break down complex tasks into smaller, actionable sub-steps.
5. Maintain a professional, encouraging, and organized tone.
6. Use the 'log_report' tool whenever you generate a detailed analysis, summary, or when the user asks to 'save' a response.
7. When adding a task, only ask the user for the task name. You must automatically set the priority to 'High' and the date to the current date (today) when calling the 'add_task' tool. You can also specify a comma-separated list of mobile numbers in the 'shared_with_mobiles' argument if the user wants to share the task with specific individuals.
8. Motivation: Encourage users to improve their 'Sprint Speed' and reach 'Elite Executioner' rank by completing tasks quickly. Provide positive reinforcement.
9. Privacy Rules: You can see your tasks and tasks explicitly shared with your mobile number. You can modify tasks you own or tasks that are explicitly shared with your mobile number.
   If a user asks to share a task, use the 'add_task' tool and provide a comma-separated list of mobile numbers in the 'shared_with_mobiles' argument.
   Do not use a boolean 'shared' argument.
10. Security: Never display full mobile numbers (e.g. 9876543210) in your chat responses. Always mask them for privacy (e.g. 98******10).

When asked to 'Analyze' or 'Report', read the list first, then provide a structured breakdown with priorities and workload warnings if necessary.
Today's Date: {today}
""".format(today=datetime.now().strftime("%Y-%m-%d"))

def save_chat_state(agent_history, chat_display, user_id):
    """Saves both the agent's internal history and the UI chat display to a JSON file."""
    history_file = get_history_file_path(user_id)
    if not history_file:
        return # Do not save for guests

    serialized_history = []
    for c in agent_history:
        if hasattr(c, "model_dump"):
            serialized_history.append(c.model_dump())
        elif hasattr(c, "to_dict"):
            serialized_history.append(type(c).to_dict(c))
        elif isinstance(c, (dict, list, str, int, float, bool)):
            serialized_history.append(c)
        else:
            try:
                serialized_history.append(json.loads(json.dumps(c, default=str)))
            except Exception:
                serialized_history.append(str(c))

    state = {
        "agent_history": serialized_history,
        "chat_display": chat_display
    }
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)

def load_chat_state(user_id):
    """Loads the chat state from the JSON file."""
    history_file = get_history_file_path(user_id)
    if not history_file or not os.path.exists(history_file):
        return {"agent_history": [], "chat_display": []}

    # Check if file exists and is not empty to prevent parsing errors
    if os.path.exists(history_file) and os.path.getsize(history_file) > 0:
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Auto-delete non-archived messages older than 8 hours (28,800 seconds)
            now = datetime.now()
            cutoff_sec = 8 * 3600
            chat_display = data.get("chat_display", [])
            
            new_display = []
            deleted_any = False
            for msg in chat_display:
                ts_str = msg.get("timestamp")
                is_archived = msg.get("archived", False)
                
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if (now - ts).total_seconds() > cutoff_sec and not is_archived:
                            deleted_any = True
                            continue # Remove this message from history
                    except (ValueError, TypeError):
                        pass
                new_display.append(msg)
            
            if deleted_any:
                data["chat_display"] = new_display
                # Reset agent history in the returned state to maintain context integrity
                data["agent_history"] = []
            
            return data
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️ Error loading history for {user_id}: {e}")
    return {"agent_history": [], "chat_display": []}

def clear_chat_state(user_id):
    """Removes the history file from disk."""
    history_file = get_history_file_path(user_id)
    if history_file and os.path.exists(history_file):
        os.remove(history_file)

def extract_response_text(response):
    """Extract the assistant text from a generative response."""
    if not getattr(response, "candidates", None):
        return ""

    candidate = response.candidates[0]
    content = getattr(candidate, "content", None)
    if not content:
        return ""

    parts = []
    if isinstance(content, list):
        parts = content
    elif hasattr(content, "parts"):
        parts = content.parts

    texts = []
    for part in parts:
        if hasattr(part, "text") and part.text:
            texts.append(part.text)
    
    return "".join(texts).strip()


def normalize_history(history):
    """Convert history entries to genai.types.Content objects with 'model' role for Gemma."""
    normalized = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            # Gemma models use 'model' instead of 'assistant'
            if role == "assistant":
                role = "model"

            # Handle restored complex dictionaries (from model_dump/to_dict) or simple dicts
            parts = item.get("parts")
            if parts and isinstance(parts, list):
                text_parts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
                if text_parts:
                    normalized.append(genai.types.Content(
                        parts=[genai.types.Part(text=t) for t in text_parts],
                        role=role
                    ))
            elif "content" in item:
                normalized.append(genai.types.Content(
                    parts=[genai.types.Part(text=item["content"])],
                    role=role
                ))
        elif isinstance(item, genai.types.Content):
            # Convert assistant role to model role if needed
            if item.role == "assistant":
                item.role = "model"
            normalized.append(item)
        else:
            # Skip unsupported history items
            continue
    return normalized


def run_autonomous_agent(prompt: str, history: list = None, user_id: str = "guest") -> tuple[str, list]:
    if not api_key or not client:
        return "Error: GOOGLE_API_KEY not found. Please set it to use the Agentic AI features.", history or []

    # Initialization logs (ASCII-only to avoid encoding issues)
    print("Initializing Personal Assistant...")
    print(f"User: {user_id} | Thinking about: {prompt}\n")

    # Set the user context for the tools
    tools.context.user = user_id

    messages = normalize_history(history)
    
    # Create parts for the current message (Text + Multimodal Attachments)
    current_parts = [genai.types.Part.from_text(text=prompt)]

    # Wrap tool functions so they always run with an explicit owner (user_id).
    # This avoids losing thread-local context when the model runtime invokes functions.
    def read_todo_list_owner(*args, **kwargs):
        return tools.read_todo_list()

    def add_task_owner(task: str = "test task", priority: str = "High", date: str = None, shared_with_mobiles: str = "", **kwargs):
        return tools.add_task(task=task, priority=priority, date=date, shared_with_mobiles=shared_with_mobiles, owner=user_id)

    def delete_task_owner(task_identifier: str, **kwargs):
        return tools.delete_task(task_identifier, owner=user_id)

    def update_task_status_owner(task_identifier: str, new_status: str, **kwargs):
        return tools.update_task_status(task_identifier, new_status, owner=user_id)

    def log_report_owner(report_content: str, **kwargs):
        return tools.log_report(report_content)

    config = genai.types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[
            read_todo_list_owner,
            add_task_owner,
            delete_task_owner,
            update_task_status_owner,
            log_report_owner,
        ],
        tool_config=genai.types.ToolConfig(
            function_calling_config=genai.types.FunctionCallingConfig(
                mode=genai.types.FunctionCallingConfigMode.AUTO
            )
        ),
        automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(),
        temperature=0.25,
    )

    last_error = None
    for model_name in MODEL_FALLBACKS:
        try:
            chat = client.chats.create(
                model=model_name,
                history=messages,
                config=config,
            )
            response = chat.send_message(current_parts)
            response_text = extract_response_text(response)
            
            # Retrieve the chat history using the SDK method
            try:
                updated_history = chat.get_history()
            except Exception:
                # Fallback: no history available, return prior history
                updated_history = history or []

            print(f"[Task Complete] Using model: {model_name}")
            return response_text, updated_history

        except Exception as e:
            last_error = e
            error_text = str(e)
            print(f"Model {model_name} failed: {error_text}")
            if "RESOURCE_EXHAUSTED" in error_text or "quota" in error_text.lower():
                return (
                    "Error: Resource exhausted or quota limit reached. "
                    "Please check your Google API billing/quota or try a different model.",
                    history or [],
                )
            if "not found" in error_text.lower() or "unsupported" in error_text.lower():
                continue
            break

    # If the model was unavailable due to high demand, attempt a safe fallback:
    if last_error:
        le = str(last_error)
        if ("UNAVAILABLE" in le) or ("503" in le) or ("high demand" in le.lower()):
            try:
                # Fallback: add the user's prompt as a task directly for persistence
                add_result = add_task_owner(task=prompt)
                return f"Model unavailable; fallback executed. {add_result}", history or []
            except Exception as e:
                return f"Error: {str(last_error)}; fallback add failed: {e}", history or []
    return f"Error: {str(last_error)}", history or []

if __name__ == "__main__":
    # Initialize a demo todo file if it doesn't exist
    if not os.path.exists("todo.txt"):
        print("🛠️ Creating sample 'todo.txt'...")
        with open("todo.txt", "w", encoding="utf-8") as f:
            f.write("Date,Task,Status,Priority\n"
                    "2026-05-29,Review backend schema,Pending,Medium\n"
                    "2026-05-29,Clean docker states,Working,Medium\n"
                    "2026-05-29,Mentor students,Pending,High")

    user_command = "Analyze my tasks, create the daily technical summary, and log it."
    run_autonomous_agent(user_command)
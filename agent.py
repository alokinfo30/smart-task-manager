# agent.py
import os
from dotenv import load_dotenv
from google import genai
from tools import read_todo_list, add_task, delete_task, update_task_status, log_report
from datetime import datetime
import json

load_dotenv()

HISTORY_FILE = "chat_history.json"
# Use free Gemma models by default (no paid quota limits).
# Ordered list: preferred -> fallback.
MODEL_FALLBACKS = ["models/gemma-4-31b-it", "models/gemma-4-26b-a4b-it"]

# Configure Gemini AI client
# Ensure GOOGLE_API_KEY is set in your environment variables
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

SYSTEM_INSTRUCTION = """
You are a highly capable Personal Task Assistant. Your goal is to help the user manage their professional and personal life efficiently.

Capabilities:
1. Manage tasks (add, update status, delete) using your tools.
2. Provide insights and analysis on the current workload.
3. Categorize tasks and suggest priorities based on user context.
4. Break down complex tasks into smaller, actionable sub-steps.
5. Maintain a professional, encouraging, and organized tone.
6. Use the 'log_report' tool whenever you generate a detailed analysis, summary, or when the user asks to 'save' a response.

When asked to 'Analyze' or 'Report', read the list first, then provide a structured breakdown with priorities and workload warnings if necessary.
Today's Date: {today}
""".format(today=datetime.now().strftime("%Y-%m-%d"))

def save_chat_state(agent_history, chat_display):
    """Saves both the agent's internal history and the UI chat display to a JSON file."""
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
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_chat_state():
    """Loads the chat state from the JSON file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading history: {e}")
    return {"agent_history": [], "chat_display": []}

def clear_chat_state():
    """Removes the history file from disk."""
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

def extract_response_text(response):
    """Extract the assistant text from a generative response."""
    if not getattr(response, "candidates", None):
        return ""

    candidate = response.candidates[0]
    content = getattr(candidate, "content", None)
    if not content:
        return ""

    if isinstance(content, list):
        texts = []
        for item in content:
            if getattr(item, "text", None):
                texts.append(item.text)
            for part in getattr(item, "parts", []) or []:
                if getattr(part, "text", None):
                    texts.append(part.text)
        return "".join(texts).strip()

    if getattr(content, "text", None):
        return content.text.strip()

    return "".join(
        part.text or "" for part in getattr(content, "parts", []) or []
        if getattr(part, "text", None)
    ).strip()


def normalize_history(history):
    """Convert history entries to genai.types.Content objects with 'model' role for Gemma."""
    normalized = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            text = item.get("content")
            if text is None:
                continue
            # Gemma models use 'model' instead of 'assistant'
            if role == "assistant":
                role = "model"
            normalized.append(genai.types.Content(
                parts=[genai.types.Part(text=text)],
                role=role,
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


def run_autonomous_agent(prompt: str, history: list = None, attachments: list = None):
    if not api_key or not client:
        return "Error: GOOGLE_API_KEY not found. Please set it to use the Agentic AI features.", history or []

    print(f"🚀 Initializing Personal Assistant...")
    print(f"📝 Thinking about: {prompt}\n")

    messages = normalize_history(history)
    
    # Create parts for the current message (Text + Multimodal Attachments)
    current_parts = [genai.types.Part.from_text(text=prompt)]
    if attachments:
        for data, mime_type in attachments:
            current_parts.append(genai.types.Part.from_bytes(data=data, mime_type=mime_type))

    config = genai.types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[read_todo_list, add_task, delete_task, update_task_status, log_report],
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
            # Retrieve the chat history via the client helper
            try:
                updated_history = chat.get_history()
            except Exception:
                # Fallback: append the current turn to messages
                updated_history = messages + [genai.types.Content(parts=[genai.types.Part(text=response_text)], role="model")]

            print(f"✅ [Task Complete] Using model: {model_name}")
            return response_text, updated_history

        except Exception as e:
            last_error = e
            error_text = str(e)
            print(f"⚠️ Model {model_name} failed: {error_text}")
            if "RESOURCE_EXHAUSTED" in error_text or "quota" in error_text.lower():
                return (
                    "Error: Resource exhausted or quota limit reached. "
                    "Please check your Google API billing/quota or try a different model.",
                    history or [],
                )
            if "not found" in error_text.lower() or "unsupported" in error_text.lower():
                continue
            break

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
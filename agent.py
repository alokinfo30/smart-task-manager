# agent.py
import os
from dotenv import load_dotenv
from google import genai
import tools
from datetime import datetime
import json

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

load_dotenv()

# Gemini Flash models are available completely FREE of cost on the Google AI Studio Free Tier
MODEL_FALLBACKS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemma-2-27b-it",
    "gemma-2-9b-it"
]
OFFLINE_MODEL = os.getenv("OFFLINE_MODEL", "llama3.2")

# Configure AI client
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
1. Manage tasks (add, update status, delete, clear done) using your tools.
2. Provide insights and analysis on the current workload.
3. Categorize tasks and suggest priorities based on user context.
4. Break down complex tasks into smaller, actionable sub-steps.
5. Maintain a professional, encouraging, and organized tone.
6. Use the 'log_report' tool whenever you generate a detailed analysis, summary, or when the user asks to 'save' a response.
7. When adding a task, only ask the user for the task name. You must automatically set the priority to 'High' and the date to the current date (today) when calling the 'add_task' tool. You can also specify a comma-separated list of user accounts (mobile numbers or emails) in the 'shared_with_accounts' argument if the user wants to share the task with specific individuals.
8. Manage and analyze the user's daily and monthly finances using the 'add_expense', 'read_expenses', and 'delete_expense' tools when requested.
9. Generate learning materials on any topic or from a job description using the 'generate_lesson' tool.
10. Create a tailored resume using the 'create_resume' tool when the user provides their details and a job description.
11. Motivation & Strategy: Encourage users to improve their 'Sprint Speed' and reach 'Elite Executioner' rank by completing tasks quickly. Provide positive reinforcement. ALWAYS suggest the best strategic plan based on their pending tasks and daily routines to help them achieve peak productivity and become the best version of themselves.
12. Privacy Rules: You can see your tasks and tasks explicitly shared with your account. You can modify tasks you own or tasks that are explicitly shared with your account.
   If a user asks to share a task, use the 'add_task' tool and provide a comma-separated list of user accounts in the 'shared_with_accounts' argument.
   If a user asks to change a task's date, priority, or description, use the 'update_task' tool with the 'updates' dictionary.
   Do not use a boolean 'shared' argument.
13. Security: Never display full mobile numbers or emails in your chat responses. Always mask them for privacy (e.g. 98******10).

When asked to 'Analyze', 'Report', or suggest a strategy, use 'read_todo_list' and 'read_routines' first, then provide a structured breakdown with priorities, workload warnings if necessary, and an optimized daily plan.
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
                # Reset agent history to maintain context integrity with the UI
                data["agent_history"] = []
                # Note: We don't write to disk here to prevent infinite rerun loops on load
            
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
    """Convert history entries to genai.types.Content objects with 'model' role."""
    normalized = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            # Gemini models use 'model' instead of 'assistant'
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

def run_autonomous_agent(prompt: str, history: list = None, user_id: str = "guest", language: str = "English") -> tuple[str, list]:
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
    def read_todo_list(*args, **kwargs):
        return tools.read_todo_list()

    def add_task(task: str = "test task", priority: str = "High", date: str = None, shared_with_accounts: str = "", **kwargs):
        return tools.add_task(task=task, priority=priority, date=date, shared_with_accounts=shared_with_accounts, owner=user_id)

    def delete_task(task_identifier: str, **kwargs):
        return tools.delete_task(task_identifier, owner=user_id)

    def update_task(task_identifier: str, updates: dict, **kwargs):
        return tools.update_task(task_identifier, updates, owner=user_id)

    def update_task_status(task_identifier: str, new_status: str, **kwargs):
        return tools.update_task_status(task_identifier, new_status, owner=user_id)

    def log_report(report_content: str, **kwargs):
        return tools.log_report(report_content)

    def read_routines(*args, **kwargs):
        return tools.read_routines()
        
    def add_expense(amount: float, category: str, description: str, date: str = None, **kwargs):
        return tools.add_expense(amount=amount, category=category, description=description, date=date, owner=user_id)

    def read_expenses(*args, **kwargs):
        return tools.read_expenses()
        
    def clear_done_tasks(*args, **kwargs):
        return tools.clear_done_tasks(owner=user_id)

    def delete_expense(description_keyword: str, **kwargs):
        return tools.delete_expense(description_keyword, owner=user_id)
    
    def generate_lesson(topic: str, **kwargs):
        """Generates a learning module on a specific topic or a learning plan from a job description."""
        return generate_learning_content(topic, language)

    def create_resume(user_details: str, job_description: str, **kwargs):
        """Generates a tailored resume. The user must provide their details and the target job description in the prompt."""
        return generate_tailored_resume(user_details, job_description, language)

    # The system instruction is now more complex, so I'll add the language instruction with a higher number.
    dynamic_instruction = SYSTEM_INSTRUCTION + f"\n14. Language: You MUST ALWAYS respond to the user in {language}."
    config = genai.types.GenerateContentConfig(
        system_instruction=dynamic_instruction,
        tools=[
            read_todo_list,
            add_task,
            update_task,
            delete_task,
            update_task_status,
            log_report,
            read_routines,
            add_expense,
            read_expenses,
            clear_done_tasks,
            delete_expense,
            generate_lesson,
            create_resume,
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
            continue

    # If all models failed, return the clearest error possible
    if last_error:
        le = str(last_error)
        if "RESOURCE_EXHAUSTED" in le or "quota" in le.lower() or "429" in le or "404" in le or "NOT_FOUND" in le:
            if OLLAMA_AVAILABLE:
                try:
                    print(f"Falling back to local offline model: {OFFLINE_MODEL}...")
                    ollama_msgs = [{"role": "system", "content": dynamic_instruction + "\n[SYSTEM NOTICE: You are running in OFFLINE FALLBACK MODE because the primary API quota is exhausted. You CANNOT execute tools (add_task, delete_task, etc.) right now. Provide helpful advice or conversational responses instead.]"}]
                    for m in messages:
                        role = "assistant" if getattr(m, "role", "") == "model" else getattr(m, "role", "user")
                        text = ""
                        if getattr(m, 'parts', None):
                            for p in m.parts:
                                if getattr(p, 'text', None):
                                    text += p.text + "\n"
                        if text.strip():
                            ollama_msgs.append({"role": role, "content": text.strip()})
                    ollama_msgs.append({"role": "user", "content": prompt})
                    
                    response = ollama.chat(model=OFFLINE_MODEL, messages=ollama_msgs)
                    return response['message']['content'], history or []
                except Exception as ollama_err:
                    print(f"Offline fallback failed: {ollama_err}")
                    hint = f"\n\n*(Hint: Open your terminal and run `ollama pull {OFFLINE_MODEL}` to download the model)*" if "not found" in str(ollama_err).lower() else ""
                    return f"⏳ **Offline Fallback Failed**: The Google API limit was reached, but the local offline model ('{OFFLINE_MODEL}') also failed. Ensure Ollama is running.{hint}\n\n*Ollama Error*: `{ollama_err}`\n\n*Original API Error*: `{le}`", history or []
            else:
                return f"⏳ **API Issue/Quota Exceeded**: Google API limit reached or model unavailable. You may have hit the daily free tier limit, or your API key's project requires billing setup.\n\n*Detailed Error*: `{le}`\n\n*(Note: To enable the backend offline AI fallback, install Ollama from ollama.com and run `pip install ollama`)*", history or []
                
        if ("UNAVAILABLE" in le) or ("503" in le) or ("high demand" in le.lower()):
            return "I am currently experiencing high demand and am temporarily unavailable. Please try again in a few moments.", history or []
    return f"Error: {str(last_error)}", history or []
    
def generate_learning_content(topic_or_jd: str, language: str = "English") -> str:
    """Generates a learning module on a specific topic or a learning plan from a job description."""
    if not api_key or not client:
        return "Error: GOOGLE_API_KEY not found. Please set it to enable Agentic AI features."

    is_job_description = len(topic_or_jd.split()) > 30 # Heuristic to detect a JD

    if is_job_description:
        prompt = f"""
        You are an expert career coach and technical tutor. The user has provided a job description and wants a learning plan to acquire the necessary skills.

        Job Description:
        ---
        {topic_or_jd}
        ---

        Please analyze the job description in {language} and generate a structured learning plan. For each key skill or technology identified, provide a mini-learning module with this exact structure:
        1. **Basic Concepts**: Explain the topic simply and clearly.
        2. **Key Areas to Focus On**: List the most important sub-topics relevant to the job description.
        3. **Learning Resources**: Suggest 1-2 high-quality online resources (like official documentation, tutorials, or articles) to learn the topic.
        
        Organize the output by the most important skills first.
        """
    else:
        prompt = f"""
        You are an expert educational tutor. The user wants to learn about: '{topic_or_jd}'.
        
        Please generate a comprehensive learning module in {language} following this exact structure:
        1. **Basic Concepts**: Explain the topic simply and clearly.
        2. **Syntax & Examples**: Provide code snippets or practical examples depending on the topic.
        3. **Practice Quiz**: Provide 3 to 5 objective questions (multiple choice) to test the user's knowledge.
        4. **Answers**: Provide the correct answers for the quiz at the very end.
        """
    
    last_error = None
    for model_name in MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return extract_response_text(response)
        except Exception as e:
            last_error = e
            print(f"Model {model_name} failed for learning content: {e}")
            continue
            
    if last_error:
        le = str(last_error)
        if "RESOURCE_EXHAUSTED" in le or "quota" in le.lower() or "429" in le or "404" in le or "NOT_FOUND" in le:
            if OLLAMA_AVAILABLE:
                try:
                    print(f"Falling back to local offline model: {OFFLINE_MODEL}...")
                    response = ollama.chat(model=OFFLINE_MODEL, messages=[{"role": "user", "content": prompt}])
                    return response['message']['content']
                except Exception as e:
                    print(f"Offline fallback failed: {e}")
                    hint = f"\n\n*(Hint: Open your terminal and run `ollama pull {OFFLINE_MODEL}` to download the model)*" if "not found" in str(e).lower() else ""
                    return f"⏳ **Offline Fallback Failed**: Ensure Ollama is running.{hint}\n*Ollama Error*: `{e}`\n\n*Original API Error*: `{le}`"
            else:
                return f"⏳ **API Issue/Quota Exceeded**: Google API limit reached or model unavailable. You may have hit the daily free tier limit, or your API key requires billing setup.\n\n*Detailed Error*: `{le}`\n\n*(Note: To enable the backend offline AI fallback, install Ollama from ollama.com and run `pip install ollama`)*"
        if ("UNAVAILABLE" in le) or ("503" in le) or ("high demand" in le.lower()):
            return "I am currently experiencing high demand and am temporarily unavailable. Please try again in a few moments."
        return f"Failed to generate learning content. Error: {le}"

    return "Failed to generate learning content. Please try again later."

def generate_tailored_resume(user_info: str, job_desc: str, language: str = "English") -> str:
    """Generates a professionally formatted resume based on user details and job description."""
    if not api_key or not client:
        return "Error: GOOGLE_API_KEY not found. Please set it to enable Agentic AI features."

    prompt = f"""
    You are an Expert Executive Resume Writer and Career Coach. 
    The user wants to tailor their resume for a specific Job Description.

    User Details & Raw Resume Data:
    {user_info}

    Target Job Description:
    {job_desc}

    Please generate a professional, highly-tailored resume in {language} based ONLY on the provided user details. 
    Align their experience, projects, and skills to highlight their fit for the Job Description.
    Format the resume cleanly using plain text. 
    RULES FOR FORMATTING: 
    - Use ALL CAPS for section headers (e.g., SUMMARY, SKILLS, EXPERIENCE, EDUCATION, PROJECTS).
    - Do NOT use asterisks (*) or hash symbols (#) for markdown headers. 
    - Use standard dash (-) for bullet points.
    """
    
    last_error = None
    for model_name in MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return extract_response_text(response)
        except Exception as e:
            last_error = e
            print(f"Model {model_name} failed for tailored resume: {e}")
            continue
            
    if last_error:
        le = str(last_error)
        if "RESOURCE_EXHAUSTED" in le or "quota" in le.lower() or "429" in le or "404" in le or "NOT_FOUND" in le:
            if OLLAMA_AVAILABLE:
                try:
                    print(f"Falling back to local offline model: {OFFLINE_MODEL}...")
                    response = ollama.chat(model=OFFLINE_MODEL, messages=[{"role": "user", "content": prompt}])
                    return response['message']['content']
                except Exception as e:
                    print(f"Offline fallback failed: {e}")
                    hint = f"\n\n*(Hint: Open your terminal and run `ollama pull {OFFLINE_MODEL}` to download the model)*" if "not found" in str(e).lower() else ""
                    return f"⏳ **Offline Fallback Failed**: Ensure Ollama is running.{hint}\n*Ollama Error*: `{e}`\n\n*Original API Error*: `{le}`"
            else:
                return f"⏳ **API Issue/Quota Exceeded**: Google API limit reached or model unavailable. You may have hit the daily free tier limit, or your API key requires billing setup.\n\n*Detailed Error*: `{le}`\n\n*(Note: To enable the backend offline AI fallback, install Ollama from ollama.com and run `pip install ollama`)*"
        if ("UNAVAILABLE" in le) or ("503" in le) or ("high demand" in le.lower()):
            return "I am currently experiencing high demand and am temporarily unavailable. Please try again in a few moments."
        return f"Failed to generate tailored resume. Error: {le}"

    return "Failed to generate tailored resume. Please try again later."

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
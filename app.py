# asyncio monkeypatch for Windows (fixes ConnectionResetError WinError 10054)
import sys
if sys.platform == 'win32':
    import asyncio
    from asyncio import proactor_events
    
    _orig_call_connection_lost = proactor_events._ProactorBasePipeTransport._call_connection_lost
    def _patched_call_connection_lost(self, exc):
        try:
            _orig_call_connection_lost(self, exc)
        except (ConnectionResetError, BrokenPipeError):
            pass
    proactor_events._ProactorBasePipeTransport._call_connection_lost = _patched_call_connection_lost

import streamlit as st
import asyncio
try:
    import websockets
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
import os
import re
import threading
import tempfile
from dotenv import load_dotenv
import time
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
import base64
import json
import uuid
import smtplib
from email.message import EmailMessage
import requests
import urllib.parse
try:
    from PyPDF2 import PdfReader
    from fpdf import FPDF
    PDF_TOOLS_AVAILABLE = True
except ImportError:
    PDF_TOOLS_AVAILABLE = False

from auth0_server_python.auth_server.server_client import ServerClient
from auth0_server_python.auth_types import LogoutOptions, StartInteractiveLoginOptions, StateData, TransactionData
from auth0_server_python.store.abstract import AbstractDataStore
from agent import run_autonomous_agent, save_chat_state, load_chat_state, clear_chat_state, generate_learning_content, generate_tailored_resume
import tools # Import the whole module to access context
from auth import SessionManager, PasswordHandler, AuthenticationError, SECURITY_QUESTIONS
from translations import get_text

load_dotenv()

# --- Auth0 SDK Streamlit Store Implementation ---
class FileDataStore(AbstractDataStore):
    def __init__(self, secret, model, file_name):
        super().__init__({"secret": secret})
        self.model = model
        self.file_name = file_name

    def _load(self):
        if os.path.exists(self.file_name):
            try:
                with open(self.file_name, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self, data):
        with open(self.file_name, "w") as f:
            json.dump(data, f)

    async def set(self, identifier, state, options=None, **_):
        data = state.model_dump() if hasattr(state, "model_dump") else state
        store = self._load()
        store[identifier] = self.encrypt(identifier, data)
        self._save(store)

    async def get(self, identifier, options=None):
        store = self._load()
        encrypted = store.get(identifier)
        if encrypted:
            return self.model.model_validate(self.decrypt(identifier, encrypted))
        return None

    async def delete(self, identifier, options=None, **_):
        store = self._load()
        if identifier in store:
            del store[identifier]
            self._save(store)

def get_auth0_client():
    session_secret = os.getenv("AUTH0_SECRET", "0000000000000000000000000000000000000000000000000000000000000000")
    return ServerClient(
        domain=os.getenv("AUTH0_DOMAIN", ""),
        client_id=os.getenv("AUTH0_CLIENT_ID", ""),
        client_secret=os.getenv("AUTH0_CLIENT_SECRET", ""),
        redirect_uri=os.getenv("APP_BASE_URL", "http://localhost:8501").rstrip("/") + "/callback",
        authorization_params={"scope": "openid profile email"},
        secret=session_secret,
        state_store=FileDataStore(session_secret, StateData, "auth0_sessions.json"),
        transaction_store=FileDataStore(session_secret, TransactionData, "auth0_transactions.json"),
    )

# --- WebSocket Server for Real-Time Multiplayer Sync ---
WS_PORT = 8765
WS_HOST = os.getenv("WEBSOCKET_HOST", "localhost")
connected_clients = set()
ws_loop = None

async def ws_handler(websocket, *args, **kwargs):
    """Manage active WebSocket connections from the frontend."""
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            pass
    except Exception:
        pass
    finally:
        connected_clients.remove(websocket)

async def ws_main():
    """Async context for running the WebSocket server."""
    try:
        async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
            await asyncio.Future()  # Run forever
    except OSError:
        # Port already in use (likely due to Streamlit's auto-reloader)
        pass

def run_ws_server():
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)
    try:
        server = websockets.serve(ws_handler, WS_HOST, WS_PORT)
        ws_loop.run_until_complete(server)
        ws_loop.run_forever()
    except OSError:
        # Port already in use (likely due to Streamlit's auto-reloader)
        ws_loop.run_until_complete(ws_main())
    except Exception:
        pass

if WS_AVAILABLE:
    @st.cache_resource
    def start_websocket_server():
        """Start the WebSocket broadcaster in a background daemon thread."""
        t = threading.Thread(target=run_ws_server, daemon=True)
        t.start()
        return True
    start_websocket_server()

def broadcast_update():
    """Broadcast an update event to all active connected browser clients."""
    global ws_loop
    if WS_AVAILABLE and ws_loop and connected_clients:
        try:
            asyncio.run_coroutine_threadsafe(
                asyncio.gather(*(ws.send("update") for ws in connected_clients)),
                ws_loop
            )
        except Exception:
            pass

def render_websocket_client():
    """Inject JS to listen for remote updates and trigger browser notifications."""
    if not WS_AVAILABLE:
        return
    js = f"""
    <script>
        if (!window.wsSyncConnected) {{
            const ws = new WebSocket('ws://{WS_HOST}:{WS_PORT}');
            ws.onmessage = function(event) {{
                if (event.data === 'update' && Notification.permission === 'granted') {{
                    new Notification('Smart Task Agent', {{ body: 'Task board updated remotely by another device or AI.' }});
                }}
            }};
            window.wsSyncConnected = true;
        }}
    </script>
    """
    st.html(js)

def parse_task_name_from_prompt(prompt: str) -> str | None:
    """Extract a direct task name from an explicit add-task request."""
    if not prompt or not isinstance(prompt, str):
        return None

    prompt_clean = prompt.strip()
    
    # Prevent predefined AI command prompts from being misidentified as tasks
    quick_prompts = [
        "Analyze my current workload",
        "Suggest priorities for today",
        "Break down a complex task",
        "Create a daily technical summary"
    ]
    if prompt_clean.lower() in [q.lower() for q in quick_prompts]:
        return None

    # Look for clear add task instructions like "add task demo", "create task demo", "add task called demo"
    match = re.search(r"\b(?:add|create)(?:\s+(?:a|an|new|a new|an new))?\s+(?:task\s+)?[\"']?(?P<task>[^\"'\n]+?)(?:[\"']|\s+with\b|\s+for\b|\s+today\b|\s+now\b|\s+to\s+my\s+tasks\b|\s+to\s+todo\b|\s+to\s+my\s+list\b|\s+to\s+my\s+task\s+list\b|$)", prompt_clean, flags=re.IGNORECASE)
    if match:
        task = match.group('task').strip()
        if task:
            return task

    # Fallback for prompts like "add demo to my tasks" or "please create task demo to my list"
    normalized = prompt_clean
    for suffix in [" to my tasks", " to todo", " to my list", " as a task", " to my task list"]:
        if normalized.lower().endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    match = re.search(r"\b(?:add|create)(?:\s+(?:a|an|new|a new|an new))?\s+(?:task\s+)?(?P<task>.+)", normalized, flags=re.IGNORECASE)
    if match:
        task = match.group('task').strip(" '")
        if task and len(task.split()) <= 10:
            return task

    return None

def create_pdf(text: str):
    """Creates a basic formatted PDF byte stream out of simple text using fpdf."""
    if not PDF_TOOLS_AVAILABLE:
        return None
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=11)
        
        text = text.replace('•', '-') # Sanitize common unicode bullet
        for line in text.split('\n'):
            safe_line = line.encode('latin-1', 'replace').decode('latin-1')
            if safe_line.isupper() and len(safe_line.strip()) > 3:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, txt=safe_line, ln=True)
                pdf.set_font("Arial", size=11)
            else:
                pdf.multi_cell(0, 6, txt=safe_line)
                
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf.output(tmp.name)
            with open(tmp.name, "rb") as f:
                pdf_bytes = f.read()
        os.remove(tmp.name)
        return pdf_bytes
    except Exception:
        return None

def mask_mobile(mobile):
    """Helper to mask mobile numbers or emails for privacy."""
    val = str(mobile).strip()
    if not val or val.lower() == "nan" or val.lower() == "guest":
        return "guest" if val.lower() == "guest" else ""
    if val.lower() == "demo_user":
        return "Demo User"
        
    # Handle email masking if logged in via SSO
    if "@" in val:
        parts = val.split("@")
        if len(parts[0]) > 2:
            return f"{parts[0][:2]}***@{parts[1]}"
        return f"*@{parts[1]}"
        
    if len(val) <= 4:
        return "****"
    return f"{val[:2]}******{val[-2:]}"

def get_default_language():
    """Guess default language based on user IP geolocation."""
    try:
        # Fast, free IP geolocation
        response = requests.get('https://ipapi.co/json/', timeout=3)
        if response.status_code == 200:
            country = response.json().get("country_code", "")
            mapping = {
                "CN": "Mandarin Chinese", "TW": "Mandarin Chinese", "HK": "Mandarin Chinese",
                "IN": "Hindi",
                "ES": "Spanish", "MX": "Spanish", "AR": "Spanish", "CO": "Spanish", "PE": "Spanish", "CL": "Spanish", "VE": "Spanish",
                "AE": "Standard Arabic", "SA": "Standard Arabic", "EG": "Standard Arabic", "IQ": "Standard Arabic", "MA": "Standard Arabic", "DZ": "Standard Arabic",
                "FR": "French", "SN": "French", "CI": "French", "CD": "French",
                "BD": "Bengali",
                "BR": "Portuguese", "PT": "Portuguese", "AO": "Portuguese", "MZ": "Portuguese",
                "RU": "Russian", "BY": "Russian", "KZ": "Russian",
                "PK": "Urdu"
            }
            return mapping.get(country, "English")
    except Exception:
        pass
    return "English"

def init_session_state():
    """Initialize session state for authentication."""
    if "checkbox_suffix" not in st.session_state:
        st.session_state.checkbox_suffix = 0
    if "language" not in st.session_state:
        st.session_state.language = get_default_language()
    if "current_user" not in st.session_state:
        # 1. Check for Auth0 authorization code callback
        if "code" in st.query_params and "state" in st.query_params:
            auth0 = get_auth0_client()
            app_base = os.getenv("APP_BASE_URL", "http://localhost:8501").rstrip("/")
            q_params = urllib.parse.urlencode(st.query_params)
            req_url = f"{app_base}/callback?{q_params}"
            
            if os.getenv("AUTH0_DOMAIN"):
                try:
                    async def process_auth0_login():
                        await auth0.complete_interactive_login(
                            url=req_url, 
                            store_options={"query_params": st.query_params}
                        )
                        return await auth0.get_user(store_options={})
                        
                    user_info = asyncio.run(process_auth0_login())
                    if user_info:
                        user_id = user_info.get("email") or user_info.get("nickname") or user_info.get("sub")
                        if user_id:
                            st.session_state.current_user = user_id
                            st.session_state.auth_method = "Auth0 SSO"
                            st.query_params.clear() # type: ignore
                            return
                except Exception as e:
                    print(f"Auth0 SSO Error: {e}")

        # 2. Check for persistent session in query parameters to handle page refreshes
        if "u" in st.query_params:
            token_param = st.query_params.get("u")
            token = token_param[0] if isinstance(token_param, list) and token_param else token_param
            
            mobile = SessionManager.get_mobile_from_session(token)
            if mobile:
                st.session_state.current_user = mobile
                st.session_state.auth_method = "PIN"
            else:
                st.session_state.current_user = "guest"
        else:
            st.session_state.current_user = "guest"

def load_todo_df(current_user):
    """Loads the todo list into a DataFrame, handles 24h deletion, and sorts."""
    required_cols = ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]

    try:
        if os.path.exists(tools.TODO_FILE):
            df = pd.read_csv(tools.TODO_FILE, dtype={'Owner': str, 'SharedWith': str})
        else:
            df = pd.DataFrame(columns=required_cols)
    except Exception:
        df = pd.DataFrame(columns=required_cols)

    if 'Time' in df.columns:
        df = df.drop(columns=['Time'])

    # Ensure required columns exist with safe defaults and proper dtypes
    for col in required_cols:
        if col not in df.columns:
            if col == 'Priority':
                df[col] = 'High'
            elif col == 'Owner':
                df[col] = current_user
            elif col == 'SharedWith':
                df[col] = ''
            elif col == 'Date':
                # Use NaT-aware dtype
                df[col] = pd.Series([pd.NaT] * len(df))
            elif col == 'CompletedAt':
                df[col] = pd.Series([pd.NaT] * len(df))
            else:
                df[col] = None

    # Normalize Owner and SharedWith to string to avoid float inference
    df['Owner'] = df['Owner'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
    df['SharedWith'] = df['SharedWith'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')

    # Convert CompletedAt to datetime safely
    try:
        df['CompletedAt'] = pd.to_datetime(df['CompletedAt'], errors='coerce')
    except Exception:
        df['CompletedAt'] = pd.to_datetime(pd.Series([pd.NaT] * len(df)))

    # --- Logic: Auto-delete "Done" tasks after 24 hours ---
    if not df.empty:
        cutoff = datetime.now() - timedelta(hours=24)
        mask = (df['Status'] == 'Done') & (df['CompletedAt'].notna()) & (df['CompletedAt'] < cutoff)
        if mask.any():
            # Filter in memory only to prevent Rerun Loop on production
            df = df[~mask]

    # Privacy Filtering: owner OR explicitly shared. Guests only see their own tasks.
    def is_visible(row):
        try:
            if row.get('Owner') == current_user:
                return True
            if current_user == "guest":
                return False
            shared_list = [s.strip() for s in str(row.get('SharedWith', '')).split(',') if s.strip()]
            return current_user in shared_list
        except Exception:
            return False

    if not df.empty:
        user_mask = df.apply(is_visible, axis=1)
        df = df[user_mask].copy()

    # Ensure Date column exists and convert to date objects for Streamlit
    if 'Date' not in df.columns:
        df['Date'] = pd.Series([pd.NaT] * len(df))
    try:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
    except Exception:
        # Last-resort: fill with NaT/date.today placeholders to keep types consistent
        df['Date'] = pd.Series([datetime.now().date() if pd.isna(x) else x for x in df.get('Date', pd.Series([pd.NaT] * len(df)))])

    # Automatic sorting by Date
    if not df.empty:
        priority_order = {"High": 0, "Medium": 1, "Low": 2}
        df['p_val'] = df['Priority'].map(priority_order).fillna(3)
        try:
            df = df.sort_values(by=["Date", "p_val"]).drop(columns=['p_val']).reset_index(drop=True)
        except Exception:
            # If sorting fails due to mixed types, fallback to unsorted
            df = df.drop(columns=['p_val']).reset_index(drop=True)

    return df

def load_expenses_df(current_user):
    """Loads the expenses list into a DataFrame."""
    required_cols = ["Date", "Amount", "Category", "Description", "Owner"]

    try:
        if os.path.exists(tools.EXPENSES_FILE):
            df = pd.read_csv(tools.EXPENSES_FILE, dtype={'Owner': str})
        else:
            df = pd.DataFrame(columns=required_cols)
    except Exception:
        df = pd.DataFrame(columns=required_cols)

    for col in required_cols:
        if col not in df.columns:
            if col == 'Owner': df[col] = current_user
            elif col == 'Amount': df[col] = 0.0
            else: df[col] = ""

    df['Owner'] = df['Owner'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
    
    if not df.empty:
        df = df[df['Owner'] == current_user].copy()
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)
        df = df.sort_values(by="Date", ascending=False).reset_index(drop=True)

    return df

def render_auth_ui():
    """Render the secure authentication UI with encrypted PIN."""
    init_session_state()
    lang = st.session_state.language
    language_options = ["English", "Mandarin Chinese", "Hindi", "Spanish", "Standard Arabic", "French", "Bengali", "Portuguese", "Russian", "Urdu"]
    st.sidebar.selectbox(get_text("🌐 Language / भाषा / Idioma", lang), language_options, key="language")
    lang = st.session_state.language # Refresh after selection change
    st.sidebar.title(get_text("🔐 Sign In / Register", lang))
    
    if st.session_state.current_user == "guest":
        st.sidebar.subheader(get_text("🚀 Quick Test", lang))
        st.sidebar.info(get_text("Want to test features without registering?", lang))
        if st.sidebar.button(get_text("Login as Demo User", lang), use_container_width=True):
            st.session_state.current_user = "demo_user"
            st.session_state.auth_method = "Demo"
            st.rerun()
            
        st.sidebar.divider()
        st.sidebar.subheader(get_text("🌐 Login with Email / Social", lang))
        
        if os.getenv("AUTH0_DOMAIN") and os.getenv("AUTH0_CLIENT_ID"):
            auth0 = get_auth0_client()
            auth_url = asyncio.run(auth0.start_interactive_login(
                options=StartInteractiveLoginOptions(),
                store_options={}
            ))
            st.sidebar.markdown(f'<a href="{auth_url}" target="_self"><button style="width:100%; padding:0.5rem; background-color:#4CAF50; color:white; border:none; border-radius:4px; cursor:pointer;">{get_text("Continue with Email / Social", lang)}</button></a>', unsafe_allow_html=True)
            st.sidebar.caption(get_text("Secure Login", lang))
        else:
            st.sidebar.info("Auth0 SSO is not configured. Set `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, and `AUTH0_SECRET` in `.env`.")
            
        st.sidebar.divider()

        st.sidebar.subheader(get_text("📱 Mobile Number & PIN", lang))
        mobile_input = st.sidebar.text_input(get_text("Mobile Number", lang), placeholder="e.g. 9876543210", key="auth_mobile")
        pin_input = st.sidebar.text_input(get_text("6-Digit PIN", lang), type="password", help="Enter your 6-digit PIN", key="auth_pin")
        remember_me = st.sidebar.checkbox(get_text("Remember Me", lang), value=True, help="Keep me logged in even after page refresh")

        if not mobile_input or len(mobile_input) < 10:
            st.sidebar.warning(get_text("⚠️ Enter a valid mobile number", lang))
            return "guest"

        col_reg, col_log = st.sidebar.columns(2)

        with col_reg:
            if st.button(get_text("📝 Register", lang), use_container_width=True):
                st.session_state.show_reg_form = True

        if st.session_state.get("show_reg_form", False):
            with st.sidebar.expander(get_text("Complete Registration", lang), expanded=True):
                q = st.selectbox(get_text("Security Question", lang), SECURITY_QUESTIONS)
                a = st.text_input(get_text("Answer", lang), placeholder="Your secret answer")
                if st.button(get_text("Confirm Registration", lang), use_container_width=True):
                    try:
                        if PasswordHandler.register(mobile_input, pin_input, q, a):
                            st.success(get_text("Account created!", lang))
                            st.session_state.show_reg_form = False
                            st.rerun()
                    except AuthenticationError as e:
                        st.error(str(e))

        with col_log:
            if st.button(get_text("🔐 Login", lang), use_container_width=True):
                try:
                    if PasswordHandler.login(mobile_input, pin_input):
                        st.session_state.current_user = mobile_input
                        # Persist session token in query params to survive page refresh if requested
                        if remember_me:
                            token = SessionManager.create_session(mobile_input)
                            st.query_params["u"] = token
                        st.session_state.auth_method = "PIN"
                        st.rerun()
                except AuthenticationError as e:
                    st.sidebar.error(str(e))

        if st.sidebar.button(get_text("❓ Forgot PIN?", lang), use_container_width=True):
            st.session_state.forgot_pin_flow = True

        if st.session_state.get("forgot_pin_flow", False):
            with st.sidebar.expander(get_text("Recover PIN", lang), expanded=True):
                try:
                    question = PasswordHandler.get_user_security_question(mobile_input)
                    st.write(f"**Question**: {question}")
                    ans = st.text_input(get_text("Answer", lang), type="password")
                    if st.button(get_text("Verify & Show New PIN", lang)):
                        new_p = PasswordHandler.verify_answer_and_reset_pin(mobile_input, ans)
                        st.success(get_text("Recovery Successful!", lang))
                        st.code(f"Your NEW PIN is: {new_p}")
                        st.warning(get_text("⚠️ Write this down! This message will disappear on refresh.", lang))
                except AuthenticationError as e:
                    st.error(str(e))
                if st.button(get_text("Cancel", lang)):
                    st.session_state.forgot_pin_flow = False
                    st.rerun()
            
        st.sidebar.divider()
        return "guest"
        
    else:
        # User is logged in
        st.sidebar.success(f"{get_text('✅ Logged in as:', lang)} **{mask_mobile(st.session_state.current_user)}**")
        auth_method_display = f" ({st.session_state.auth_method})" if st.session_state.auth_method else ""
        st.sidebar.caption(f"{get_text('Auth Method:', lang)} {auth_method_display}")
        
        if st.sidebar.button(get_text("🚪 Logout", lang), use_container_width=True):
            if "u" in st.query_params:
                token_param = st.query_params.get("u")
                token = token_param[0] if isinstance(token_param, list) and token_param else token_param
                SessionManager.clear_session(token)
                
            if st.session_state.auth_method == "Auth0 SSO":
                auth0 = get_auth0_client()
                logout_url = asyncio.run(auth0.logout(
                    options=LogoutOptions(return_to=os.getenv("APP_BASE_URL", "http://localhost:8501")),
                    store_options={}
                ))
                st.session_state.current_user = "guest"
                st.session_state.auth_method = None
                st.query_params.clear() # type: ignore
                safe_url = logout_url.replace('&', '&amp;')
                st.markdown(f'<meta http-equiv="refresh" content="0; url={safe_url}">', unsafe_allow_html=True)
                st.stop()
            else:
                st.session_state.current_user = "guest"
                st.session_state.auth_method = None
                st.query_params.clear() # type: ignore
                st.rerun()
        
        return st.session_state.current_user


def main():
    # Set page configuration (This MUST be the first Streamlit command and called only once)
    st.set_page_config(page_title="Smart Task Manager - AI Powered Assistant", page_icon="🚀", layout="wide")

    # Load Google Analytics ID from .env
    ga_id = os.getenv("GA_MEASUREMENT_ID")
    ga_script = ""
    if ga_id:
        ga_script = f"""
        <!-- Google Analytics (GA4) Tracking Snippet -->
        <script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          gtag('config', '{ga_id}');
        </script>
        """

    # Inject SEO Meta Tags, JSON-LD structured data, and Google Analytics
    st.markdown(f"""
        <meta name="description" content="Smart Task Manager: An AI-powered task assistant using Streamlit and Gemini. Features automated analysis, persistent history, resume builder, expense tracker, and real-time productivity metrics.">
        <meta name="keywords" content="AI Task Manager, Productivity Tracker, Autonomous AI Agent, Expense Tracker, AI Resume Builder, Smart Task Management, Gemini AI, Task Automation, Learning Hub, Punctuality Tracker">
        <meta name="author" content="Smart Task Manager">
        <meta name="robots" content="index, follow">
        <meta property="og:title" content="Smart Task Manager - AI Powered Assistant">
        <meta property="og:description" content="Boost your productivity with an Autonomous AI Agent that manages tasks, tracks expenses, and builds your resume.">
        <meta property="og:type" content="website">
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          "name": "Smart Task Manager",
          "operatingSystem": "Web",
          "applicationCategory": "ProductivityApplication",
          "description": "An AI-powered task assistant using Gemini, featuring automated analysis, persistent history, resume builder, expense tracker, and real-time productivity metrics tracking.",
          "offers": {{ "@type": "Offer", "price": "0", "priceCurrency": "USD" }}
        }}
        </script>
        {ga_script}
    """, unsafe_allow_html=True)

    # Initialize state at the very beginning
    init_session_state()

    # Render authentication UI
    current_user = render_auth_ui()
    
    # CRITICAL: Set the user context for tool execution (like archiving)
    tools.context.user = current_user

    # Custom CSS for status font colors
    st.markdown("""
        <style>
        .status-pending { color: #FF4B4B; font-weight: bold; }
        .status-working { color: #FFD700; font-weight: bold; }
        .status-done { color: #008000; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    st.title(get_text("🤖 Smart Task Manager Agent", st.session_state.language))

    # API Key Warning
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("🔑 **Action Required**: Please set the `GOOGLE_API_KEY` environment variable to enable Agentic AI features.")
    
    # Guest Account Warning
    if current_user == "guest":
        st.warning(get_text("⚠️  **Guest Mode**: Your tasks are visible to others. Please login to secure your data.", st.session_state.language))
        st.info(get_text("As a guest, you cannot use the AI assistant, save tasks, or view archives.", st.session_state.language))


    render_dashboard(current_user)

def style_status(row):
    color = ''
    if row['Status'] == 'Pending': color = 'color: #FF4B4B; font-weight: bold;'
    elif row['Status'] == 'Working': color = 'color: #FFD700; font-weight: bold;'
    elif row['Status'] == 'Done': color = 'color: #008000; font-weight: bold;'
    return [color if i == 'Status' else '' for i in row.index]

# --- Routine Alert System ---

# A short, royalty-free notification sound encoded in base64
BEEP_SOUND_BASE64 = "data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjMyLjEwNAAAAAAAAAAAAAAA//tAwAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAAEAAABIADAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1axcBAAAAAAAAADhVVT/2R/+3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//ahcBAAAAAAAAADhVVT/2R/+3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//3//-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV-TEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
ROUTINES_FILE = "routines.json"

def load_routines_data():
    """Load user routines and check-in history from disk."""
    if os.path.exists(ROUTINES_FILE):
        try:
            with open(ROUTINES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Cleanup old routine history: past one month data deleted on 15th
            now = datetime.now()
            current_month_str = now.strftime("%Y-%m")
            prev_month_str = f"{now.year - 1}-12" if now.month == 1 else f"{now.year}-{now.month - 1:02d}"
            
            changed = False
            for user, user_data in data.items():
                if isinstance(user_data, dict) and "history" in user_data:
                    dates_to_delete = [
                        date_str for date_str in user_data["history"]
                        if not (date_str.startswith(current_month_str) or 
                               (date_str.startswith(prev_month_str) and now.day < 15))
                    ]
                    for d in dates_to_delete:
                        del user_data["history"][d]
                        changed = True
                        
            if changed:
                with open(ROUTINES_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            return data
        except Exception:
            pass
    return {}

def save_routines_data(data):
    """Persist user routines and check-in history to disk."""
    with open(ROUTINES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def send_routine_notifications(routine_name, time_str, action):
    """Dispatch notifications via JS (Browser TTS/Desktop), Email, and Telegram."""
    message = f"Routine Alert: It is time to {action} {routine_name} at {time_str}"
    
    # 1. Browser TTS and Desktop Notification
    js_code = f"""
    <script>
        const message = "{message}";
        if ('speechSynthesis' in window) {{
            var msg = new SpeechSynthesisUtterance(message);
            window.speechSynthesis.speak(msg);
        }}
        if (Notification.permission === 'granted') {{
            new Notification('Smart Task Agent', {{ body: message }});
        }} else if (Notification.permission !== 'denied') {{
            Notification.requestPermission().then(function(permission) {{
                if (permission === 'granted') {{
                    new Notification('Smart Task Agent', {{ body: message }});
                }}
            }});
        }}
    </script>
    """
    st.html(js_code)

    # 2. Gmail Notification
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    if gmail_user and gmail_pass:
        try:
            msg = EmailMessage()
            msg.set_content(message)
            msg['Subject'] = 'Smart Task Agent: Routine Reminder'
            msg['To'] = gmail_user
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(gmail_user, gmail_pass)
                server.send_message(msg)
        except Exception as e:
            print(f"Failed to send email: {e}")

    # 3. Telegram Notification
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            requests.post(url, json={'chat_id': chat_id, 'text': f"🔔 {message}"}, timeout=5)
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")

def check_routine_alerts(current_user):
    """Displays global alerts for check-ins/outs based on time."""
    if current_user == "guest":
        return
        
    data = load_routines_data()
    if current_user not in data:
        return
        
    user_data = data[current_user]
    today_str = datetime.now().strftime("%Y-%m-%d")
    if today_str not in user_data["history"]:
        user_data["history"][today_str] = {}
        save_routines_data(data)
        
    today_history = user_data["history"][today_str]
    current_day_name = datetime.now().strftime("%A")
    
    todays_routines = [
        r for r in user_data["settings"] 
        if current_day_name in r.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
    ]
    
    now = datetime.now()
    now_time = now.time()
    alert_triggered = False
    
    for r in todays_routines:
        rid = r["id"]
        r_hist = today_history.get(rid, {})
        try:
            start_time = datetime.strptime(r['start'], "%H:%M").time()
            end_time = datetime.strptime(r['end'], "%H:%M").time()
        except ValueError:
            continue
            
        # Check-in Alert
        if not r_hist.get("check_in") and not r_hist.get("ci_declined"):
            if now_time >= start_time:
                ci_snoozes = r_hist.get("ci_snoozes", 0)
                last_snooze_str = r_hist.get("ci_last_snooze")
                
                alert_active = True
                if last_snooze_str:
                    try:
                        last_snooze_dt = datetime.strptime(last_snooze_str, "%H:%M")
                        last_snooze_dt = now.replace(hour=last_snooze_dt.hour, minute=last_snooze_dt.minute, second=0)
                        if now < last_snooze_dt + timedelta(minutes=5):
                            alert_active = False
                    except ValueError: pass
                        
                if alert_active and ci_snoozes < 3:
                    alert_triggered = True
                    
                    notify_key = f"ci_notified_{ci_snoozes}"
                    if not r_hist.get(notify_key):
                        send_routine_notifications(r['name'], r['start'], "start")
                        r_hist[notify_key] = True
                        today_history[rid] = r_hist
                        user_data["history"][today_str] = today_history
                        save_routines_data(data)
                        
                    with st.container(border=True):
                        st.warning(f"🔔 **Routine Alert**: It is time to start **{r['name']}** ({r['start']}). Are you starting now?")
                        c1, c2, c3, _ = st.columns([2, 2, 2, 6])
                        if c1.button("✅ Yes", key=f"alert_ci_yes_{rid}"):
                            r_hist["check_in"] = now.strftime("%H:%M")
                            today_history[rid] = r_hist
                            user_data["history"][today_str] = today_history
                            save_routines_data(data); st.rerun()
                        if c2.button("❌ No", key=f"alert_ci_no_{rid}"):
                            r_hist["ci_declined"] = True
                            today_history[rid] = r_hist
                            user_data["history"][today_str] = today_history
                            save_routines_data(data); st.rerun()
                        if c3.button(f"💤 Snooze ({3 - ci_snoozes})", key=f"alert_ci_snz_{rid}"):
                            r_hist["ci_snoozes"] = ci_snoozes + 1
                            r_hist["ci_last_snooze"] = now.strftime("%H:%M")
                            today_history[rid] = r_hist
                            user_data["history"][today_str] = today_history
                            save_routines_data(data); st.rerun()
                    break # Show one alert at a time

        # Check-out Alert
        if r_hist.get("check_in") and not r_hist.get("check_out") and not r_hist.get("co_declined"):
            if now_time >= end_time:
                co_snoozes = r_hist.get("co_snoozes", 0)
                last_snooze_str = r_hist.get("co_last_snooze")
                
                alert_active = True
                if last_snooze_str:
                    try:
                        last_snooze_dt = datetime.strptime(last_snooze_str, "%H:%M")
                        last_snooze_dt = now.replace(hour=last_snooze_dt.hour, minute=last_snooze_dt.minute, second=0)
                        if now < last_snooze_dt + timedelta(minutes=5):
                            alert_active = False
                    except ValueError: pass
                        
                if alert_active and co_snoozes < 3:
                    alert_triggered = True
                    
                    notify_key = f"co_notified_{co_snoozes}"
                    if not r_hist.get(notify_key):
                        send_routine_notifications(r['name'], r['end'], "end")
                        r_hist[notify_key] = True
                        today_history[rid] = r_hist
                        user_data["history"][today_str] = today_history
                        save_routines_data(data)
                        
                    with st.container(border=True):
                        st.warning(f"🔔 **Routine Alert**: It is time to end **{r['name']}** ({r['end']}). Are you checking out?")
                        c1, c2, c3, _ = st.columns([2, 2, 2, 6])
                        if c1.button("✅ Yes", key=f"alert_co_yes_{rid}"):
                            r_hist["check_out"] = now.strftime("%H:%M")
                            today_history[rid] = r_hist
                            user_data["history"][today_str] = today_history
                            save_routines_data(data); st.rerun()
                        if c2.button("❌ No", key=f"alert_co_no_{rid}"):
                            r_hist["co_declined"] = True
                            today_history[rid] = r_hist
                            user_data["history"][today_str] = today_history
                            save_routines_data(data); st.rerun()
                        if c3.button(f"💤 Snooze ({3 - co_snoozes})", key=f"alert_co_snz_{rid}"):
                            r_hist["co_snoozes"] = co_snoozes + 1
                            r_hist["co_last_snooze"] = now.strftime("%H:%M")
                            today_history[rid] = r_hist
                            user_data["history"][today_str] = today_history
                            save_routines_data(data); st.rerun()
                    break
                    
    if alert_triggered:
        audio_html = f'<audio autoplay="true" src="{BEEP_SOUND_BASE64}"></audio>'
        st.markdown(audio_html, unsafe_allow_html=True)

def render_routines(current_user):
    """Renders the Daily Routines and Punctuality tracker."""
    lang = st.session_state.language
    if current_user == "guest":
        st.info(get_text("Please log in to manage your daily routines and punctuality.", lang))
        return

    st.header(get_text("⏱️ Daily Routines & Time Tracking", lang))
    st.markdown(get_text("Track your daily habits like morning walks, job hours, and personal time. Be punctual to earn a high productivity score!", lang))
    
    data = load_routines_data()
    if current_user not in data:
        data[current_user] = {"settings": [], "history": {}}
        
    user_data = data[current_user]
    today_str = datetime.now().strftime("%Y-%m-%d")
    if today_str not in user_data["history"]:
        user_data["history"][today_str] = {}
    today_history = user_data["history"][today_str]
    
    # 1. Manage Routines Expander
    with st.expander(get_text("⚙️ Manage Routine Timings", lang), expanded=(len(user_data["settings"]) == 0)):
        with st.form("add_routine_form"):
            r_name = st.text_input(get_text("Routine Name", lang))
            c1, c2 = st.columns(2)
            r_start = c1.time_input(get_text("Expected Start Time", lang))
            r_end = c2.time_input(get_text("Expected End Time", lang))
            
            days_options = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            active_days = st.multiselect(get_text("Active Days", lang), options=days_options, default=days_options)
            
            if st.form_submit_button(get_text("➕ Add Routine", lang)):
                if r_name.strip():
                    if not active_days:
                        st.error(get_text("Please select at least one active day.", lang))
                    else:
                        user_data["settings"].append({
                            "id": str(uuid.uuid4())[:8], 
                            "name": r_name.strip(), 
                            "start": r_start.strftime("%H:%M"), 
                            "end": r_end.strftime("%H:%M"),
                            "days": active_days
                        })
                        data[current_user] = user_data
                        save_routines_data(data)
                        st.success(f"Added routine: {r_name}")
                        st.rerun()
                else:
                    st.error(get_text("Please enter a routine name.", lang))
                    
        if user_data["settings"]:
            st.markdown(get_text("**Your Defined Routines:**", lang))
            for i, r in enumerate(user_data["settings"]):
                col_del1, col_del2 = st.columns([0.9, 0.1])
                
                days_list = r.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                if len(days_list) == 7:
                    days_str = "Everyday"
                elif len(days_list) == 5 and set(days_list) == {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}:
                    days_str = "Weekdays"
                elif len(days_list) == 2 and set(days_list) == {"Saturday", "Sunday"}:
                    days_str = "Weekends"
                else:
                    days_str = ", ".join([d[:3] for d in days_list])
                    
                col_del1.write(f"- **{r['name']}**: {r['start']} to {r['end']} ({days_str})")
                if col_del2.button("🗑️", key=f"del_r_{r['id']}", help="Delete Routine"):
                    user_data["settings"].pop(i)
                    data[current_user] = user_data
                    save_routines_data(data)
                    st.rerun()

    # 2. Today's Check-ins
    if user_data["settings"]:
        st.subheader(get_text("📅 Today's Schedule & Punctuality", lang))
        
        current_day_name = datetime.now().strftime("%A")
        todays_routines = [
            r for r in user_data["settings"] 
            if current_day_name in r.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        ]
        
        if todays_routines:
            punctuality_score = 0
            completed_routines = 0
            
            for r in todays_routines:
                rid = r["id"]
                r_hist = today_history.get(rid, {})
                
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1.5])
                    
                    col1.markdown(f"**{r['name']}**  \n`{r['start']} - {r['end']}`")
                    
                    # Check-in Logic
                    if not r_hist.get("check_in"):
                        if r_hist.get("ci_declined") or r_hist.get("ci_snoozes", 0) >= 3:
                            col2.warning(get_text("Skipped", lang))
                            if col2.button(get_text("Check-In Anyway", lang), key=f"ci_anyway_{rid}", use_container_width=True):
                                r_hist["check_in"] = datetime.now().strftime("%H:%M")
                                today_history[rid] = r_hist
                                user_data["history"][today_str] = today_history
                                data[current_user] = user_data
                                save_routines_data(data)
                                st.rerun()
                        else:
                            if col2.button(get_text("🟢 Check-In", lang), key=f"ci_{rid}", use_container_width=True):
                                r_hist["check_in"] = datetime.now().strftime("%H:%M")
                                today_history[rid] = r_hist
                                user_data["history"][today_str] = today_history
                                data[current_user] = user_data
                                save_routines_data(data)
                                st.rerun()
                    else:
                        col2.success(f"In: {r_hist['check_in']}")
                    
                    # Check-out Logic
                    if r_hist.get("check_in") and not r_hist.get("check_out"):
                        if r_hist.get("co_declined") or r_hist.get("co_snoozes", 0) >= 3:
                            col3.warning(get_text("Skipped", lang))
                            if col3.button(get_text("Check-Out Anyway", lang), key=f"co_anyway_{rid}", use_container_width=True):
                                r_hist["check_out"] = datetime.now().strftime("%H:%M")
                                today_history[rid] = r_hist
                                user_data["history"][today_str] = today_history
                                data[current_user] = user_data
                                save_routines_data(data)
                                st.rerun()
                        else:
                            if col3.button(get_text("🔴 Check-Out", lang), key=f"co_{rid}", use_container_width=True):
                                r_hist["check_out"] = datetime.now().strftime("%H:%M")
                                today_history[rid] = r_hist
                                user_data["history"][today_str] = today_history
                                data[current_user] = user_data
                                save_routines_data(data)
                                st.rerun()
                    elif r_hist.get("check_out"):
                        col3.info(f"Out: {r_hist['check_out']}")
                        completed_routines += 1
                    
                    # Punctuality calculation & motivation
                    if r_hist.get("check_in"):
                        expected_start = datetime.strptime(r['start'], "%H:%M")
                        actual_start = datetime.strptime(r_hist['check_in'], "%H:%M")
                        diff_mins = (actual_start - expected_start).total_seconds() / 60
                        
                        if diff_mins <= 5: # 5 mins grace period (early is also perfect)
                            col4.success(get_text("🌟 Perfect Punctuality!", lang))
                            punctuality_score += 100
                        elif diff_mins <= 15:
                            col4.warning(get_text("👍 Good, but a bit late.", lang))
                            punctuality_score += 50
                        else:
                            col4.error(f"⏰ {int(diff_mins)} mins late.")
                            punctuality_score += 10
            
            # Global motivation based on completed routines
            st.divider()
            if completed_routines > 0:
                avg_punctuality = punctuality_score / len(todays_routines)
                st.progress(min(avg_punctuality / 100, 1.0), text=f"Overall Punctuality Score: {avg_punctuality:.0f}%")
                
                if completed_routines == len(todays_routines):
                    if avg_punctuality >= 90:
                        st.success(get_text("🏆 Master of Routines! You conquered the day with flawless punctuality.", lang))
                        st.balloons()
                    elif avg_punctuality >= 60:
                        st.info(get_text("✅ All routines completed! Focus on hitting start times perfectly tomorrow.", lang))
                    else:
                        st.warning(get_text("✅ All routines completed, but try to be more mindful of timings tomorrow.", lang))
                else:
                    st.info(f"Keep going! You have {len(todays_routines) - completed_routines} routines left today.")
        else:
            st.info(get_text("🏖️ You don't have any routines scheduled for today. Enjoy your day off!", lang))

def render_dashboard(current_user):
    """Renders the main dashboard, including metrics, table, and editor."""
    
    render_websocket_client()
    lang = st.session_state.language

    SCHOOL_QUOTES = [
        "“The roots of education are bitter, but the fruit is sweet.” – Aristotle",
        "“Success is the sum of small efforts, repeated day in and day out.” – Robert Collier",
        "“You don’t have to be great to start, but you have to start to be great.” – Zig Ziglar",
        "“Discipline is the bridge between goals and accomplishment.” – Jim Rohn",
        "“The secret of your future is hidden in your daily routine.” – Mike Murdock",
        "“Do not wait; the time will never be 'just right.' Start where you stand.” – George Herbert",
        "“We are what we repeatedly do. Excellence, then, is not an act, but a habit.” – Will Durant"
    ]
    # Pick a rotating quote based on the day of the year
    daily_quote = SCHOOL_QUOTES[datetime.now().timetuple().tm_yday % len(SCHOOL_QUOTES)]
    st.info(f"{get_text('🎓 **Daily Motivation:**', lang)} {daily_quote}")
    
    required_cols_for_metrics = ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]
    df = pd.DataFrame(columns=required_cols_for_metrics)
    
    if current_user != "guest":
        df = load_todo_df(current_user)

    # 1. Dashboard Metrics (Hide completely if guest or empty)
    if current_user != "guest" and not df.empty:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric(get_text("Total", lang), len(df))
        m2.metric(get_text("Pending ⏳", lang), len(df[df["Status"] == "Pending"]))
        m3.metric(get_text("Working 🛠️", lang), len(df[df["Status"] == "Working"]))
        m4.metric(get_text("Done ✅", lang), len(df[df["Status"] == "Done"]))
        
        # Motivational Productivity Score
        score = (len(df[df["Status"] == "Done"]) / len(df)) * 100
        m5.metric(get_text("Sprint Speed ⚡", lang), f"{score:.0f}%")

        # 2. Workload Health Notification
        pending_count = len(df[df["Status"] == "Pending"])
        if pending_count > 5:
            st.warning(get_text("🚨 **High Workload Detected**: You have {0} pending tasks. The AI suggests focusing on one High Priority task to regain momentum.", lang).format(pending_count))
        elif pending_count == 0 and len(df) > 0:
            st.success(get_text("🌟 Peak Productivity: All tasks are underway or completed. Great job!", lang))

    # 2. Status Overview (Styled Table)
    display_df = df.copy()
    if not df.empty:
        overview_state = st.session_state.get("overview_table", {})
        overview_edits = overview_state.get("edited_rows", {})
        
        display_df.insert(0, "👁️", False)
        for idx, row in display_df.iterrows():
            # Check session state to see if this specific row was toggled to reveal
            row_edits = overview_edits.get(idx, overview_edits.get(str(idx), {}))
            is_revealed = row_edits.get("👁️", False)
            
            if not is_revealed:
                display_df.at[idx, "Owner"] = mask_mobile(row.get("Owner", ""))
                if pd.notna(row.get("SharedWith")) and row.get("SharedWith"):
                    display_df.at[idx, "SharedWith"] = ", ".join([mask_mobile(s.strip()) for s in str(row["SharedWith"]).split(",") if s.strip()])

        search_query = st.text_input(get_text("🔍 Search tasks:", lang), "").lower()
        if search_query:
            display_df = display_df[display_df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)]

        with st.expander(get_text("👀 Live Status Overview", lang), expanded=True):
            if current_user == "guest":
                st.info(get_text("Please log in to view your live status overview.", lang))
            else:
                st.data_editor(
                    display_df.style.apply(style_status, axis=1),
                    width='stretch',
                    hide_index=True,
                    disabled=[col for col in display_df.columns if col != "👁️"],
                    column_config={"👁️": st.column_config.CheckboxColumn("👁️", default=False, width="small", help="Reveal mobile numbers")},
                    key="overview_table"
                )
        
        # Replace Task Distribution with Motivational Gamification System
        with st.expander(get_text("🏆 Productivity Rank & Quick Wins", lang), expanded=True):
            if current_user == "guest":
                st.info(get_text("Please log in to view your productivity rank and quick wins.", lang))
            elif not df.empty:
                done_count = len(df[df["Status"] == "Done"])
                total_count = len(df)
                efficiency = (done_count / total_count) * 100
                
                # Determine Rank based on Efficiency
                rank_title = get_text("Rookie", lang)
                rank_icon = "🔰"
                if efficiency >= 90: rank_title, rank_icon = get_text("Elite Executioner", lang), "👑"
                elif efficiency >= 70: rank_title, rank_icon = get_text("Productivity Pro", lang), "🛡️"
                elif efficiency >= 40: rank_title, rank_icon = get_text("Busy Bee", lang), "🐝"
                
                c1, c2 = st.columns([1, 2])
                c1.subheader(f"{rank_icon} {rank_title}")
                c2.progress(efficiency / 100, text=f"{get_text('Sprint Progress:', lang)} {efficiency:.0f}%")
                
                # Quick Win Motivation Logic
                pending_tasks = df[df["Status"] == "Pending"]
                if not pending_tasks.empty:
                    # Select highest priority task as the 'Fast-Track' target
                    quick_win = pending_tasks[pending_tasks["Priority"] == "High"]
                    if quick_win.empty: quick_win = pending_tasks
                    
                    target_task = quick_win.iloc[0]["Task"]
                    st.info(f"{get_text('⚡ Fast-Track Challenge:', lang)} '{target_task}' in the next 15 mins to boost your momentum!")
                elif total_count > 0:
                    st.balloons()
                    st.success(get_text("🎉 Board Cleared! You're working at light speed today. Time to celebrate!", lang))

    check_routine_alerts(current_user)

    tab_tasks, tab_routines, tab_learning, tab_resume, tab_expenses = st.tabs([
        get_text("📋 Tasks & AI Agent", st.session_state.language), 
        get_text("⏱️ Daily Routines & Punctuality", st.session_state.language),
        get_text("📚 Learning Hub", st.session_state.language),
        get_text("📄 Resume Builder", st.session_state.language),
        get_text("💰 Expense Tracker", st.session_state.language)
    ])
    col1, col2 = tab_tasks.columns([1, 2])

    with col1:
        st.subheader(get_text("📝 Task Editor", st.session_state.language))
        
        if current_user == "guest":
            st.info(get_text("Please log in to view and edit your tasks.", lang))

        # Add a button to explicitly add a new task
        if st.button(get_text("➕ Add New Task", st.session_state.language), use_container_width=True, disabled=(current_user == "guest")):
            # Use the centralized tool function to handle locking and formatting correctly
            status_msg = tools.add_task(task="New task...", priority="High", owner=current_user)
            if "Success" not in status_msg:
                st.toast(status_msg, icon="❌")
            st.rerun()

        # Add a temporary 'Delete' column for the editor
        df_editor = df.copy()
        df_editor.insert(0, "🗑️", False)
        df_editor.insert(1, "👁️", False)
        
        # Mask sensitive info in the editor while storing original values to restore on save
        original_metadata = df[['Owner', 'SharedWith']].to_dict('index')
        
        editor_state = st.session_state.get("todo_editor", {})
        edited_rows = editor_state.get("edited_rows", {})
        
        for idx, row in df_editor.iterrows():
            row_edits = edited_rows.get(idx, edited_rows.get(str(idx), {}))
            is_revealed = row_edits.get("👁️", False)
            
            if not is_revealed:
                df_editor.at[idx, "Owner"] = mask_mobile(row.get("Owner", ""))
                if pd.notna(row.get("SharedWith")) and row.get("SharedWith"):
                    df_editor.at[idx, "SharedWith"] = ", ".join([mask_mobile(s.strip()) for s in str(row["SharedWith"]).split(",") if s.strip()])

        # Normalize column dtypes to satisfy Streamlit's data_editor type checks
        df_editor["🗑️"] = df_editor["🗑️"].astype(bool)
        df_editor["👁️"] = df_editor["👁️"].astype(bool)
        df_editor["Status"] = df_editor["Status"].fillna("Pending").astype(str)
        df_editor["Priority"] = df_editor["Priority"].fillna("High").astype(str)
        if "Date" in df_editor.columns:
            # Ensure Date column is date objects (not strings) for DateColumn
            df_editor["Date"] = pd.to_datetime(df_editor["Date"], errors='coerce').dt.date
        df_editor["Task"] = df_editor["Task"].fillna("").astype(str)
        # CompletedAt should be a datetime (or NaT) for DatetimeColumn
        df_editor["CompletedAt"] = pd.to_datetime(df_editor["CompletedAt"], errors='coerce')
        df_editor["Owner"] = df_editor["Owner"].fillna("").astype(str)
        df_editor["SharedWith"] = df_editor["SharedWith"].fillna("").astype(str)

        edited_df = st.data_editor(
            df_editor,
            disabled=(current_user == "guest"),
            column_config={
                "🗑️": st.column_config.CheckboxColumn(get_text("Delete?", lang), default=False, width="small"),
                "👁️": st.column_config.CheckboxColumn("👁️", default=False, width="small", help="Reveal mobile numbers"),
                "Status": st.column_config.SelectboxColumn(
                    get_text("Status", lang),
                    options=["Pending", "Working", "Done"],
                    required=True,
                ),
                "Priority": st.column_config.SelectboxColumn(
                    get_text("Priority", lang),
                    options=["High", "Medium", "Low"],
                    required=True,
                ),
                "Date": st.column_config.DateColumn(get_text("Date", lang), format="YYYY-MM-DD", width="medium"),
                "Task": st.column_config.TextColumn(get_text("Task", lang), width="medium"),
                "CompletedAt": st.column_config.DatetimeColumn(get_text("Completed At", lang), disabled=True, width="small"),
                "Owner": st.column_config.TextColumn(get_text("Owner", lang), disabled=True),
                "SharedWith": st.column_config.TextColumn(get_text("Shared With (Mobile #s)", lang), help="Comma-separated mobile numbers", default=""),
            },
            num_rows="fixed", # Changed to fixed to prevent accidental row generation
            width='stretch',
            hide_index=True,
            key="todo_editor",
        )

        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button(get_text("💾 Save Changes", st.session_state.language), use_container_width=True, disabled=(current_user == "guest")):
            # 1. Filter out rows marked for deletion
            save_df = edited_df[edited_df["🗑️"] == False].drop(columns=["🗑️", "👁️"], errors='ignore')
            
            # 2. Restore real Mobile Numbers from masked versions before saving
            for idx, row in save_df.iterrows():
                if idx in original_metadata:
                    # Restore Owner (Disabled field, so always restore original)
                    save_df.at[idx, 'Owner'] = original_metadata[idx]['Owner']
                    
                    # Restore SharedWith (Check if user entered new numbers or kept the masked ones)
                    current_val = str(row['SharedWith'])
                    if "*" in current_val:
                        # User didn't overwrite with new numbers, restore original list
                        save_df.at[idx, 'SharedWith'] = original_metadata[idx]['SharedWith']
                    # else: user typed new numbers, keep as is
                else:
                    # New task row (appended via button)
                    save_df.at[idx, 'Owner'] = current_user

            # Logic: If status changed to 'Done', record timestamp
            for idx, row in save_df.iterrows():
                # Determine if this was a new row or if the index exists in the original df
                original_status = None
                if idx in df.index:
                    original_status = df.loc[idx, 'Status']
                
                if row['Status'] == 'Done' and original_status != 'Done':
                    # Use Pandas Timestamp and floor to seconds to match inferred column dtype
                    save_df.at[idx, 'CompletedAt'] = pd.Timestamp.now().floor('s')
                # Reset timestamp if status is reverted from Done
                elif row['Status'] != 'Done':
                    save_df.at[idx, 'CompletedAt'] = None
            
            # Reload full file to ensure we don't overwrite other users' data
            if os.path.exists(tools.TODO_FILE):
                full_df = pd.read_csv(tools.TODO_FILE, dtype={'Owner': str, 'SharedWith': str})
                # Ensure required columns exist to avoid KeyError during filtering or processing
                for col in ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]:
                    if col not in full_df.columns:
                        if col == "Priority": full_df[col] = "High"
                        elif col == "Owner": full_df[col] = "guest"
                        elif col == "SharedWith": full_df[col] = ""
                        else: full_df[col] = None
                # Cast to string to prevent type mismatch during concat or editing
                full_df['Owner'] = full_df['Owner'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
                full_df['SharedWith'] = full_df['SharedWith'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
            else:
                full_df = pd.DataFrame(columns=save_df.columns)
            
            # Logic: Identify rows that belong to the user's view (owned or shared)
            def check_persistence(row):
                if row['Owner'] == current_user: return True
                shared_list = [s.strip() for s in str(row.get('SharedWith', '')).split(',') if s.strip()]
                return current_user in shared_list and current_user != 'guest'

            visible_mask = full_df.apply(check_persistence, axis=1)
            others_tasks = full_df[~visible_mask]
            
            final_df = pd.concat([others_tasks, save_df], ignore_index=True)
            final_df.to_csv(tools.TODO_FILE, index=False)
            broadcast_update()
            st.success(get_text("Tasks saved and automatically sorted!", lang))
            st.rerun() # Rerun to reflect changes in the UI and metrics
            
        if btn_col2.button(get_text("🗑️ Clear Done", st.session_state.language), use_container_width=True, disabled=(current_user == "guest")):
            if os.path.exists(tools.TODO_FILE):
                full_df = pd.read_csv(tools.TODO_FILE, dtype={'Owner': str, 'SharedWith': str})
                # Ensure required columns exist to avoid KeyError: 'Owner'
                for col in ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]:
                    if col not in full_df.columns:
                        if col == "Priority": full_df[col] = "High"
                        elif col == "Owner": full_df[col] = "guest"
                        elif col == "SharedWith": full_df[col] = ""
                        else: full_df[col] = None
                        
                # Cast to string to prevent type mismatch
                full_df['Owner'] = full_df['Owner'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
                full_df['SharedWith'] = full_df['SharedWith'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')

                # Keep tasks not owned by user OR tasks owned by user that are NOT Done
                mask = (full_df['Owner'] != current_user) | (full_df['Status'] != 'Done')
                final_df = full_df[mask]
                final_df.to_csv(tools.TODO_FILE, index=False)
                broadcast_update()
            
            st.toast(get_text("Completed tasks archived.", lang))
            st.rerun()

    with col2:
        st.subheader(get_text("📊 Agent Execution", st.session_state.language))
        
        # Initialize or load chat history from disk
        if "agent_history" not in st.session_state or st.session_state.current_user != st.session_state.get("last_loaded_user", None):
            state = load_chat_state(current_user)
            st.session_state.agent_history = state.get("agent_history", [])
            st.session_state.chat_display = state.get("chat_display", [])
            st.session_state.last_loaded_user = current_user

        if current_user == "guest":
            st.info(get_text("Please log in to use the AI assistant.", lang))
            
        # Display previous conversation
        chat_container = st.container(height=300, border=True)
        for i, msg in enumerate(st.session_state.chat_display):
            with chat_container.chat_message(msg["role"]): # type: ignore
                col_text, col_sel = st.columns([0.9, 0.1])
                col_text.write(msg["content"])
                # Check last 2 messages if conversation complete, else only check the last 1 pending user message
                is_current = i >= (len(st.session_state.chat_display) - (2 if len(st.session_state.chat_display) % 2 == 0 else 1))
                suffix = st.session_state.get("checkbox_suffix", 0)
                col_sel.checkbox("💾", key=f"sel_{i}_{suffix}", value=is_current, help="Select for archival", label_visibility="collapsed", disabled=(current_user == "guest"))

        # Handle pending AI processing after the UI has updated and cleared old checkboxes
        if "pending_agent_prompt" in st.session_state:
            prompt = st.session_state.pending_agent_prompt
            del st.session_state.pending_agent_prompt
            
            log_stream = StringIO()
            old_stdout = sys.stdout
            sys.stdout = log_stream
            try:
                with chat_container:
                    with st.spinner(get_text("Assistant is thinking...", lang)):
                        report_content, updated_history = run_autonomous_agent(
                            prompt, st.session_state.agent_history, user_id=current_user, language=st.session_state.language
                        )
                        st.session_state.agent_history = updated_history
                        broadcast_update()
                        st.session_state.chat_display.append({
                            "role": "assistant", 
                            "content": report_content,
                            "timestamp": datetime.now().isoformat(),
                            "archived": False
                        })
                        save_chat_state(st.session_state.agent_history, st.session_state.chat_display, current_user)
            finally:
                sys.stdout = old_stdout
            st.session_state.last_agent_log = log_stream.getvalue()
            st.rerun()

        prompt_clicked = None
        if current_user != "guest":
            st.caption(get_text("💡 Quick Prompts:", lang))
            pc1, pc2 = st.columns(2)
            if pc1.button(get_text("📊 Analyze workload", lang), use_container_width=True): prompt_clicked = "Analyze my current workload"
            if pc2.button(get_text("🎯 Suggest priorities", lang), use_container_width=True): prompt_clicked = "Suggest priorities for today"
            if pc1.button(get_text("🧩 Break down a task", lang), use_container_width=True): prompt_clicked = "Break down a complex task"
            if pc2.button(get_text("📝 Create daily summary", lang), use_container_width=True): prompt_clicked = "Create a daily technical summary"

        user_command = st.chat_input(get_text("Ask your assistant...", st.session_state.language), disabled=(current_user == "guest"))
        
        final_command = user_command or prompt_clicked
        
        if final_command:
            if current_user == "guest":
                st.error(get_text("Please log in to use the AI assistant.", lang))
            else:
                # Forcefully uncheck previous messages by rendering fresh keys
                st.session_state.checkbox_suffix = st.session_state.get("checkbox_suffix", 0) + 1
                final_prompt = final_command
                st.session_state.chat_display.append({
                    "role": "user", 
                    "content": final_prompt,
                    "timestamp": datetime.now().isoformat(),
                    "archived": False
                })

                # Detect explicit task-creation commands and persist directly.
                task_name = parse_task_name_from_prompt(final_prompt)
                if task_name:
                    status_msg = tools.add_task(task=task_name, priority="High", owner=current_user)
                    if "Success" in status_msg:
                        assistant_text = f"✅ Added task '{task_name}' with High priority for today."
                    else:
                        assistant_text = f"❌ Failed to add task: {status_msg}"
                    st.session_state.chat_display.append({
                        "role": "assistant",
                        "content": assistant_text,
                        "timestamp": datetime.now().isoformat(),
                        "archived": False
                    })
                    save_chat_state(st.session_state.agent_history, st.session_state.chat_display, current_user)
                    st.rerun()

                # Continue through normal AI agent flow when the prompt is not a direct add-task command.
                else:
                    # Queue agent for execution and trigger an immediate rerun to uncheck previous UI elements
                    st.session_state.pending_agent_prompt = final_prompt
                    st.rerun()

        if st.session_state.chat_display:
            if current_user == "guest":
                st.info(get_text("Please log in to use the AI assistant.", lang))
            else:
                # Allow users to selectively save messages for future reference
                if st.button(get_text("💾 Archive Selected Messages", lang), use_container_width=True):
                    suffix = st.session_state.get("checkbox_suffix", 0)
                    selected_indices = [i for i, msg in enumerate(st.session_state.chat_display) if st.session_state.get(f"sel_{i}_{suffix}", False)]
                    
                    if selected_indices:
                        selected_msgs = [
                            f"{st.session_state.chat_display[i]['role'].upper()}: {st.session_state.chat_display[i]['content']}" 
                            for i in selected_indices
                        ]
                        archive_content = "\n".join(selected_msgs)
                        status_msg = tools.log_report(archive_content)

                        if "Success" in status_msg:
                            # Mark selected messages as archived in session state
                            for i in selected_indices:
                                st.session_state.chat_display[i]["archived"] = True
                            
                            # Persist the 'archived' status to disk
                            save_chat_state(st.session_state.agent_history, st.session_state.chat_display, current_user)
                            
                            # Forcefully uncheck messages after successful archival
                            st.session_state.checkbox_suffix = suffix + 1
                            st.toast(status_msg, icon="✅")
                            time.sleep(1) # Allow user to see the confirmation
                            st.rerun()
                        else:
                            st.error(status_msg)
                    else:
                        st.warning(get_text("No messages selected to archive.", lang))

                if st.button(get_text("🗑️ Clear Chat History", lang), use_container_width=True):
                    st.session_state.agent_history = []
                    st.session_state.chat_display = []
                    # Reset keys since widgets are destroyed
                    st.session_state.checkbox_suffix = st.session_state.get("checkbox_suffix", 0) + 1
                    clear_chat_state(current_user)
                    st.rerun()

        # Persistent Log Viewer
        st.divider()
        with st.expander(get_text("📖 View Persistent Archives", lang), expanded=False):
            if current_user == "guest":
                st.info(get_text("Please log in to view your archives.", lang))
            else:
                archive_file_path = tools.get_archive_file_path(current_user)
                if archive_file_path and os.path.exists(archive_file_path):
                    with open(archive_file_path, "r", encoding="utf-8") as f:
                        archive_content = f.read()
                    
                    # Capture user edits from the text area
                    updated_archive = st.text_area(
                        get_text("Archived Reports", lang), 
                        archive_content, 
                        height=400,
                        key="archive_content_editor"
                    )
                    
                    # If changes are detected, show a Save button
                    if updated_archive != archive_content:
                        if st.button(get_text("💾 Save Archive Changes", lang), use_container_width=True):
                            with open(archive_file_path, "w", encoding="utf-8") as f:
                                f.write(updated_archive)
                            st.success(get_text("Archive updated successfully!", lang))
                            st.rerun()
                else:
                    st.info(get_text("No persistent archives found yet.", lang))

        # Display the agent's internal logs/thinking from the LAST run if available
        if st.session_state.get("last_agent_log"):
            with st.expander(get_text("🔍 View Agent Thinking Process", lang), expanded=False):
                st.code(st.session_state.last_agent_log)
                
    with tab_routines:
        render_routines(current_user)
        
    with tab_learning:
        st.header(get_text("📚 AI Learning & Practice", lang))
        st.markdown(get_text("Enter a topic to learn, or paste a job description to get a tailored learning plan.", lang))

        topic = st.text_area(get_text("Enter Topic or Job Description:", lang), height=150, placeholder=get_text("e.g., Python Decorators, or paste a full job description here...", lang))
        if st.button(get_text("🚀 Generate Lesson", lang)):
            if not topic.strip():
                st.error(get_text("Please enter a topic or job description.", lang))
            else:
                with st.spinner(get_text("Generating lesson...", lang)):
                    lesson_content = generate_learning_content(topic.strip(), lang)
                    st.session_state[f"lesson_{current_user}"] = lesson_content
                    st.session_state[f"lesson_topic_{current_user}"] = topic.strip()
        
        lesson = st.session_state.get(f"lesson_{current_user}")
        if lesson:
            st.divider()
            st.markdown(lesson)
            
            st.divider()
            col_act1, col_act2 = st.columns([1, 1])
            
            current_topic = st.session_state.get(f"lesson_topic_{current_user}", "AI Lesson")
            
            with col_act1:
                if current_user != "guest":
                    if st.button(get_text("💾 Archive Lesson", lang), use_container_width=True):
                        archive_text = f"--- AI Lesson: {current_topic} ---\n{lesson}"
                        status = tools.log_report(archive_text)
                        if "Success" in status:
                            st.success(get_text("Lesson archived successfully!", lang))
                        else:
                            st.error(status)
                else:
                    st.info(get_text("Log in to archive lessons.", lang))
            
            with col_act2:
                st.markdown(f"**{get_text('Share Lesson:', lang)}**")
                app_url = os.getenv("APP_BASE_URL", "http://localhost:8501").rstrip("/")
                tweet_text = urllib.parse.quote(f"{app_url}\n\nI just generated an AI lesson on '{current_topic}'! \n\nCheck out Smart Task Manager. 🚀")
                wa_text = urllib.parse.quote(f"{app_url}\n\nCheck out this AI lesson on '{current_topic}':\n\n{lesson[:1000]}...")
                email_body = urllib.parse.quote(f"{app_url}\n\nCheck out this AI lesson on '{current_topic}':\n\n{lesson}")
                email_sub = urllib.parse.quote(f"AI Lesson: {current_topic}")
                
                st.markdown(f"""
                <div style="display: flex; gap: 10px;">
                    <a href="https://twitter.com/intent/tweet?text={tweet_text}" target="_blank" style="text-decoration:none;">
                        <button style="background-color:#1DA1F2; color:white; border:none; padding:5px 15px; border-radius:5px; cursor:pointer;">🐦 X (Twitter)</button>
                    </a>
                    <a href="https://api.whatsapp.com/send?text={wa_text}" target="_blank" style="text-decoration:none;">
                        <button style="background-color:#25D366; color:white; border:none; padding:5px 15px; border-radius:5px; cursor:pointer;">📱 WhatsApp</button>
                    </a>
                    <a href="mailto:?subject={email_sub}&body={email_body}" target="_blank" style="text-decoration:none;">
                        <button style="background-color:#D44638; color:white; border:none; padding:5px 15px; border-radius:5px; cursor:pointer;">📧 Email</button>
                    </a>
                </div>
                """, unsafe_allow_html=True)
            
    with tab_resume:
        st.header(get_text("📄 Resume Builder", lang))
        if not PDF_TOOLS_AVAILABLE:
            st.warning("⚠️ Please install 'PyPDF2' and 'fpdf' (e.g., `pip install PyPDF2 fpdf`) to fully enable PDF uploads and formatting.")

        rc1, rc2 = st.columns([1, 1.2])
        with rc1:
            uploaded_resume = st.file_uploader(get_text("Upload Existing Resume (PDF/TXT)", lang), type=["pdf", "txt"])
            st.divider()
            st.markdown(f"**{get_text('Or Fill Details Manually', lang)}**")
            r_name = st.text_input(get_text("Full Name", lang))
            r_mobile = st.text_input(get_text("Mobile Number", lang), key="resume_mobile_input")
            r_email = st.text_input(get_text("Email ID", lang))
            r_link = st.text_input(get_text("LinkedIn URL (Optional)", lang))
            r_git = st.text_input(get_text("GitHub URL (Optional)", lang))
            r_exp = st.text_area(get_text("Experiences (Roles, Companies, Dates)", lang), height=100)
            r_edu = st.text_area(get_text("Education (Degrees, Institutions, Dates)", lang), height=100)
            r_proj = st.text_area(get_text("Projects (Names, Tech Stack, Outcomes)", lang), height=100)
            
        with rc2:
            job_desc = st.text_area(get_text("Job Description (Target Role)", lang), height=300)
            
            if st.button(get_text("✨ Generate Tailored Resume", lang), use_container_width=True):
                combined_info = ""
                if uploaded_resume and PDF_TOOLS_AVAILABLE and uploaded_resume.name.endswith(".pdf"):
                    reader = PdfReader(uploaded_resume)
                    combined_info += "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
                elif uploaded_resume:
                    combined_info += uploaded_resume.getvalue().decode("utf-8", errors="ignore")
                
                manual_data = f"Name: {r_name}\nMobile: {r_mobile}\nEmail: {r_email}\nLinkedIn: {r_link}\nGitHub: {r_git}\nExperience: {r_exp}\nEducation: {r_edu}\nProjects: {r_proj}"
                if len(manual_data.replace("Name: \nMobile: \nEmail: \nLinkedIn: \nGitHub: \nExperience: \nEducation: \nProjects: ", "").strip()) > 0:
                    combined_info += "\n\n" + manual_data
                    
                if not combined_info.strip():
                    st.error(get_text("Please provide either manual details or upload a resume.", lang))
                elif not job_desc.strip():
                    st.error(get_text("Please provide a Job Description.", lang))
                else:
                    with st.spinner(get_text("Generating resume...", lang)):
                        tailored_text = generate_tailored_resume(combined_info, job_desc, lang)
                        st.session_state[f"resume_output_{current_user}"] = tailored_text
                        
        if f"resume_output_{current_user}" in st.session_state:
            res_txt = st.session_state[f"resume_output_{current_user}"]
            st.divider()
            st.text_area("Generated Tailored Resume", res_txt, height=400)
            if PDF_TOOLS_AVAILABLE:
                pdf_bytes = create_pdf(res_txt)
                if pdf_bytes:
                    st.download_button(
                        label=get_text("📥 Download Resume (PDF)", lang),
                        data=pdf_bytes,
                        file_name="Tailored_Resume.pdf",
                        mime="application/pdf"
                    )
                    
    with tab_expenses:
        st.header(get_text("💰 Expense Tracker", lang))
        if current_user == "guest":
            st.info(get_text("Please log in to manage your expenses.", lang))
        else:
            with st.form("add_expense_form"):
                col_e1, col_e2 = st.columns(2)
                e_amount = col_e1.number_input(get_text("Amount", lang), min_value=0.0, format="%.2f")
                e_category = col_e2.selectbox(get_text("Category", lang), [
                    get_text("Food", lang), get_text("Transport", lang), 
                    get_text("Shopping", lang), get_text("Bills", lang), get_text("Other", lang)
                ])
                e_desc = st.text_input(get_text("Description", lang))
                e_date = st.date_input(get_text("Date", lang))
                
                if st.form_submit_button(get_text("➕ Add Expense", lang)):
                    if e_amount > 0:
                        tools.add_expense(e_amount, e_category, e_desc, e_date.strftime("%Y-%m-%d"), current_user)
                        st.success(get_text("Expense added successfully!", lang))
                        st.rerun()
                    else:
                        st.error(get_text("Amount must be greater than 0.", lang))

            exp_df = load_expenses_df(current_user)
            if not exp_df.empty:
                today = pd.Timestamp.today().date()
                this_month = today.replace(day=1)
                
                daily_total = exp_df[exp_df['Date'] == today]['Amount'].sum()
                monthly_total = exp_df[pd.to_datetime(exp_df['Date']) >= pd.to_datetime(this_month)]['Amount'].sum()
                
                st.divider()
                m1, m2 = st.columns(2)
                m1.metric(get_text("Daily Total", lang), f"${daily_total:.2f}")
                m2.metric(get_text("Monthly Total", lang), f"${monthly_total:.2f}")
                
                st.subheader(get_text("📊 Expense Summary", lang))
                exp_editor = exp_df.copy()
                exp_editor.insert(0, "🗑️", False)
                
                edited_exp = st.data_editor(
                    exp_editor, hide_index=True, use_container_width=True,
                    column_config={"🗑️": st.column_config.CheckboxColumn(get_text("Delete?", lang), default=False), "Owner": None},
                    key="expense_editor"
                )
                if st.button(get_text("💾 Save Changes", lang), key="save_exp_btn"):
                    save_df = edited_exp[edited_exp["🗑️"] == False].drop(columns=["🗑️"])
                    if os.path.exists(tools.EXPENSES_FILE):
                        full_exp = pd.read_csv(tools.EXPENSES_FILE, dtype={'Owner': str})
                        full_exp['Owner'] = full_exp['Owner'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
                        other_exp = full_exp[full_exp['Owner'] != current_user]
                        pd.concat([other_exp, save_df], ignore_index=True).to_csv(tools.EXPENSES_FILE, index=False)
                    st.success(get_text("Changes saved!", lang))
                    st.rerun()

if __name__ == "__main__":
    main()
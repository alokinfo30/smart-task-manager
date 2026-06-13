import sys
import os
import json
import asyncio
import uuid
import pusher
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import urllib.parse
import secrets
import hashlib
import base64
import requests
from fastapi import UploadFile, File
from sqlalchemy.future import select
from database import AsyncSessionLocal, TaskDB, ExpenseDB, init_db

# Add the parent directory to sys.path so we can import agent.py from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import run_autonomous_agent, generate_learning_content, generate_tailored_resume
from auth import PasswordHandler, AuthenticationError, PasswordDB, SessionManager, TokenManager

IS_PROD = os.getenv("ENVIRONMENT", "development").lower() == "production"

def get_current_user(request: Request):
    token = request.cookies.get("stm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return TokenManager.verify_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

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
        except Exception as e:
            print(f"Pusher trigger failed: {e}")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTINES_FILE = os.path.join(ROOT_DIR, "routines.json")
RECURRING_EXPENSES_FILE = os.path.join(ROOT_DIR, "recurring_expenses.json")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8501"]
frontend_urls = os.environ.get("FRONTEND_URLS", os.environ.get("FRONTEND_URL", ""))
if frontend_urls:
    ALLOWED_ORIGINS.extend([url.strip() for url in frontend_urls.split(",") if url.strip()])

# Enable CORS so the Next.js frontend can make requests to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

@app.middleware("http")
async def secure_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    return response

# Root endpoint to fix the "GET / HTTP/1.1 404 Not Found" error
@app.get("/")
def read_root():
    return {"message": "Smart Task Manager API is running!"}

# --- Auth Models & Endpoints ---
class LoginRequest(BaseModel):
    mobile: str
    pin: str

class RegisterRequest(BaseModel):
    mobile: str
    pin: str
    security_question: str
    security_answer: str

@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    if req.mobile == "demo_user":
        token = TokenManager.create_access_token({"sub": req.mobile})
        response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)
        return {"user_id": req.mobile, "name": "Demo User", "email": "", "avatar": ""}
    try:
        if PasswordHandler.login(req.mobile, req.pin):
            user_data = PasswordDB.get_user(req.mobile)
            token = TokenManager.create_access_token({"sub": req.mobile})
            response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)
            return {"user_id": req.mobile, "name": user_data.get("name", ""), "email": user_data.get("email", ""), "avatar": user_data.get("avatar", "")}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=400, detail="Invalid credentials")

@app.post("/api/auth/register")
def register(req: RegisterRequest, response: Response):
    try:
        PasswordHandler.register(req.mobile, req.pin, req.security_question, req.security_answer)
        token = TokenManager.create_access_token({"sub": req.mobile})
        response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)
        return {"user_id": req.mobile}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/auth/question")
def get_security_question(mobile: str):
    if mobile.strip() == "demo_user":
        raise HTTPException(status_code=400, detail="Demo user does not have a security question.")
    try:
        q = PasswordHandler.get_user_security_question(mobile)
        return {"question": q}
    except AuthenticationError as e:
        raise HTTPException(status_code=404, detail=str(e))

class RecoverRequest(BaseModel):
    mobile: str
    answer: str

@app.post("/api/auth/recover")
def recover_pin(req: RecoverRequest):
    try:
        new_pin = PasswordHandler.verify_answer_and_reset_pin(req.mobile, req.answer)
        return {"new_pin": new_pin}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(key="stm_token", httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax")
    return {"message": "Logged out successfully"}

@app.get("/api/auth/me")
def get_current_user_profile(current_user: str = Depends(get_current_user)):
    if current_user == "demo_user":
        return {"user_id": "demo_user", "name": "Demo User", "email": "", "avatar": ""}
    user_data = PasswordDB.get_user(current_user)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": current_user,
        "name": user_data.get("name", ""),
        "email": user_data.get("email", ""),
        "avatar": user_data.get("avatar", "")
    }

@app.get("/api/auth/google/url")
def get_google_url(redirect_uri: str):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=500, detail="Google SSO not configured")
        
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).decode('ascii').rstrip('=')
    
    SessionManager.set_oauth_state(state, code_verifier)
    
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "select_account"
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"url": url}

class GoogleCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str

@app.post("/api/auth/google/callback")
def google_callback(req: GoogleCallbackRequest, response: Response):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google SSO not configured")
        
    code_verifier = SessionManager.get_and_clear_oauth_state(req.state)
    token_url = "https://oauth2.googleapis.com/token"
    payload = {"grant_type": "authorization_code", "client_id": client_id, "client_secret": client_secret, "code": req.code, "redirect_uri": req.redirect_uri}
    if code_verifier: payload["code_verifier"] = code_verifier
        
    res = requests.post(token_url, data=payload)
    if res.status_code != 200: raise HTTPException(status_code=400, detail="Failed to exchange token with Google")
    access_token = res.json().get("access_token")
    user_res = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {access_token}"})
    if user_res.status_code != 200: raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")
    email = user_res.json().get("email")
    if not email: raise HTTPException(status_code=400, detail="Google account has no email")
    return {"email": email}

class CompleteSSORegistration(BaseModel):
    email: str
    mobile: str
    pin: str
    security_question: str
    security_answer: str

@app.post("/api/auth/google/complete")
def complete_sso(req: CompleteSSORegistration, response: Response):
    try:
        try:
            PasswordHandler.register(req.mobile, req.pin, req.security_question, req.security_answer)
        except AuthenticationError as e:
            if "already exists" not in str(e).lower():
                raise e
            if not PasswordHandler.login(req.mobile, req.pin):
                raise AuthenticationError("Mobile already exists. Incorrect PIN to link account.")

        # Preserve existing profile data if linking to an existing account
        existing_user = PasswordDB.get_user(req.mobile)
        existing_name = existing_user.get("name", "")
        existing_avatar = existing_user.get("avatar", "")
        PasswordHandler.update_profile(req.mobile, existing_name, req.email, "", existing_avatar)
        
        token = TokenManager.create_access_token({"sub": req.mobile})
        response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)

        return {"user_id": req.mobile}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))

class ProfileEditRequest(BaseModel):
    user_id: str
    name: str
    email: str
    pin: str = ""
    avatar: str = ""
    security_question: str = ""
    security_answer: str = ""

@app.put("/api/profile/edit")
def edit_profile(req: ProfileEditRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        PasswordHandler.update_profile(req.user_id, req.name, req.email, req.pin, req.avatar, req.security_question, req.security_answer)
        return {"status": "success", "message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/profile/delete")
def delete_account(current_user: str = Depends(get_current_user), response: Response = None):
    try:
        PasswordHandler.delete_account(current_user)
        if response:
            response.delete_cookie(key="stm_token", httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax")
        return {"message": "Account deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Tasks Endpoints ---
class UpdateTaskStatus(BaseModel):
    task_id: int
    status: str
    user_id: str = ""

@app.get("/api/tasks")
async def get_tasks(user_id: str = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB))
            tasks = result.scalars().all()
            records = []
            for t in tasks:
                if t.owner == user_id or (user_id != 'guest' and user_id in [s.strip() for s in str(t.shared_with or "").split(',')]):
                    records.append({
                        "id": t.id, "date": t.date or "", "task": t.task or "",
                        "status": t.status or "Pending", "priority": t.priority or "High",
                        "completed_at": t.completed_at or "", "owner": t.owner or "", "shared_with": t.shared_with or ""
                    })
            return {"tasks": records}
    except Exception as e:
        return {"tasks": []}

class AddTaskRequest(BaseModel):
    task: str
    priority: str
    user_id: str = ""
    date: Optional[str] = None
    shared_with: Optional[str] = ""

@app.post("/api/tasks")
async def add_manual_task(req: AddTaskRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        import tools
        await asyncio.to_thread(tools.add_task, req.task, req.priority, req.date, req.shared_with, req.user_id)
        return {"message": "Success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ShareTaskRequest(BaseModel):
    task_id: int
    shared_with: str
    user_id: str = ""

@app.put("/api/tasks/share")
async def share_task(req: ShareTaskRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        user = await asyncio.to_thread(PasswordDB.get_user, req.shared_with)
        if not user:
            raise HTTPException(status_code=400, detail=f"Account '{req.shared_with}' does not exist.")
        if req.shared_with == req.user_id:
            raise HTTPException(status_code=400, detail="You cannot share a task with yourself.")

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB).filter(TaskDB.id == req.task_id))
            t = result.scalars().first()
            if not t: raise HTTPException(status_code=404, detail="Task not found")
            if t.owner != req.user_id: raise HTTPException(status_code=403, detail="Permission Denied")
            
            existing = str(t.shared_with or "")
            t.shared_with = f"{existing},{req.shared_with}" if existing else req.shared_with
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class EditTaskRequest(BaseModel):
    task_id: int
    user_id: str = ""
    task: str
    priority: str

@app.put("/api/tasks/edit")
async def edit_task(req: EditTaskRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB).filter(TaskDB.id == req.task_id))
            t = result.scalars().first()
            if not t: return {"message": "Task not found"}
            if t.owner != req.user_id: return {"message": "Permission Denied"}
            t.task = req.task
            t.priority = req.priority
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except Exception as e:
        return {"message": str(e)}

@app.put("/api/tasks")
async def update_task(req: UpdateTaskStatus, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB).filter(TaskDB.id == req.task_id))
            t = result.scalars().first()
            if not t: return {"message": "Task not found"}
            t.status = req.status
            t.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if req.status == 'Done' else ""
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except Exception as e:
        return {"message": str(e)}

@app.delete("/api/tasks/done")
async def clear_done_tasks_api(user_id: str = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB).filter(TaskDB.owner == user_id, TaskDB.status == "Done"))
            tasks = result.scalars().all()
            cleared_count = len(tasks)
            for t in tasks: await session.delete(t)
            await session.commit()
            if cleared_count > 0: trigger_pusher_update()
            return {"message": "Success", "cleared": cleared_count}
    except Exception as e:
        return {"message": str(e)}

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, user_id: str = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB).filter(TaskDB.id == task_id))
            t = result.scalars().first()
            if not t: return {"message": "Not found"}
            await session.delete(t)
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except Exception as e:
        return {"message": str(e)}

# --- Expenses Endpoints ---
@app.get("/api/expenses")
async def get_expenses(user_id: str = Depends(get_current_user)):
    def _read_expenses():
        try:
            if not os.path.exists(EXPENSES_FILE): return {"expenses": []}
            df = pd.read_csv(EXPENSES_FILE, dtype=str)
            if 'Owner' not in df.columns: df['Owner'] = ""
            df['Owner'] = df['Owner'].fillna('')
            user_df = df[df['Owner'] == user_id].copy()
            user_df['id'] = user_df.index
            user_df = user_df.fillna("")
            user_df = user_df.rename(columns={"Amount": "amount", "Category": "category", "Description": "description", "Date": "date"})
            records = user_df.to_dict(orient="records")
            for r in records:
                for k, v in r.items():
                    if pd.isna(v) or str(v).lower() == "nan": r[k] = ""
            return {"expenses": records}
        except Exception as e:
            return {"expenses": []}
    return await asyncio.to_thread(_read_expenses)

class AddExpenseRequest(BaseModel):
    user_id: str = ""
    amount: float
    category: str
    description: str
    date: str

@app.post("/api/expenses")
def add_expense(req: AddExpenseRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        import tools
        tools.add_expense(req.amount, req.category, req.description, req.date, req.user_id)
        return {"message": "Success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class EditExpenseRequest(BaseModel):
    expense_id: int
    user_id: str = ""
    amount: float
    category: str
    description: str
    date: str

@app.put("/api/expenses/edit")
async def edit_expense(req: EditExpenseRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ExpenseDB).filter(ExpenseDB.id == req.expense_id))
            e = result.scalars().first()
            if not e: return {"message": "Expense not found"}
            if e.owner != req.user_id: return {"message": "Permission Denied"}
            e.amount = req.amount
            e.category = req.category
            e.description = req.description
            e.date = req.date
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except Exception as e:
        return {"message": str(e)}

# --- Recurring Expenses Endpoints ---
def load_recurring_expenses_data():
    if not os.path.exists(RECURRING_EXPENSES_FILE):
        return {}
    try:
        with open(RECURRING_EXPENSES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
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
            with open(RECURRING_EXPENSES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        return data
    except Exception:
        return {}

def save_recurring_expenses_data(data):
    with open(RECURRING_EXPENSES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@app.get("/api/expenses/recurring")
def get_recurring_expenses(user_id: str = Depends(get_current_user)):
    data = load_recurring_expenses_data()
    return data.get(user_id, {"settings": [], "history": {}})

class AddRecurringExpenseRequest(BaseModel):
    user_id: str = ""
    amount: float
    category: str
    description: str

@app.post("/api/expenses/recurring")
def add_recurring_expense(req: AddRecurringExpenseRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    data = load_recurring_expenses_data()
    if req.user_id not in data:
        data[req.user_id] = {"settings": [], "history": {}}
    data[req.user_id]["settings"].append({
        "id": str(uuid.uuid4())[:8],
        "amount": req.amount,
        "category": req.category,
        "description": req.description
    })
    save_recurring_expenses_data(data)
    trigger_pusher_update()
    return {"message": "Success"}

@app.delete("/api/expenses/recurring/{exp_id}")
def delete_recurring_expense(exp_id: str, user_id: str = Depends(get_current_user)):
    data = load_recurring_expenses_data()
    if user_id in data:
        data[user_id]["settings"] = [e for e in data[user_id]["settings"] if e["id"] != exp_id]
        save_recurring_expenses_data(data)
        trigger_pusher_update()
    return {"message": "Success"}

class CheckRecurringRequest(BaseModel):
    user_id: str = ""
    exp_id: str
    action: str
    date: str

@app.post("/api/expenses/recurring/check")
def check_recurring_expense(req: CheckRecurringRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    data = load_recurring_expenses_data()
    if req.user_id not in data:
        data[req.user_id] = {"settings": [], "history": {}}
    history = data[req.user_id].get("history", {})
    if req.date not in history: 
        history[req.date] = {}
    history[req.date][req.exp_id] = req.action
    data[req.user_id]["history"] = history
    save_recurring_expenses_data(data)
    trigger_pusher_update()
    return {"message": "Success"}

@app.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: int, user_id: str = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ExpenseDB).filter(ExpenseDB.id == expense_id))
            e = result.scalars().first()
            if not e: return {"message": "Not found"}
            await session.delete(e)
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except Exception as e:
        return {"message": str(e)}

# --- Routines Endpoints ---
class AddRoutineRequest(BaseModel):
    user_id: str = ""
    name: str
    start: str
    end: str
    days: List[str]

class RoutineCheckRequest(BaseModel):
    user_id: str = ""
    routine_id: str
    action: str
    time: str
    date: str

class EditRoutineRequest(BaseModel):
    user_id: str = ""
    routine_id: str
    name: str
    start: str
    end: str

def load_routines_data():
    if not os.path.exists(ROUTINES_FILE):
        return {}
    try:
        with open(ROUTINES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_routines_data(data):
    with open(ROUTINES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

@app.get("/api/routines")
async def get_routines(user_id: str = Depends(get_current_user)):
    data = await asyncio.to_thread(load_routines_data)
    return data.get(user_id, {"settings": [], "history": {}})

@app.post("/api/routines")
async def add_routine(req: AddRoutineRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    def _add():
        data = load_routines_data()
        if req.user_id not in data: data[req.user_id] = {"settings": [], "history": {}}
        new_routine = {"id": str(uuid.uuid4()), "name": req.name, "start": req.start, "end": req.end, "days": req.days}
        data[req.user_id]["settings"].append(new_routine)
        save_routines_data(data)
        trigger_pusher_update()
        return {"message": "Routine added"}
    return await asyncio.to_thread(_add)

@app.put("/api/routines/edit")
async def edit_routine(req: EditRoutineRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    def _edit():
        data = load_routines_data()
        if req.user_id in data:
            for r in data[req.user_id]["settings"]:
                if r["id"] == req.routine_id:
                    r["name"] = req.name
                    r["start"] = req.start
                    r["end"] = req.end
                    save_routines_data(data)
                    trigger_pusher_update()
                    return {"message": "Success"}
        return {"message": "Routine not found"}
    return await asyncio.to_thread(_edit)

@app.delete("/api/routines/{routine_id}")
async def delete_routine(routine_id: str, user_id: str = Depends(get_current_user)):
    def _del():
        data = load_routines_data()
        if user_id in data:
            data[user_id]["settings"] = [r for r in data[user_id]["settings"] if r["id"] != routine_id]
            save_routines_data(data)
            trigger_pusher_update()
        return {"message": "Routine deleted"}
    return await asyncio.to_thread(_del)

@app.post("/api/routines/check")
async def check_routine(req: RoutineCheckRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    def _chk():
        data = load_routines_data()
        if req.user_id not in data: data[req.user_id] = {"settings": [], "history": {}}
        history = data[req.user_id].get("history", {})
        if req.date not in history: history[req.date] = {}
        if req.routine_id not in history[req.date]: history[req.date][req.routine_id] = {}
        history[req.date][req.routine_id][req.action] = req.time
        data[req.user_id]["history"] = history
        save_routines_data(data)
        trigger_pusher_update()
        return {"message": "Routine checked"}
    return await asyncio.to_thread(_chk)

# --- Archive Endpoints ---
class AddArchiveRequest(BaseModel):
    user_id: str = ""
    content: str

ARCHIVE_DIR = "archives"
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def get_safe_archive_path(user_id: str) -> str:
    safe_id = "".join(c for c in str(user_id) if c.isalnum() or c in ("_", "-", "@", "."))
    return os.path.join(ARCHIVE_DIR, f"daily_summary_{safe_id}.txt")

@app.get("/api/archive")
async def get_archive(user_id: str = Depends(get_current_user)):
    def _get():
        file_path = get_safe_archive_path(user_id)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return {"content": f.read()}
        return {"content": ""}
    return await asyncio.to_thread(_get)

@app.post("/api/archive")
async def add_archive(req: AddArchiveRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    def _add():
        file_path = get_safe_archive_path(req.user_id)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n# Persistent Archive: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{req.content}\n" + "-" * 40 + "\n")
        return {"message": "Archived successfully"}
    return await asyncio.to_thread(_add)

@app.put("/api/archive")
async def update_archive(req: AddArchiveRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    def _up():
        file_path = get_safe_archive_path(req.user_id)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"message": "Archive updated successfully"}
    return await asyncio.to_thread(_up)

# --- AI/Assistant Endpoints ---
class ChatRequest(BaseModel):
    prompt: str
    user_id: str = ""
    history: List[Dict[str, Any]]
    language: Optional[str] = "English"

@app.post("/api/chat")
async def chat(req: ChatRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    def _chat():
        # CRITICAL: Set the user context in this new thread so the AI 
        # modifies your database rows instead of the "guest" fallback.
        import tools
        tools.context.user = req.user_id
        return run_autonomous_agent(
            prompt=req.prompt,
            history=req.history,
            user_id=req.user_id,
            language=req.language
        )
    response_text, updated_history = await asyncio.to_thread(_chat)
    return {"response": response_text}

class LearnRequest(BaseModel):
    topic: str
    language: str

@app.post("/api/learn")
async def learn(req: LearnRequest, current_user: str = Depends(get_current_user)):
    content = await asyncio.to_thread(generate_learning_content, req.topic, req.language)
    return {"content": content}

class ResumeRequest(BaseModel):
    user_info: str
    job_desc: str
    language: str

@app.post("/api/resume")
async def generate_resume(req: ResumeRequest, current_user: str = Depends(get_current_user)):
    content = await asyncio.to_thread(generate_tailored_resume, req.user_info, req.job_desc, req.language)
    return {"content": content}

@app.post("/api/parse-pdf")
async def parse_pdf(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    def _parse():
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(file.file)
            text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
            return {"text": text}
        except Exception as e:
            return {"text": ""}
    return await asyncio.to_thread(_parse)
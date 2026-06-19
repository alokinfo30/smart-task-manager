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
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import urllib.parse
import secrets
import hashlib
import time
from collections import defaultdict
import base64
import requests
from fastapi import UploadFile, File
from sqlalchemy.future import select
from database import AsyncSessionLocal, TaskDB, ExpenseDB, init_db

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stm_backend")

# Add the parent directory to sys.path so we can import agent.py from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import run_autonomous_agent, generate_learning_content, generate_tailored_resume
from auth import PasswordHandler, AuthenticationError, PasswordDB, SessionManager, TokenManager

IS_PROD = os.getenv("ENVIRONMENT", "development").lower() == "production"

def get_current_user(request: Request):
    # Prioritize Next.js Authorization header over potentially stale browser cookies
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    if not token:
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
            logger.error(f"Pusher trigger failed: {e}")

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
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app",
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

# --- Rate Limiting Middleware ---
IP_RATE_LIMIT = defaultdict(list)
RATE_LIMIT_WINDOW = 60 # seconds
MAX_REQUESTS_PER_WINDOW = 20

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/auth/"):
        # Handle Reverse Proxies (Vercel, Nginx, AWS, Cloudflare)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        IP_RATE_LIMIT[client_ip] = [t for t in IP_RATE_LIMIT[client_ip] if now - t < RATE_LIMIT_WINDOW]
        if len(IP_RATE_LIMIT[client_ip]) >= MAX_REQUESTS_PER_WINDOW:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again later."})
        IP_RATE_LIMIT[client_ip].append(now)
    return await call_next(request)

# --- Auth Models & Endpoints ---
class LoginRequest(BaseModel):
    mobile: str = Field(..., max_length=50)
    pin: str = Field(..., max_length=50) # Remove pattern to allow dummy/empty strings

class RegisterRequest(BaseModel):
    mobile: str = Field(..., max_length=50)
    pin: str = Field(..., max_length=6, pattern=r"^[0-9]+$")
    security_question: str = Field(..., max_length=300)
    security_answer: str = Field(..., max_length=300)

class RefreshRequest(BaseModel):
    refresh_token: str

@app.post("/api/auth/refresh")
def refresh_token(req: RefreshRequest):
    try:
        user_id = TokenManager.verify_token(req.refresh_token)
        new_token = TokenManager.create_access_token({"sub": user_id})
        return {"access_token": new_token, "refresh_token": new_token}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    mobile = req.mobile.strip()
    if mobile == "demo_user" or mobile.startswith("demo_") or mobile.startswith("guest"):
        token = TokenManager.create_access_token({"sub": mobile})
        response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)
        return {"user_id": mobile, "name": "Demo User", "email": "", "avatar": "", "access_token": token, "refresh_token": token}
        
    mobile = "".join(filter(str.isdigit, mobile))
    if len(mobile) != 10:
        raise HTTPException(status_code=400, detail="Mobile number must be exactly 10 digits.")

    try:
        if PasswordHandler.login(mobile, req.pin):
            user_data = PasswordDB.get_user(mobile)
            token = TokenManager.create_access_token({"sub": mobile})
            response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)
            return {"user_id": mobile, "name": user_data.get("name", ""), "email": user_data.get("email", ""), "avatar": user_data.get("avatar", ""), "access_token": token, "refresh_token": token}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=400, detail="Invalid credentials")

@app.post("/api/auth/register")
def register(req: RegisterRequest, response: Response):
    mobile = "".join(filter(str.isdigit, req.mobile))
    if len(mobile) != 10:
        raise HTTPException(status_code=400, detail="Mobile number must be exactly 10 digits.")
    try:
        PasswordHandler.register(mobile, req.pin, req.security_question, req.security_answer)
        token = TokenManager.create_access_token({"sub": mobile})
        response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)
        return {"user_id": mobile, "access_token": token, "refresh_token": token}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/auth/question")
def get_security_question(mobile: str):
    mobile = mobile.strip()
    if mobile == "demo_user" or mobile.startswith("demo_"):
        raise HTTPException(status_code=400, detail="Demo user does not have a security question.")
    try:
        q = PasswordHandler.get_user_security_question(mobile)
        return {"question": q}
    except AuthenticationError as e:
        raise HTTPException(status_code=404, detail=str(e))

class RecoverRequest(BaseModel):
    mobile: str = Field(..., max_length=50)
    answer: str = Field(..., max_length=300)

@app.post("/api/auth/recover")
def recover_pin(req: RecoverRequest):
    mobile = "".join(filter(str.isdigit, req.mobile))
    if len(mobile) != 10:
        raise HTTPException(status_code=400, detail="Mobile number must be exactly 10 digits.")

    try:
        new_pin = PasswordHandler.verify_answer_and_reset_pin(mobile, req.answer)
        return {"new_pin": new_pin}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(key="stm_token", httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax")
    return {"message": "Logged out successfully"}

@app.get("/api/auth/me")
def get_current_user_profile(current_user: str = Depends(get_current_user)):
    if current_user == "demo_user" or current_user.startswith("demo_") or current_user.startswith("guest"):
        return {"user_id": current_user, "name": "Demo User", "email": "", "avatar": ""}
    user_data = PasswordDB.get_user(current_user)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": current_user,
        "name": user_data.get("name", ""),
        "email": user_data.get("email", ""),
        "avatar": user_data.get("avatar", "")
    }

def is_safe_redirect_uri(uri: str, allowed_origins: list) -> bool:
    try:
        parsed = urllib.parse.urlparse(uri)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return origin in allowed_origins or uri in allowed_origins
    except Exception:
        return False

@app.get("/api/auth/google/url")
def get_google_url(redirect_uri: str):
    # Prevent Open Redirect Vulnerability
    if not is_safe_redirect_uri(redirect_uri, ALLOWED_ORIGINS):
        raise HTTPException(status_code=400, detail="Invalid redirect URI")
        
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
    code: str = Field(..., max_length=1000)
    state: str = Field(..., max_length=1000)
    redirect_uri: str = Field(..., max_length=1000)

@app.post("/api/auth/google/callback")
def google_callback(req: GoogleCallbackRequest, response: Response):
    # Prevent Open Redirect Vulnerability
    if not is_safe_redirect_uri(req.redirect_uri, ALLOWED_ORIGINS):
        raise HTTPException(status_code=400, detail="Invalid redirect URI")

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
    email: str = Field(..., max_length=100)
    mobile: str = Field(..., max_length=50)
    pin: str = Field(..., max_length=6, pattern=r"^[0-9]+$")
    security_question: str = Field(..., max_length=300)
    security_answer: str = Field(..., max_length=300)

@app.post("/api/auth/google/complete")
def complete_sso(req: CompleteSSORegistration, response: Response):
    mobile = "".join(filter(str.isdigit, req.mobile))
    if len(mobile) != 10:
        raise HTTPException(status_code=400, detail="Mobile number must be exactly 10 digits.")

    try:
        try:
            PasswordHandler.register(mobile, req.pin, req.security_question, req.security_answer)
        except AuthenticationError as e:
            if "already exists" not in str(e).lower():
                raise e
            if not PasswordHandler.login(mobile, req.pin):
                raise AuthenticationError("Mobile already exists. Incorrect PIN to link account.")

        # Preserve existing profile data if linking to an existing account
        existing_user = PasswordDB.get_user(mobile)
        existing_name = existing_user.get("name", "")
        existing_avatar = existing_user.get("avatar", "")
        PasswordHandler.update_profile(mobile, existing_name, req.email, "", existing_avatar)
        
        token = TokenManager.create_access_token({"sub": mobile})
        response.set_cookie(key="stm_token", value=token, httponly=True, secure=IS_PROD, samesite="none" if IS_PROD else "lax", max_age=604800)

        return {"user_id": mobile, "access_token": token, "refresh_token": token}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))

class ProfileEditRequest(BaseModel):
    user_id: str
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=100)
    pin: str = Field("", max_length=6)
    avatar: str = Field("", max_length=1000)
    security_question: str = Field("", max_length=300)
    security_answer: str = Field("", max_length=300)

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
    status: str = Field(..., max_length=20)
    comment: str = Field("", max_length=1000)
    user_id: str = ""

@app.get("/api/tasks")
async def get_tasks(user_id: str = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB))
            tasks = result.scalars().all()
            records = []
            now = datetime.now()
            tasks_deleted = False
            for t in tasks:
                # Auto clear done tasks after 24 hours
                if t.status == "Done" and t.completed_at:
                    try:
                        completed_time = datetime.strptime(t.completed_at, "%Y-%m-%d %H:%M:%S")
                        if (now - completed_time).total_seconds() > 24 * 3600:
                            await session.delete(t)
                            tasks_deleted = True
                            continue
                    except ValueError:
                        pass
                if t.owner == user_id or (user_id != 'guest' and user_id in [s.strip() for s in str(t.shared_with or "").split(',')]):
                    records.append({
                        "id": t.id, "date": t.date or "", "task": t.task or "",
                        "status": t.status or "Pending", "priority": t.priority or "High",
                        "completed_at": t.completed_at or "", "owner": t.owner or "", "shared_with": t.shared_with or "",
                        "comment": t.comment or ""
                    })
            if tasks_deleted:
                await session.commit()
                trigger_pusher_update()
            return {"tasks": records}
    except Exception as e:
        return {"tasks": []}

class AddTaskRequest(BaseModel):
    task: str = Field(..., max_length=500)
    priority: str = Field(..., max_length=20)
    user_id: str = ""
    date: Optional[str] = Field(None, max_length=20)
    shared_with: Optional[str] = Field("", max_length=200)
    comment: Optional[str] = Field("", max_length=1000)

@app.post("/api/tasks")
async def add_manual_task(req: AddTaskRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        import tools
        await asyncio.to_thread(tools.add_task, req.task, req.priority, req.date, req.shared_with, req.user_id, req.comment)
        return {"message": "Success"}
    except Exception as e:
        logger.error(f"Task creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

class ShareTaskRequest(BaseModel):
    task_id: int
    shared_with: str = Field(..., max_length=50)
    user_id: str = ""

@app.put("/api/tasks/share")
async def share_task(req: ShareTaskRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        if "@" not in req.shared_with:
            req.shared_with = "".join(filter(str.isdigit, req.shared_with))
            if len(req.shared_with) != 10:
                raise HTTPException(status_code=400, detail="Mobile number must be exactly 10 digits.")

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
        logger.error(f"Task share failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

class EditTaskRequest(BaseModel):
    task_id: int
    user_id: str = ""
    task: str = Field(..., max_length=500)
    priority: str = Field(..., max_length=20)
    comment: str = Field("", max_length=1000)

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
            t.comment = req.comment
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except Exception as e:
        logger.error(f"Task edit failed: {e}", exc_info=True)
        return {"message": "Internal server error"}

@app.put("/api/tasks")
async def update_task(req: UpdateTaskStatus, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TaskDB).filter(TaskDB.id == req.task_id))
            t = result.scalars().first()
            if not t: return {"message": "Task not found"}
            t.status = req.status
            if req.comment:
                t.comment = req.comment
            t.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if req.status == 'Done' else ""
            await session.commit()
            trigger_pusher_update()
            return {"message": "Success"}
    except Exception as e:
        logger.error(f"Task status update failed: {e}", exc_info=True)
        return {"message": "Internal server error"}

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
        logger.error(f"Clear done tasks failed: {e}", exc_info=True)
        return {"message": "Internal server error"}

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
        logger.error(f"Task deletion failed: {e}", exc_info=True)
        return {"message": "Internal server error"}

# --- Expenses Endpoints ---
@app.get("/api/expenses")
async def get_expenses(user_id: str = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ExpenseDB).filter(ExpenseDB.owner == user_id).order_by(ExpenseDB.id.desc()))
            expenses = result.scalars().all()
            records = []
            for e in expenses:
                records.append({
                    "id": e.id, "date": e.date or "", "amount": e.amount or 0.0,
                    "category": e.category or "", "description": e.description or "",
                    "owner": e.owner or ""
                })
            return {"expenses": records}
    except Exception as e:
        logger.error(f"Read expenses failed: {e}", exc_info=True)
        return {"expenses": []}

class AddExpenseRequest(BaseModel):
    user_id: str = ""
    amount: float
    category: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)
    date: str = Field(..., max_length=20)

@app.post("/api/expenses")
def add_expense(req: AddExpenseRequest, current_user: str = Depends(get_current_user)):
    req.user_id = current_user
    try:
        import tools
        tools.add_expense(req.amount, req.category, req.description, req.date, req.user_id)
        return {"message": "Success"}
    except Exception as e:
        logger.error(f"Add expense failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/expenses/scan")
async def scan_receipt(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    file_bytes = await file.read()
    mime_type = file.content_type
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Max 5MB.")
        
    def _scan():
        import agent
        from google import genai
        prompt = """
        Analyze this receipt and extract the following information in strict JSON format:
        {
            "amount": 0.00,
            "category": "Food", // Choose best fit: Food, Transport, Shopping, Bills, Other
            "description": "Detailed description including specific item names to ensure best customer experience suggestions",
            "date": "YYYY-MM-DD"
        }
        If you cannot find a date, use the current date. Ensure the response is ONLY valid JSON.
        """
        try:
            image_part = genai.types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            response = agent.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=[prompt, image_part],
            )
            text = agent.extract_response_text(response)
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            logger.error(f"Receipt scan failed: {e}")
            return {"error": "Failed to parse receipt."}
    
    result = await asyncio.to_thread(_scan)
    if "error" in result: raise HTTPException(status_code=500, detail=result["error"])
    return result

class EditExpenseRequest(BaseModel):
    expense_id: int
    user_id: str = ""
    amount: float
    category: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)
    date: str = Field(..., max_length=20)

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
        logger.error(f"Edit expense failed: {e}", exc_info=True)
        return {"message": "Internal server error"}

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
    category: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)

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
    exp_id: str = Field(..., max_length=50)
    action: str = Field(..., max_length=50)
    date: str = Field(..., max_length=20)

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
        logger.error(f"Delete expense failed: {e}", exc_info=True)
        return {"message": "Internal server error"}

# --- Routines Endpoints ---
class AddRoutineRequest(BaseModel):
    user_id: str = ""
    name: str = Field(..., max_length=100)
    start: str = Field(..., max_length=10)
    end: str = Field(..., max_length=10)
    days: List[str]

class RoutineCheckRequest(BaseModel):
    user_id: str = ""
    routine_id: str = Field(..., max_length=50)
    action: str = Field(..., max_length=50)
    time: str = Field(..., max_length=10)
    date: str = Field(..., max_length=20)

class EditRoutineRequest(BaseModel):
    user_id: str = ""
    routine_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    start: str = Field(..., max_length=10)
    end: str = Field(..., max_length=10)

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
    content: str = Field(..., max_length=100000)

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

# --- Resume Profile Archival ---
class ResumeProfileRequest(BaseModel):
    content: str = Field(..., max_length=50000)

def get_safe_resume_path(user_id: str) -> str:
    safe_id = "".join(c for c in str(user_id) if c.isalnum() or c in ("_", "-", "@", "."))
    return os.path.join(ROOT_DIR, f"resume_profile_{safe_id}.txt")

@app.get("/api/resume/profile")
async def get_resume_profile(user_id: str = Depends(get_current_user)):
    def _get():
        file_path = get_safe_resume_path(user_id)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f: return {"content": f.read()}
        return {"content": ""}
    return await asyncio.to_thread(_get)

@app.post("/api/resume/profile")
async def save_resume_profile(req: ResumeProfileRequest, current_user: str = Depends(get_current_user)):
    def _save():
        with open(get_safe_resume_path(current_user), "w", encoding="utf-8") as f: f.write(req.content)
        return {"message": "Resume profile archived for future use"}
    return await asyncio.to_thread(_save)

# --- AI/Assistant Endpoints ---
class ChatRequest(BaseModel):
    prompt: str = Field(..., max_length=3000)
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
        import agent
        tools.context.user = req.user_id
        
        state = agent.load_chat_state(req.user_id)
        chat_display = state.get("chat_display", [])
        chat_display.append({
            "role": "user",
            "content": req.prompt,
            "timestamp": datetime.now().isoformat(),
            "archived": False
        })
        
        response_text, updated_history = run_autonomous_agent(
            prompt=req.prompt,
            history=req.history,
            user_id=req.user_id,
            language=req.language
        )
        
        chat_display.append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat(),
            "archived": False
        })
        agent.save_chat_state(updated_history, chat_display, req.user_id)
        return response_text, updated_history
    response_text, updated_history = await asyncio.to_thread(_chat)
    return {"response": response_text}

@app.get("/api/chat/history")
async def get_chat_history(current_user: str = Depends(get_current_user)):
    def _get():
        import agent
        return agent.load_chat_state(current_user)
    return await asyncio.to_thread(_get)

class LearnRequest(BaseModel):
    topic: str = Field(..., max_length=1000)
    language: str = Field(..., max_length=50)

@app.post("/api/learn")
async def learn(req: LearnRequest, current_user: str = Depends(get_current_user)):
    content = await asyncio.to_thread(generate_learning_content, req.topic, req.language)
    return {"content": content}

class ResumeRequest(BaseModel):
    user_info: str = Field(..., max_length=20000)
    job_desc: str = Field(..., max_length=10000)
    language: str = Field(..., max_length=50)

@app.post("/api/resume")
async def generate_resume(req: ResumeRequest, current_user: str = Depends(get_current_user)):
    content = await asyncio.to_thread(generate_tailored_resume, req.user_info, req.job_desc, req.language)
    return {"content": content}

MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB

@app.post("/api/parse-pdf")
async def parse_pdf(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    # Prevent Large File Upload DoS
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5MB.")
        
    def _parse():
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(file.file)
            text = "\n".join([p.extract_text() for p in reader.pages[:10] if p.extract_text()])[:20000]
            return {"text": text}
        except Exception as e:
            logger.error(f"PDF Parse failed: {e}", exc_info=True)
            return {"text": ""}
    return await asyncio.to_thread(_parse)
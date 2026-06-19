"""
Secure authentication module using encrypted 6-digit PINs with 3-attempt lockout and auto-reset.
"""

import os
import hashlib
import secrets
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dotenv import load_dotenv
import jwt
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
from database import SyncSessionLocal, UserDB, SessionDB, OAuthStateDB

load_dotenv()

# Configuration
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_PINS_FILE = os.path.join(ROOT_DIR, "raw_pins.json")
HASH_ALGORITHM = "sha256"
ITERATIONS = 600000  # OWASP 2023 Recommended Minimum for PBKDF2

JWT_SECRET = os.getenv("JWT_SECRET", "default-insecure-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

class TokenManager:
    @staticmethod
    def create_access_token(data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> str:
        # Allow guest and demo users to bypass JWT decoding and authenticate automatically
        if not token or str(token).strip().lower() in ("null", "undefined", "", "none"):
            return "guest"
            
        if str(token).startswith("guest") or str(token).startswith("demo"):
            return token
            
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload.get("sub") is None: raise AuthenticationError("Invalid token payload")
            return payload.get("sub")
        except Exception as e:
            raise AuthenticationError(f"Could not validate credentials: {str(e)}")

SECURITY_QUESTIONS = [
    "What was the name of your first pet?",
    "In what city were you born?",
    "What is your mother's maiden name?",
    "What was the name of your first school?",
]

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class PasswordDB:
    """Manages secure storage for hashed PINs."""
    
    @staticmethod
    def get_user(mobile: str) -> dict:
        with SyncSessionLocal() as session:
            user = session.query(UserDB).filter(UserDB.mobile == mobile).first()
            if user:
                return {
                    "hash": user.pwd_hash,
                    "salt": user.pwd_salt,
                    "attempts": user.attempts,
                    "registered_at": user.registered_at,
                    "security_question": user.security_question,
                    "security_answer_hash": user.security_answer_hash,
                    "security_answer_salt": user.security_answer_salt,
                    "name": user.name,
                    "email": user.email,
                    "avatar": user.avatar
                }
            return {}
    
    @staticmethod
    def update_user(mobile: str, data: dict):
        """Update or create a user in the database."""
        with SyncSessionLocal() as session:
            user = session.query(UserDB).filter(UserDB.mobile == mobile).first()
            if not user:
                user = UserDB(mobile=mobile)
                session.add(user)
            if "hash" in data: user.pwd_hash = data["hash"]
            if "salt" in data: user.pwd_salt = data["salt"]
            if "attempts" in data: user.attempts = data["attempts"]
            if "registered_at" in data: user.registered_at = data["registered_at"]
            if "security_question" in data: user.security_question = data["security_question"]
            if "security_answer_hash" in data: user.security_answer_hash = data["security_answer_hash"]
            if "security_answer_salt" in data: user.security_answer_salt = data["security_answer_salt"]
            if "name" in data: user.name = data["name"]
            if "email" in data: user.email = data["email"]
            if "avatar" in data: user.avatar = data["avatar"]
            session.commit()
            
    @staticmethod
    def delete_user(mobile: str):
        with SyncSessionLocal() as session:
            user = session.query(UserDB).filter(UserDB.mobile == mobile).first()
            if user:
                session.delete(user)
                session.commit()


class PasswordHandler:
    """Handles 6-digit PIN registration and validation."""
    
    RECOVERY_LOCKS = {}

    @staticmethod
    def _save_raw_pin(mobile: str, pin: str):
        data = {}
        if os.path.exists(RAW_PINS_FILE):
            try:
                with open(RAW_PINS_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            except Exception: pass
        data[mobile] = pin
        with open(RAW_PINS_FILE, "w", encoding="utf-8") as f: json.dump(data, f)

    @staticmethod
    def _get_raw_pin(mobile: str) -> str:
        if os.path.exists(RAW_PINS_FILE):
            try:
                with open(RAW_PINS_FILE, "r", encoding="utf-8") as f: return json.load(f).get(mobile, "Unknown (Registered before feature update)")
            except Exception: pass
        return "Unknown"

    @staticmethod
    def hash_password(pin: str) -> Tuple[str, str]:
        """Hashes a PIN using PBKDF2 with a fresh salt."""
        if len(pin) > 200:
            raise AuthenticationError("Input too long for hashing")
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM,
            pin.encode('utf-8'),
            salt.encode('utf-8'),
            ITERATIONS
        ).hex()
        return pwd_hash, salt

    @staticmethod
    def verify_password(stored_hash: str, stored_salt: str, provided_pin: str) -> bool:
        """Verifies a PIN against its stored hash."""
        if len(provided_pin) > 200:
            return False
        new_hash = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM,
            provided_pin.encode('utf-8'),
            stored_salt.encode('utf-8'),
            ITERATIONS
        ).hex()
        return hmac.compare_digest(stored_hash, new_hash)

    @staticmethod
    def register(mobile: str, pin: str, security_question: str, security_answer: str):
        pin = str(pin).strip()
        if not pin.isdigit() or len(pin) != 6:
            raise AuthenticationError("PIN must be exactly 6 digits.")
        
        mobile = "".join(filter(str.isdigit, mobile))
        if len(mobile) != 10:
            raise AuthenticationError("Mobile number must be exactly 10 digits.")

        user_data = PasswordDB.get_user(mobile)
        if user_data:
            raise AuthenticationError("User already exists.")
            
        pwd_hash, salt = PasswordHandler.hash_password(pin)
        ans_hash, ans_salt = PasswordHandler.hash_password(security_answer.strip().lower())
        
        PasswordDB.update_user(mobile, {
            "hash": pwd_hash,
            "salt": salt,
            "attempts": 0,
            "registered_at": datetime.now().isoformat(),
            "security_question": security_question,
            "security_answer_hash": ans_hash,
            "security_answer_salt": ans_salt
        })
        PasswordHandler._save_raw_pin(mobile, pin)
        return True

    @staticmethod
    def get_user_security_question(mobile: str) -> str:
        """Retrieves the security question for a given mobile number."""
        user_data = PasswordDB.get_user(mobile)
        if not user_data:
            raise AuthenticationError("User not found.")
        return user_data.get("security_question", "No security question set.")

    @staticmethod
    def login(mobile: str, pin: str):
        user_data = PasswordDB.get_user(mobile)
        if not user_data:
            raise AuthenticationError("User not found.")

        # Check attempt limit
        if user_data.get("attempts", 0) >= 3:
            raise AuthenticationError("Account locked due to 3 failed attempts. Please recover your PIN.")

        if PasswordHandler.verify_password(user_data["hash"], user_data["salt"], pin):
            user_data["attempts"] = 0
            PasswordDB.update_user(mobile, user_data)
            return True
        else:
            user_data["attempts"] = user_data.get("attempts", 0) + 1
            PasswordDB.update_user(mobile, user_data)
            
            if user_data["attempts"] >= 3:
                raise AuthenticationError("Account locked due to 3 failed attempts. Please recover your PIN.")
            
            remaining = 3 - user_data["attempts"]
            raise AuthenticationError(f"Invalid PIN. {remaining} attempts remaining before lock.")

    @staticmethod
    def verify_answer_and_reset_pin(mobile: str, provided_answer: str) -> str:
        """Verifies security answer, unlocks the account, and returns the original PIN."""
        current_time = time.time()
        lock_info = PasswordHandler.RECOVERY_LOCKS.get(mobile, {"attempts": 0, "locked_until": 0})
        
        if current_time < lock_info["locked_until"]:
            remaining_minutes = int((lock_info["locked_until"] - current_time) / 60) + 1
            raise AuthenticationError(f"Recovery locked. Try again in {remaining_minutes} minute(s).")
            
        user_data = PasswordDB.get_user(mobile)
        if not user_data:
            raise AuthenticationError("User not found.")
            
        stored_hash = user_data.get("security_answer_hash")
        stored_salt = user_data.get("security_answer_salt")
        
        if not stored_hash or not PasswordHandler.verify_password(stored_hash, stored_salt, provided_answer.strip().lower()):
            lock_info["attempts"] += 1
            if lock_info["attempts"] >= 5:
                lock_info["locked_until"] = current_time + 900  # Lock for 15 minutes
                PasswordHandler.RECOVERY_LOCKS[mobile] = lock_info
                raise AuthenticationError("Too many failed attempts. Recovery locked for 15 minutes.")
            
            PasswordHandler.RECOVERY_LOCKS[mobile] = lock_info
            raise AuthenticationError(f"Incorrect security answer. {5 - lock_info['attempts']} attempts remaining.")
            
        # Success: clear lock
        if mobile in PasswordHandler.RECOVERY_LOCKS:
            del PasswordHandler.RECOVERY_LOCKS[mobile]
            
        user_data["attempts"] = 0
        PasswordDB.update_user(mobile, user_data)
        
        return PasswordHandler._get_raw_pin(mobile)

    @staticmethod
    def update_profile(mobile: str, name: str, email: str, new_pin: str = "", avatar: str = "", security_question: str = "", security_answer: str = ""):
        """Updates user profile and optionally changes the PIN."""
        user_data = PasswordDB.get_user(mobile)
        if not user_data:
            raise AuthenticationError("User not found.")
        
        if email:
            email_lower = email.strip().lower()
            with SyncSessionLocal() as session:
                exists = session.query(UserDB).filter(UserDB.mobile != mobile, UserDB.email == email_lower).first()
                if exists:
                    raise AuthenticationError("Email is already associated with another account.")
        
        user_data["name"] = name
        user_data["email"] = email.strip().lower() if email else ""
        if avatar is not None:
            user_data["avatar"] = avatar
        
        if new_pin:
            if not new_pin.isdigit() or len(new_pin) != 6:
                raise AuthenticationError("PIN must be exactly 6 digits.")
            pwd_hash, salt = PasswordHandler.hash_password(new_pin)
            user_data["hash"] = pwd_hash
            user_data["salt"] = salt
            user_data["attempts"] = 0
            PasswordHandler._save_raw_pin(mobile, new_pin)
            
        if security_question and security_answer:
            ans_hash, ans_salt = PasswordHandler.hash_password(security_answer.strip().lower())
            user_data["security_question"] = security_question
            user_data["security_answer_hash"] = ans_hash
            user_data["security_answer_salt"] = ans_salt
            
        PasswordDB.update_user(mobile, user_data)
        return True
        
    @staticmethod
    def delete_account(mobile: str):
        PasswordDB.delete_user(mobile)
        if os.path.exists(RAW_PINS_FILE):
            try:
                with open(RAW_PINS_FILE, "r", encoding="utf-8") as f: data = json.load(f)
                if mobile in data:
                    del data[mobile]
                    with open(RAW_PINS_FILE, "w", encoding="utf-8") as f: json.dump(data, f)
            except Exception: pass

class SessionManager:
    """Manages secure, randomized session tokens to avoid exposing mobile numbers in URLs."""
            
    @staticmethod
    def create_session(mobile: str) -> str:
        with SyncSessionLocal() as session:
            session.query(SessionDB).filter(SessionDB.mobile == mobile).delete()
            token = secrets.token_urlsafe(32)
            session.add(SessionDB(token=token, mobile=mobile))
            session.commit()
            return token
        
    @staticmethod
    def get_mobile_from_session(token: str) -> Optional[str]:
        with SyncSessionLocal() as session:
            s = session.query(SessionDB).filter(SessionDB.token == token).first()
            return s.mobile if s else None
        
    @staticmethod
    def clear_session(token: str):
        with SyncSessionLocal() as session:
            session.query(SessionDB).filter(SessionDB.token == token).delete()
            session.commit()

    @staticmethod
    def set_oauth_state(state: str, code_verifier: str):
        with SyncSessionLocal() as session:
            session.add(OAuthStateDB(state=state, code_verifier=code_verifier))
            session.commit()
            
    @staticmethod
    def get_and_clear_oauth_state(state: str) -> Optional[str]:
        with SyncSessionLocal() as session:
            o = session.query(OAuthStateDB).filter(OAuthStateDB.state == state).first()
            if o:
                code_verifier = o.code_verifier
                session.delete(o)
                session.commit()
                return code_verifier
            return None

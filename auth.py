"""
Secure authentication module using encrypted 6-digit PINs with 3-attempt lockout and auto-reset.
"""

import os
import json
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dotenv import load_dotenv

load_dotenv()

# Configuration
PASSWORD_DB = "passwords.json"
HASH_ALGORITHM = "sha256"
ITERATIONS = 100000

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class PasswordDB:
    """Manages secure storage for hashed PINs."""
    
    @staticmethod
    def load():
        if os.path.exists(PASSWORD_DB):
            try:
                with open(PASSWORD_DB, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @staticmethod
    def save(db: Dict):
        """Save the password database."""
        with open(PASSWORD_DB, "w") as f:
            json.dump(db, f, indent=2)


class PasswordHandler:
    """Handles 6-digit PIN registration and validation."""

    @staticmethod
    def hash_password(pin: str) -> Tuple[str, str]:
        """Hashes a PIN using PBKDF2 with a fresh salt."""
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
        new_hash = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM,
            provided_pin.encode('utf-8'),
            stored_salt.encode('utf-8'),
            ITERATIONS
        ).hex()
        return hmac.compare_digest(stored_hash, new_hash)

    @staticmethod
    def _simulate_send_pin(mobile: str, pin: str):
        """Simulates sending a PIN via a free lifetime facility (log file)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("sent_pins_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] SMS to {mobile}: Your new 6-digit PIN is {pin}\n")
        # In a real app, this would integrate with a free SMTP or SMS API.

    @staticmethod
    def register(mobile: str, pin: str):
        if not pin.isdigit() or len(pin) != 6:
            raise AuthenticationError("PIN must be exactly 6 digits.")
        
        if not mobile or len(mobile) < 10:
            raise AuthenticationError("Please enter a valid mobile number.")

        db = PasswordDB.load()
        if mobile in db:
            raise AuthenticationError("User already exists.")
            
        pwd_hash, salt = PasswordHandler.hash_password(pin)
        db[mobile] = {
            "hash": pwd_hash,
            "salt": salt,
            "attempts": 0,
            "registered_at": datetime.now().isoformat()
        }
        PasswordDB.save(db)
        return True

    @staticmethod
    def login(mobile: str, pin: str):
        db = PasswordDB.load()
        user_data = db.get(mobile)
        
        if not user_data:
            raise AuthenticationError("User not found.")

        # Check attempt limit
        if user_data.get("attempts", 0) >= 3:
            # Generate new 6-digit PIN
            new_pin = "".join([str(secrets.randbelow(10)) for _ in range(6)])
            pwd_hash, salt = PasswordHandler.hash_password(new_pin)
            
            user_data["hash"] = pwd_hash
            user_data["salt"] = salt
            user_data["attempts"] = 0
            PasswordDB.save(db)
            
            PasswordHandler._simulate_send_pin(mobile, new_pin)
            raise AuthenticationError("Account locked due to 3 failed attempts. A new PIN has been sent to your mobile.")

        if PasswordHandler.verify_password(user_data["hash"], user_data["salt"], pin):
            user_data["attempts"] = 0
            PasswordDB.save(db)
            return True
        else:
            user_data["attempts"] = user_data.get("attempts", 0) + 1
            PasswordDB.save(db)
            
            if user_data["attempts"] >= 3:
                # Trigger reset immediately on the 3rd failure
                return PasswordHandler.login(mobile, pin)
            
            remaining = 3 - user_data["attempts"]
            raise AuthenticationError(f"Invalid PIN. {remaining} attempts remaining before reset.")

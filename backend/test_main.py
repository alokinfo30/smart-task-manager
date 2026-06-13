import os
import pytest
from fastapi.testclient import TestClient

# Add backend to path to import database properly
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import SyncSessionLocal, UserDB, SessionDB, OAuthStateDB, TaskDB, ExpenseDB

from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Ensure a clean database before and after each test."""
    def clear_db():
        with SyncSessionLocal() as session:
            session.query(UserDB).delete()
            session.query(SessionDB).delete()
            session.query(OAuthStateDB).delete()
            session.query(TaskDB).delete()
            session.query(ExpenseDB).delete()
            session.commit()
            
    clear_db()
    yield
    clear_db()
    
    if os.path.exists("sent_pins_log.txt"):
        try:
            os.remove("sent_pins_log.txt")
        except Exception:
            pass

def test_read_root():
    """Test the health check root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Smart Task Manager API is running!"}

def test_registration_and_login_flow():
    """Test full registration, login, and protected route access."""
    # 1. Register a new user
    res_reg = client.post("/api/auth/register", json={
        "mobile": "1234567890",
        "pin": "123456",
        "security_question": "What is your pet's name?",
        "security_answer": "Fluffy"
    })
    assert res_reg.status_code == 200
    assert res_reg.json()["user_id"] == "1234567890"
    assert "stm_token" in res_reg.cookies

    # 2. Login with the user
    res_login = client.post("/api/auth/login", json={
        "mobile": "1234567890",
        "pin": "123456"
    })
    assert res_login.status_code == 200
    assert res_login.json()["user_id"] == "1234567890"
    assert "stm_token" in res_login.cookies
    
    # 3. Access a protected route using the token
    cookies = {"stm_token": res_login.cookies.get("stm_token")}
    res_me = client.get("/api/auth/me", cookies=cookies)
    assert res_me.status_code == 200
    assert res_me.json()["user_id"] == "1234567890"

    # 4. Logout
    res_logout = client.post("/api/auth/logout", cookies=cookies)
    assert res_logout.status_code == 200
    assert res_logout.cookies.get("stm_token") in [None, '""', ""] # Cookie should be cleared/expired

def test_demo_user_login():
    """Test the demo user login flow."""
    response = client.post("/api/auth/login", json={"mobile": "demo_user", "pin": "000000"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "demo_user"
    assert data["name"] == "Demo User"
    assert "stm_token" in response.cookies

def test_invalid_login():
    """Test that invalid accounts return the correct error."""
    response = client.post("/api/auth/login", json={"mobile": "invalid", "pin": "123456"})
    assert response.status_code == 400
    assert response.json()["detail"] == "User not found."

def test_lockout_on_multiple_failed_logins():
    """Test that an account is locked out and PIN reset after 3 failed attempts."""
    client.post("/api/auth/register", json={
        "mobile": "9876543210", "pin": "111111",
        "security_question": "Q?", "security_answer": "A"
    })

    # Attempt 1
    res1 = client.post("/api/auth/login", json={"mobile": "9876543210", "pin": "000000"})
    assert res1.status_code == 400
    assert "2 attempts remaining" in res1.json()["detail"]

    # Attempt 2
    res2 = client.post("/api/auth/login", json={"mobile": "9876543210", "pin": "000000"})
    assert res2.status_code == 400
    assert "1 attempts remaining" in res2.json()["detail"]

    # Attempt 3 (Lockout)
    res3 = client.post("/api/auth/login", json={"mobile": "9876543210", "pin": "000000"})
    assert res3.status_code == 400
    assert "Account locked" in res3.json()["detail"]

def test_security_question_and_pin_recovery():
    """Test fetching security question and recovering PIN via answer."""
    client.post("/api/auth/register", json={
        "mobile": "5555555555", "pin": "123456",
        "security_question": "Favorite City?", "security_answer": "Paris"
    })

    res_q = client.get("/api/auth/question?mobile=5555555555")
    assert res_q.status_code == 200
    assert res_q.json()["question"] == "Favorite City?"

    res_recover = client.post("/api/auth/recover", json={"mobile": "5555555555", "answer": "paris"})
    assert res_recover.status_code == 200
    new_pin = res_recover.json()["new_pin"]

    # Verify login works with the new pin
    res_login = client.post("/api/auth/login", json={"mobile": "5555555555", "pin": new_pin})
    assert res_login.status_code == 200

def test_unauthenticated_access():
    """Test that accessing a protected endpoint without a token fails."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
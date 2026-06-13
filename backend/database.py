import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, sessionmaker
from sqlalchemy import String, Float, Integer

# Fetch the Supabase URL from environment variables, fallback to SQLite for local development
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./smart_task.db")
SYNC_DB_URL = os.getenv("SYNC_DATABASE_URL", "sqlite:///./smart_task.db")

engine = create_async_engine(DB_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
sync_engine = create_engine(SYNC_DB_URL, echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine)
Base = declarative_base()

class TaskDB(Base):
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String, index=True)
    task: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="Pending")
    priority: Mapped[str] = mapped_column(String, default="High")
    completed_at: Mapped[str] = mapped_column(String, nullable=True)
    owner: Mapped[str] = mapped_column(String, index=True)
    shared_with: Mapped[str] = mapped_column(String, default="")

class ExpenseDB(Base):
    __tablename__ = "expenses"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(String, index=True)

class UserDB(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mobile: Mapped[str] = mapped_column(String, unique=True, index=True)
    pwd_hash: Mapped[str] = mapped_column(String)
    pwd_salt: Mapped[str] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    registered_at: Mapped[str] = mapped_column(String)
    security_question: Mapped[str] = mapped_column(String)
    security_answer_hash: Mapped[str] = mapped_column(String)
    security_answer_salt: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    avatar: Mapped[str] = mapped_column(String, default="")

class SessionDB(Base):
    __tablename__ = "sessions"
    token: Mapped[str] = mapped_column(String, primary_key=True)
    mobile: Mapped[str] = mapped_column(String)
    
class OAuthStateDB(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String, primary_key=True)
    code_verifier: Mapped[str] = mapped_column(String)

# Call this function on startup to initialize the tables
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
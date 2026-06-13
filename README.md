# 🤖 Smart Task Manager

An enterprise-grade, AI-powered personal assistant available in two independent architectures: a highly scalable **Next.js + FastAPI** Progressive Web App, and a rapid-prototyping **Streamlit** monolith.

With features ranging from real-time Kanban task management and financial tracking, to autonomous AI execution, daily routine coaching, and resume building, this app centralizes productivity.

---

## 🌟 How This Benefits the Common Person
In modern life, people juggle multiple apps for their daily needs: one app for tasks, another for budgeting, a separate AI chatbot for learning, and physical notebooks for habit tracking. 

**Smart Task Manager consolidates all of this into a single, cohesive, offline-capable application:**
- **Reduce Cognitive Load:** The Autonomous AI Agent can manage your tasks and log your expenses simply by listening to your voice ("I just spent $40 on groceries").
- **Maintain Mental Health:** The "Happiness System" and interactive 30-Day Goal tracker ensure you don't just focus on work, but also on your physical health, social connections, and well-being.
- **Stay on Top of Finances:** Track your recurring expenses (Netflix, Rent) and visualize your spending habits through a 30-day interactive trend graph.
- **Hands-Free Productivity:** Browser Text-to-Speech (TTS) capabilities mean the application can read lessons to you or confirm your check-ins while you are multitasking.
- **Career Growth:** The AI Learning Hub and Tailored Resume Builder act as a free, 24/7 personal tutor and career coach.

---

## 🛠️ Tools & Technologies Used

### Frontend (Next.js)
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript & React
- **Testing:** Cypress (End-to-End Automated Testing)
- **Data Visualization:** Recharts
- **Real-Time UI:** Pusher-js & Custom Window Events
- **Progressive Web App:** Native Service Workers & Web Manifest (Installable on mobile/desktop)
- **Voice Interactivity:** Web Speech API (Dictation & Text-to-Speech)

### Backend (FastAPI)
- **Framework:** FastAPI (Python 3.10+)
- **Database:** SQLAlchemy (PostgreSQL / SQLite)
- **AI Integration:** Google Generative AI (Gemini Flash Models)
- **Authentication:** PyJWT, PBKDF2 Hashing, Google OAuth 2.0
- **PDF Parsing:** PyPDF2
- **Real-Time Sync:** Pusher Python SDK

---

## 🚀 Key Features

1. **Offline-Capable PWA (Next.js):** The frontend uses Service Workers to cache assets, loading the UI instantly even on a poor connection.
2. **Agentic AI:** Powered by Gemma/Gemini. The AI utilizes autonomous tool-calling to manipulate your database rows (Tasks, Expenses) via natural language.
3. **Kanban Dashboard:** Create, edit, delete, and share tasks. Export your backlog to CSV, or use the Microphone to dictate new tasks.
4. **Expense Tracker:** Includes daily/monthly budget tracking, management of recurring expenses, and an interactive 30-day spending chart.
5. **Account Management:** Robust Auth utilizing JSON Web Tokens (JWT). Link a Google Account via SSO, recover forgotten PINs using security questions, or securely delete your data.
6. **Multilingual Voice Capabilities:** Support for 6+ languages. The AI agent can listen to your native language and read responses aloud with matching accents.

---

## 💻 How to Run (Option 1: Next.js + FastAPI)

Run the fully decoupled, modern web application stack.

### 1. Prerequisites
- **Node.js:** v18 or newer
- **Python:** v3.10 or newer

### 2. Backend Setup (FastAPI)
Navigate to the backend directory, install the dependencies, and configure your secrets:
```bash
cd backend

# Create a virtual environment (Optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file inside the `backend` folder:
```env
GOOGLE_API_KEY="your_google_api_key"
JWT_SECRET="your_secure_random_string_here"
ENVIRONMENT="development"

# Optional: For Google SSO
GOOGLE_CLIENT_ID="your_client_id"
GOOGLE_CLIENT_SECRET="your_client_secret"

# Optional: For real-time updates across multiple browser tabs
PUSHER_APP_ID="your_app_id"
NEXT_PUBLIC_PUSHER_KEY="your_key"
PUSHER_SECRET="your_secret"
NEXT_PUBLIC_PUSHER_CLUSTER="your_cluster"
```

#### 2. Production (Live Server)
When you deploy your app to a service like Streamlit Community Cloud, you do **not** upload your `.env` file. Instead, you configure these values as "Secrets" in the service's settings dashboard.

*Example Secrets for `https://staskma.streamlit.app/`:*
```toml
# In your Streamlit Cloud secrets editor
GOOGLE_API_KEY = "your_google_api_key"
APP_BASE_URL = "https://staskma.streamlit.app"
# WEBSOCKET_HOST = "staskma.streamlit.app" # See note below
GA_MEASUREMENT_ID = "G-YOUR_PROD_ID"
# ... other keys ...
```
The application code (`app.py`, `agent.py`) is already written to read these environment variables, so it will automatically adapt to whichever environment it's running in.

### Real-Time Sync (WebSockets) - Important Note
The current real-time sync feature runs a Python `websockets` server on a custom port (`8765`). This works perfectly for local development.

However, this architecture is **not compatible with Streamlit Community Cloud**, as it does not allow running background servers on custom ports. To deploy the real-time sync feature to production, you have two main options:
1.  **Deploy on a Virtual Private Server (VPS)**: Use a provider like DigitalOcean, AWS EC2, or Linode where you have full control to run the Streamlit app and open port `8765`. In this case, you would set `WEBSOCKET_HOST` to your server's domain name.
2.  **Refactor to a Managed Service**: Modify the WebSocket logic in `app.py` to use a third-party service like Pusher or Ably. This is the most robust solution for scalable, real-time features on any platform.

### Data Persistence
The application currently uses local flat files (`.txt`, `.csv`, `.json`) for data storage. This is suitable for local development. For production deployments on ephemeral filesystems (like Heroku, Streamlit Community Cloud), this data will be lost on app restarts. For a robust production setup, you should consider migrating the data storage logic in `tools.py` to a persistent database service (e.g., PostgreSQL, MySQL, or a cloud-based NoSQL DB).

---

## 🤖 About Agentic AI in this Project

In your current project, Agentic AI is the central engine that transforms a simple task list into an intelligent assistant. Unlike a traditional chatbot that just answers questions, an "Agent" is capable of reasoning and using tools to interact with the system autonomously.

Here are the specific uses of Agentic AI in your project:

1. Autonomous Task Management (CRUD Operations)
The AI doesn't just talk about tasks; it manages them. When you type a request like "Add a task to review the budget" or "I finished the mentorship task," the agent autonomously decides which tool to call:

Decision Making: It identifies whether to use add_task, update_task_status, or delete_task.
Parameter Inference: It extracts details from your speech. For example, if you say "Remind me to call Alok," it automatically sets the priority to High and the date to Today based on its system instructions.
2. Workload Analysis and Reasoning
The agent acts as a productivity consultant by using the read_todo_list tool to context-load your data:

Workload Health: It can analyze the number of pending vs. completed tasks to identify if you are overcommitted.
Priority Categorization: It uses its internal reasoning to suggest which tasks should be tackled first based on your specific professional or personal context.
Complex Breakdown: Per the SYSTEM_INSTRUCTION, it can take a large, vague task and break it down into actionable sub-steps.
3. Persistent Information Archiving
The project uses the agent to handle data longevity through the log_report tool:

Daily Technical Summaries: The agent can generate a structured summary of your day's work and "archive" it to daily_summary.txt.
Manual Persistence: When you ask to "save" a response or "log this report," the agent executes the file I/O operations autonomously, ensuring important insights aren't lost when the chat history is cleared.
4. Productivity Coaching (Gamification)
The agent is instructed to drive the "Motivational Gamification System":

Sprint Speed Feedback: It tracks your completion percentage and provides positive reinforcement to help you reach the "Elite Executioner" rank.
Fast-Track Motivation: It encourages you to complete "Quick Wins" to build momentum, turning task management from a chore into a challenge.
5. Privacy-Aware Collaboration
The agent strictly follows "Privacy Rules" defined in agent.py and tools.py:

It ensures it only views or modifies tasks that belong to your user_id or tasks explicitly shared with your mobile number in the SharedWith field.
Technical Implementation Note
The "Agentic" nature is powered by Gemma 4 models configured with automatic_function_calling=True. This allows the model to:

Stop generating text when it realizes it needs more information.
Call a Python function from tools.py.
Process the result of that function.
Continue the conversation with the user based on the real-time data it just retrieved

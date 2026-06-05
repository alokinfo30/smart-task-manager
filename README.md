An AI-powered task assistant using Streamlit and Gemini/Gemma, featuring automated analysis, persistent history, and real-time productivity metrics tracking.

Run Frointend At local using
streamlit run d:\project\smart-task-manager\app.py 
or 
streamlit run app.py 

Make sure to install the required PDF dependencies to use the Resume generation functionality:
`pip install PyPDF2 fpdf`

---

## 🌟 Key Features of the Application

### 1. Secure Authentication & Session Management
- **Multiple Login Methods**: Auth0 SSO (Email/Social integrations), Mobile Number & 6-Digit PIN, or a quick Demo Guest Mode.
- **Security & Account Recovery**: 3-attempt lockout auto-reset mechanism and security questions for PIN recovery.
- **Privacy Masking**: Protects sensitive mobile numbers across the UI (e.g., `98******10`).

### 2. Autonomous AI Assistant (Agentic AI)
- **Natural Language Task Management**: Chat with the AI to Add, Update, or Delete tasks without touching the UI.
- **Workload Analysis & Prioritization**: The AI evaluates your pending vs. completed tasks to suggest priorities and highlight fast-track opportunities.
- **Smart Breakdown**: Simplifies complex, vague tasks into actionable sub-steps.

### 3. Task Dashboard & Productivity Gamification
- **Live Status Overview**: A central table to view and manage task status (Pending, Working, Done), priority, and due dates.
- **Rank & Sprint Speed**: Earn ranks like *Rookie*, *Busy Bee*, *Productivity Pro*, or *Elite Executioner* based on your completion efficiency.
- **Real-Time Multiplayer Sync**: Uses WebSockets to broadcast task board updates across multiple devices simultaneously.

### 4. Daily Routines & Punctuality Tracker
- **Routine Management**: Define habits, start/end times, and active days.
- **Punctuality Scoring**: Check-in and check-out to earn an overall daily punctuality score. Get feedback for being early, late, or on time.
- **Multi-channel Alerts**: Real-time reminders via Browser TTS (Text-to-Speech), Email (Gmail), and Telegram.

### 5. AI Learning Hub
- **Instant Tutoring**: Enter any topic (e.g., "Python Decorators", "Spanish Verbs").
- **Structured Content**: Automatically generates basic concepts, syntax/examples, and a 3-5 question practice quiz with answers.

### 6. AI Resume Builder (PDF Generation)
- **Inputs**: Fill out standard form details (Experience, Education, Links) OR simply upload an existing Resume PDF/TXT.
- **Job Tailoring**: Paste a job description to dynamically align and format your skills specifically for the role using the AI.
- **Download**: Exports a clean, formatted plain-text PDF file.

### 7. Daily & Monthly Expense Tracker
- **Financial Oversight**: Log your daily cash flow categorized by Food, Transport, Shopping, Bills, etc.
- **AI Budgeting**: The Autonomous AI can directly log expenses via natural text (e.g. "I spent $25 on Food") and provide insights into your financial health.
- **Dashboard Overviews**: Readily view "Daily Total" and "Monthly Total" metrics to stay on top of your budget limits.

### 8. Multilingual Support
- The app supports 10 languages, automatically defaulting based on geolocation or user selection (English, Hindi, Spanish, Mandarin, Arabic, French, Bengali, Portuguese, Russian, Urdu).

---

## 🛠️ Tools & Technologies Used

- **Frontend & Web Framework**: Streamlit
- **Programming Language**: Python 3
- **Artificial Intelligence**: Google Generative AI SDK (Gemini 1.5 Flash, Gemini 2.0 Flash, Gemini 1.5 Flash-8B)
- **Authentication**: Auth0 SDK & Custom PBKDF2 Hashing
- **Real-Time Communication**: `websockets` & `asyncio`
- **Data Manipulation**: `pandas`
- **Storage**: Flat files (`CSV`, `JSON`, `TXT`)
- **PDF Creation/Parsing**: `fpdf`, `PyPDF2`
- **Notifications**: Standard `smtplib` (Email), Telegram Bot API, JS SpeechSynthesis API

---

## 👶 Baby Steps: How to Use Each Feature Efficiently

### Step 1: Getting Started & Authentication
1. **Launch the App**: Run `streamlit run app.py` in your terminal.
2. **Choose a Login Method**: 
   - Want to just explore? Click **Login as Demo User**.
   - For a secure profile, click **Register** under "Mobile Number & PIN", set up your 6-digit PIN, and answer a security question.
   - *Tip*: Check the "Remember Me" box to stay logged in after page refreshes.

### Step 2: Managing Your Tasks
1. Navigate to the **Tasks & AI Agent** tab.
2. **Add a Task**: Click the `➕ Add New Task` button to manually enter a task, or use the AI Assistant.
3. **Update Status**: In the "Task Editor", change the dropdown under "Status" from *Pending* to *Working* or *Done*. 
4. **Save**: Always click `💾 Save Changes` to confirm your updates. Check your "Sprint Progress" bar to see your rank improve!

### Step 3: Utilizing the AI Assistant
1. In the **Tasks & AI Agent** tab, locate the Chat Interface.
2. **Commanding the AI**: Type "Add a task to review the monthly budget" and hit Enter. The AI will parse this and automatically add it to your board.
3. **Quick Prompts**: Click buttons like `📊 Analyze workload` or `🎯 Suggest priorities` for instant AI coaching.
4. **Persistent Archiving**: Select specific valuable AI messages using the checkboxes next to them, then click `💾 Archive Selected Messages`. View them later in the **View Persistent Archives** expander.

### Step 4: Tracking Daily Routines
1. Go to the **⏱️ Daily Routines & Punctuality** tab.
2. **Create a Routine**: Open `⚙️ Manage Routine Timings`, enter a name (e.g., "Morning Walk"), set expected start/end times, pick active days, and click `➕ Add Routine`.
3. **Check-In/Out**: During the day, click `🟢 Check-In` when you start, and `🔴 Check-Out` when you finish. The app will calculate your punctuality score based on how close you were to your expected times!

### Step 5: Learning New Topics
1. Navigate to the **📚 Learning Hub** tab.
2. **Generate a Lesson**: Type in any topic you're curious about (e.g., "Machine Learning Basics" or "How to bake a cake").
3. Click **🚀 Generate Lesson** and read through the AI-generated concepts, examples, and test yourself with the quick quiz at the bottom!

### Step 6: Using the Resume Builder
1. Navigate to the **📄 Resume Builder** tab.
2. Upload an existing resume (PDF/TXT) OR manually enter your Name, Email, URLs, Experience, Education, and Projects.
3. Paste the **Job Description** of the role you are applying to into the right-hand text box.
4. Click **✨ Generate Tailored Resume**.
5. Preview the result in the text area below and click **📥 Download Resume (PDF)**.

### Step 7: Managing Your Budget & Expenses
1. Click on the **💰 Expense Tracker** tab.
2. To manually add a purchase, enter the amount, select a category, add a description, and click **➕ Add Expense**.
3. Want to do it hands-free? Go to the Agent tab and say: "I just bought $50 of Groceries, log it."
4. Your Daily and Monthly spending metrics will instantly update on the dashboard!

### Step 8: Activating Google Analytics (Traffic Tracking)
To see how many users are visiting your app, where they are from, and what features they use, you can activate the built-in Google Analytics tracker:
1. **Visit Google Analytics**: Go to [analytics.google.com](https://analytics.google.com/) and sign in with your Google account.
2. **Create a Property**: Click the blue "Start measuring" button. (If you already have an account, click the Admin gear icon ⚙️ at the bottom left, then click **Create Property**).
3. **Property Details**: Name your property (e.g., "Smart Task Manager"), select your timezone/currency, and click Next.
4. **Choose Platform**: When asked to choose a platform to collect data, click on **Web**.
5. **Set up Data Stream**: Enter your website's URL (if you are just testing locally, you can type `localhost`) and give your stream a name. Click **Create stream**.
6. **Copy Your Measurement ID**: On the "Web stream details" page that pops up, look at the top right corner for the **Measurement ID**. It always starts with `G-` (for example, `G-A1B2C3D4E5`). Copy this exact ID.
7. **Update your Environment Variables**: Open your `.env` file and add the following line: `GA_MEASUREMENT_ID="G-YOUR_COPIED_ID"`
8. **Restart**: Restart your Streamlit server. The app will automatically inject the tracking code, and the next time someone opens your app, their visit will be recorded live in your Google Analytics dashboard!

---

## 🚀 Production & Deployment Notes

This application is designed to be compatible with both local development (e.g., `http://localhost:8501`) and a live production server (e.g., `https://staskma.streamlit.app/`). The configuration is managed through environment variables.

Note on Server-Side Production:
If your goal was to automatically install Ollama on the production server (e.g., an AWS EC2 or DigitalOcean Linux VPS) rather than the end-user's PC, you should run this command on your server's terminal once before starting Streamlit:

bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull llama3.2

### Environment Variable Configuration

#### 1. Development (Local Machine)
For local development, create a file named `.env` in the root of your project. This file is loaded automatically and should contain all your secrets and local URLs. **This file should NOT be committed to version control (e.g., Git).**

*Example `.env` for local development:*
```
GOOGLE_API_KEY="your_google_api_key"
APP_BASE_URL="http://localhost:8501"
WEBSOCKET_HOST="localhost"
GA_MEASUREMENT_ID="G-YOUR_DEV_ID"
# ... other keys like Auth0, Gmail, Telegram ...
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

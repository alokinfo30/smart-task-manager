An AI-powered task assistant using Streamlit and Gemini, featuring automated analysis, persistent history, and real-time productivity metrics tracking.

Run Frointend At local using
streamlit run d:\project\smart-task-manager\app.py 
or 
streamlit run app.py 

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
The "Agentic" nature is powered by the Gemini 1.5 Flash model configured with automatic_function_calling=True. This allows the model to:

Stop generating text when it realizes it needs more information.
Call a Python function from tools.py.
Process the result of that function.
Continue the conversation with the user based on the real-time data it just retrieved

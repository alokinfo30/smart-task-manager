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
import os
from dotenv import load_dotenv
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from agent import run_autonomous_agent, save_chat_state, load_chat_state, clear_chat_state
from tools import TODO_FILE, log_report

load_dotenv()

def load_todo_df():
    """Loads the todo list into a DataFrame, handles 24h deletion, and sorts."""
    if not os.path.exists(TODO_FILE):
        df = pd.DataFrame(columns=["Date", "Task", "Status", "Priority", "CompletedAt"])
    else:
        try:
            df = pd.read_csv(TODO_FILE)
            # Remove 'Time' column if it exists in an old file
            if 'Time' in df.columns:
                df = df.drop(columns=['Time'])
        except Exception:
            df = pd.DataFrame(columns=["Date", "Task", "Status", "Priority", "CompletedAt"])

    # Ensure all required columns exist
    for col in ["Date", "Task", "Status", "Priority", "CompletedAt"]:
        if col not in df.columns:
            df[col] = "Medium" if col == "Priority" else None

    # --- Logic: Auto-delete "Done" tasks after 24 hours ---
    if not df.empty:
        df['CompletedAt'] = pd.to_datetime(df['CompletedAt'], errors='coerce')
        cutoff = datetime.now() - timedelta(hours=24)
        # Keep if not Done OR if Done but completed less than 24h ago
        mask = (df['Status'] == 'Done') & (df['CompletedAt'].notna()) & (df['CompletedAt'] < cutoff)
        if mask.any():
            df = df[~mask]
            df.to_csv(TODO_FILE, index=False)
    
    # Always convert Date to ensure st.data_editor compatibility
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
    
    # Automatic sorting by Date
    if not df.empty:
        # Sort by Date (Ascending) and Priority (High -> Medium -> Low)
        priority_order = {"High": 0, "Medium": 1, "Low": 2}
        df['p_val'] = df['Priority'].map(priority_order).fillna(3)
        df = df.sort_values(by=["Date", "p_val"]).drop(columns=['p_val']).reset_index(drop=True)
    return df

def main():
    st.set_page_config(page_title="Smart Task Manager", page_icon="🚀", layout="wide")
    
    # Custom CSS for status font colors
    st.markdown("""
        <style>
        .status-pending { color: #FF4B4B; font-weight: bold; }
        .status-working { color: #FFD700; font-weight: bold; }
        .status-done { color: #008000; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    st.title("🤖 Smart Task Manager Agent")

    # API Key Warning
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("🔑 **Action Required**: Please set the `GOOGLE_API_KEY` environment variable to enable Agentic AI features.")

    def style_status(row):
        color = ''
        if row['Status'] == 'Pending': color = 'color: #FF4B4B; font-weight: bold;'
        elif row['Status'] == 'Working': color = 'color: #FFD700; font-weight: bold;'
        elif row['Status'] == 'Done': color = 'color: #008000; font-weight: bold;'
        return [color if i == 'Status' else '' for i in row.index]

    df = load_todo_df()
    
    # 1. Dashboard Metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total", len(df))
    m2.metric("Pending ⏳", len(df[df["Status"] == "Pending"]))
    m3.metric("Working 🛠️", len(df[df["Status"] == "Working"]))
    m4.metric("Done ✅", len(df[df["Status"] == "Done"]))
    
    # New AI Feature: Productivity Score
    if not df.empty:
        score = (len(df[df["Status"] == "Done"]) / len(df)) * 100
        m5.metric("Efficiency 🚀", f"{score:.0f}%")
    else:
        m5.metric("Efficiency 🚀", "0%")

    # 2. Workload Health Notification
    pending_count = len(df[df["Status"] == "Pending"])
    if pending_count > 5:
        st.warning(f"🚨 **High Workload Detected**: You have {pending_count} pending tasks. The AI suggests focusing on one High Priority task to regain momentum.")
    elif pending_count == 0 and len(df) > 0:
        st.success("🌟 **Peak Productivity**: All tasks are underway or completed. Great job!")

    # 2. Status Overview (Styled Table)
    display_df = df.copy()
    if not df.empty:
        search_query = st.text_input("🔍 Search tasks (name, status, or priority):", "").lower()
        if search_query:
            display_df = display_df[display_df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)]

        with st.expander("👀 Live Status Overview", expanded=True):
            st.dataframe(
                display_df.style.apply(style_status, axis=1),
                width='stretch',
                hide_index=True
            )
        
        # Add a visual chart for Status Distribution
        with st.expander("📊 Task Distribution", expanded=False):
            status_counts = display_df['Status'].value_counts().sort_index()
            # Transpose to make each status a column so colors can be mapped individually
            chart_data = status_counts.to_frame().T
            color_map = {
                "Pending": "#FF4B4B",
                "Working": "#FFD700",
                "Done": "#008000"
            }
            chart_colors = [color_map.get(status, "#CCCCCC") for status in chart_data.columns]
            st.bar_chart(chart_data, color=chart_colors)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📝 Task Editor")
        
        # Add a button to explicitly add a new task
        if st.button("➕ Add New Task", width='stretch'):
            # Create a new empty row with default values
            new_row = pd.DataFrame([{
                "Date": datetime.now().date(),
                "Task": "",
                "Status": "Pending",
                "Priority": "Medium",
                "CompletedAt": None
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            st.rerun() # Rerun to show the new row in the editor

        # Add a temporary 'Delete' column for the editor
        df_editor = df.copy()
        df_editor.insert(0, "🗑️", False)

        edited_df = st.data_editor(
            df_editor,
            column_config={
                "🗑️": st.column_config.CheckboxColumn("Delete?", default=False, width="small"),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Pending", "Working", "Done"],
                    required=True,
                ),
                "Priority": st.column_config.SelectboxColumn(
                    "Priority",
                    options=["High", "Medium", "Low"],
                    required=True,
                ),
                "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", width="medium"),
                "Task": st.column_config.TextColumn("Task", width="medium"),
                "CompletedAt": st.column_config.DatetimeColumn("Completed At", disabled=True, width="small"),
            },
            num_rows="fixed", # Changed to fixed to prevent accidental row generation
            width='stretch',
            hide_index=True,
            key="todo_editor",
        )

        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("💾 Save Changes", use_container_width=True):
            # 1. Filter out rows marked for deletion
            save_df = edited_df[edited_df["🗑️"] == False].drop(columns=["🗑️"])
            
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
            
            save_df.to_csv(TODO_FILE, index=False)
            st.success("Tasks saved and automatically sorted!")
            st.rerun() # Rerun to reflect changes in the UI and metrics
            
        if btn_col2.button("🗑️ Clear Done", use_container_width=True):
            # Process edited_df but ignore the temporary delete column
            cleared_df = edited_df[edited_df["Status"] != "Done"].drop(columns=["🗑️"])
            cleared_df.to_csv(TODO_FILE, index=False)
            st.toast("Completed tasks archived.")
            st.rerun()

    with col2:
        st.subheader("📊 Agent Execution")
        
        # Initialize or load chat history from disk
        if "agent_history" not in st.session_state:
            state = load_chat_state()
            st.session_state.agent_history = state.get("agent_history", [])
            st.session_state.chat_display = state.get("chat_display", [])

        # Display previous conversation
        chat_container = st.container(height=300, border=True)
        for msg in st.session_state.chat_display:
            with chat_container.chat_message(msg["role"]):
                st.write(msg["content"])

        # File and Voice inputs
        with st.expander("📎 Attach Files or Voice", expanded=False):
            uploaded_files = st.file_uploader("Upload documents/images", accept_multiple_files=True)
            voice_audio = st.audio_input("Record voice command")

        user_command = st.chat_input("Ask your assistant...")
        
        if user_command or voice_audio:
            # If user spoke but didn't type, provide a default prompt
            final_prompt = user_command if user_command else "Please process this voice command and any attached files."
            
            # Process attachments
            attachments = []
            if uploaded_files:
                for f in uploaded_files:
                    attachments.append((f.read(), f.type))
            if voice_audio:
                attachments.append((voice_audio.read(), voice_audio.type))

            # Update UI display
            st.session_state.chat_display.append({"role": "user", "content": final_prompt})
            with chat_container.chat_message("user"):
                st.write(final_prompt)
                if uploaded_files:
                    st.caption(f"📎 {len(uploaded_files)} file(s) attached")
                if voice_audio:
                    st.caption("🎤 Voice command attached")

            # Capture stdout logs to display the agent's logic in the UI
            log_stream = StringIO()
            old_stdout = sys.stdout
            sys.stdout = log_stream
            
            try:
                with st.spinner("Assistant is thinking..."):
                    report_content, updated_history = run_autonomous_agent(
                        final_prompt, st.session_state.agent_history, attachments=attachments
                    )
                    st.session_state.agent_history = updated_history
                    st.session_state.chat_display.append({"role": "assistant", "content": report_content})
                    # Persist state after successful agent execution
                    save_chat_state(st.session_state.agent_history, st.session_state.chat_display)
            finally:
                sys.stdout = old_stdout
            
            if report_content:
                with chat_container.chat_message("assistant"):
                    st.write(report_content)
                st.rerun() # Refresh to update the task table and metrics

        if st.session_state.chat_display:
            # Allow users to manually save the last assistant response for future reference
            if st.session_state.chat_display[-1]["role"] == "assistant":
                if st.button("💾 Archive Last Response", use_container_width=True):
                    status_msg = log_report(st.session_state.chat_display[-1]["content"])
                    st.success(status_msg)
                    st.rerun()

            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.agent_history = []
                st.session_state.chat_display = []
                clear_chat_state()
                st.rerun()

        # Persistent Log Viewer
        st.divider()
        with st.expander("📖 View Persistent Archives", expanded=False):
            if os.path.exists("daily_summary.txt"):
                with open("daily_summary.txt", "r", encoding="utf-8") as f:
                    archive_content = f.read()
                
                # Capture user edits from the text area
                updated_archive = st.text_area(
                    "Archived Reports (Edit directly and save)", 
                    archive_content, 
                    height=400,
                    key="archive_content_editor"
                )
                
                # If changes are detected, show a Save button
                if updated_archive != archive_content:
                    if st.button("💾 Save Archive Changes", use_container_width=True):
                        with open("daily_summary.txt", "w", encoding="utf-8") as f:
                            f.write(updated_archive)
                        st.success("Archive updated successfully!")
                        st.rerun()
            else:
                st.info("No persistent archives found yet.")

        # Display the agent's internal logs/thinking from the LAST run if available
        if 'log_stream' in locals() and log_stream.getvalue():
            with st.expander("🔍 View Agent Thinking Process", expanded=False):
                st.code(log_stream.getvalue())

if __name__ == "__main__":
    main()
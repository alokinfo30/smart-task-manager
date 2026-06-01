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
import time
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from agent import run_autonomous_agent, save_chat_state, load_chat_state, clear_chat_state
import tools # Import the whole module to access context
from auth import (
    PasswordHandler,
    AuthenticationError,
)

load_dotenv()

def mask_mobile(mobile):
    """Helper to mask mobile numbers for privacy."""
    val = str(mobile).strip()
    if not val or val.lower() == "nan" or val.lower() == "guest":
        return "guest" if val.lower() == "guest" else ""
    if len(val) <= 4:
        return "****"
    return f"{val[:2]}******{val[-2:]}"

def init_session_state():
    """Initialize session state for authentication."""
    if "current_user" not in st.session_state:
        # Check for persistent session in query parameters to handle page refreshes
        if "u" in st.query_params:
            st.session_state.current_user = st.query_params["u"]
            st.session_state.auth_method = "PIN"
        else:
            st.session_state.current_user = "guest"

def load_todo_df(current_user):
    """Loads the todo list into a DataFrame, handles 24h deletion, and sorts."""
    required_cols = ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]
    
    try:
        if os.path.exists(tools.TODO_FILE):
            df = pd.read_csv(tools.TODO_FILE)
        else:
            df = pd.DataFrame(columns=required_cols)
    except Exception:
        df = pd.DataFrame(columns=required_cols)

    # Ensure all required columns exist
    for col in required_cols:
        if col not in df.columns:
            df[col] = "High" if col == "Priority" else (current_user if col == "Owner" else ("" if col == "SharedWith" else None))
    
    if 'Time' in df.columns:
        df = df.drop(columns=['Time'])

    # Ensure SharedWith is string type to prevent Streamlit editor errors (e.g. inferred as FLOAT)
    df['SharedWith'] = df['SharedWith'].fillna('').astype(str).replace('nan', '')

    # --- Logic: Auto-delete "Done" tasks after 24 hours ---
    if not df.empty:
        df['CompletedAt'] = pd.to_datetime(df['CompletedAt'], errors='coerce')
        cutoff = datetime.now() - timedelta(hours=24)
        # Keep if not Done OR if Done but completed less than 24h ago
        mask = (df['Status'] == 'Done') & (df['CompletedAt'].notna()) & (df['CompletedAt'] < cutoff)
        if mask.any():
            df = df[~mask]
            df.to_csv(tools.TODO_FILE, index=False)
    
    # Final check to ensure columns exist before filtering
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    # Privacy Filtering: owner OR explicitly shared. Guests only see their own tasks.
    def is_visible(row):
        if row['Owner'] == current_user: return True
        if current_user == "guest": return False
        shared_list = [s.strip() for s in str(row.get('SharedWith', '')).split(',') if s.strip()]
        return current_user in shared_list

    if not df.empty:
        user_mask = df.apply(is_visible, axis=1)
        df = df[user_mask].copy()

    # Always convert Date to ensure st.data_editor compatibility
    if not df.empty and 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
    
    # Automatic sorting by Date
    if not df.empty:
        priority_order = {"High": 0, "Medium": 1, "Low": 2}
        df['p_val'] = df['Priority'].map(priority_order).fillna(3)
        df = df.sort_values(by=["Date", "p_val"]).drop(columns=['p_val']).reset_index(drop=True)
    return df

def render_auth_ui():
    """Render the secure authentication UI with encrypted PIN."""
    st.sidebar.title("🔐 Secure Authentication")
    
    init_session_state()
    
    if st.session_state.current_user == "guest":
        st.sidebar.subheader("PIN Authentication")
        mobile_input = st.sidebar.text_input("Mobile Number", placeholder="e.g. 9876543210", key="auth_mobile")
        pin_input = st.sidebar.text_input("6-Digit PIN", type="password", help="Enter your 6-digit PIN", key="auth_pin")
        remember_me = st.sidebar.checkbox("Remember Me", value=True, help="Keep me logged in even after page refresh")

        if not mobile_input or len(mobile_input) < 10:
            st.sidebar.warning("⚠️  Enter a valid mobile number")
            return None

        col_reg, col_log = st.sidebar.columns(2)

        with col_reg:
            if st.button("📝 Register", use_container_width=True):
                try:
                    if PasswordHandler.register(mobile_input, pin_input):
                        st.sidebar.success("Account created! You can now login.")
                except AuthenticationError as e:
                    st.sidebar.error(str(e))

        with col_log:
            if st.button("🔐 Login", use_container_width=True):
                try:
                    if PasswordHandler.login(mobile_input, pin_input):
                        st.session_state.current_user = mobile_input
                        # Persist user ID in query params to survive page refresh if requested
                        if remember_me:
                            st.query_params["u"] = mobile_input
                        st.session_state.auth_method = "PIN"
                        st.rerun()
                except AuthenticationError as e:
                    st.sidebar.error(str(e))
        
        st.sidebar.divider()
        return None
        
    else:
        # User is logged in
        st.sidebar.success(f"✅ Logged in as: **{mask_mobile(st.session_state.current_user)}**")
        auth_method_display = f" ({st.session_state.auth_method})" if st.session_state.auth_method else ""
        st.sidebar.caption(f"Auth Method: {auth_method_display}")
        
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            st.session_state.current_user = "guest"
            st.session_state.auth_method = None
            st.query_params.clear()
            st.rerun()
        
        return st.session_state.current_user


def main():
    st.set_page_config(page_title="Smart Task Manager", page_icon="🚀", layout="wide")
    
    # Render authentication UI
    current_user = render_auth_ui()
    if current_user is None:
        current_user = st.session_state.current_user
    
    # CRITICAL: Set the user context for tool execution (like archiving)
    tools.context.user = current_user

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
    
    # Guest Account Warning
    if current_user == "guest":
        st.warning("⚠️  **Guest Mode**: Your tasks are visible to others. Please login to secure your data.")
        st.info("As a guest, you cannot use the AI assistant, save tasks, or view archives.")


    def style_status(row):
        color = ''
        if row['Status'] == 'Pending': color = 'color: #FF4B4B; font-weight: bold;'
        elif row['Status'] == 'Working': color = 'color: #FFD700; font-weight: bold;'
        elif row['Status'] == 'Done': color = 'color: #008000; font-weight: bold;'
        return [color if i == 'Status' else '' for i in row.index]

    df = pd.DataFrame() # Initialize empty df for guest mode
    # Initialize df with all required columns, even if empty, to prevent KeyError
    required_cols_for_metrics = ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]
    df = pd.DataFrame(columns=required_cols_for_metrics)
    if current_user != "guest":
        df = load_todo_df(current_user)

    
    # 1. Dashboard Metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total", len(df))
    m2.metric("Pending ⏳", len(df[df["Status"] == "Pending"]))
    m3.metric("Working 🛠️", len(df[df["Status"] == "Working"]))
    m4.metric("Done ✅", len(df[df["Status"] == "Done"]))
    
    # Motivational Productivity Score
    if not df.empty:
        score = (len(df[df["Status"] == "Done"]) / len(df)) * 100
        m5.metric("Sprint Speed ⚡", f"{score:.0f}%")
    else:
        m5.metric("Sprint Speed ⚡", "0%")

    # 2. Workload Health Notification
    pending_count = len(df[df["Status"] == "Pending"])
    if pending_count > 5:
        st.warning(f"🚨 **High Workload Detected**: You have {pending_count} pending tasks. The AI suggests focusing on one High Priority task to regain momentum.")
    elif pending_count == 0 and len(df) > 0:
        st.success("🌟 **Peak Productivity**: All tasks are underway or completed. Great job!")

    # 2. Status Overview (Styled Table)
    display_df = df.copy()
    if not df.empty:
        # Mask sensitive info in the overview table
        display_df["Owner"] = display_df["Owner"].apply(mask_mobile)
        if "SharedWith" in display_df.columns:
            display_df["SharedWith"] = display_df["SharedWith"].apply(
                lambda x: ", ".join([mask_mobile(s.strip()) for s in str(x).split(",") if s.strip()]) if x else ""
            )

        search_query = st.text_input("🔍 Search tasks (name, status, or priority):", "").lower()
        if search_query:
            display_df = display_df[display_df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)]

        with st.expander("👀 Live Status Overview", expanded=True):
            st.dataframe(
                display_df.style.apply(style_status, axis=1),
                width='stretch',
                hide_index=True
            )
        
        # Replace Task Distribution with Motivational Gamification System
        with st.expander("🏆 Productivity Rank & Quick Wins", expanded=True):
            if not df.empty:
                done_count = len(df[df["Status"] == "Done"])
                total_count = len(df)
                efficiency = (done_count / total_count) * 100
                
                # Determine Rank based on Efficiency
                rank_title = "Rookie"
                rank_icon = "🔰"
                if efficiency >= 90: rank_title, rank_icon = "Elite Executioner", "👑"
                elif efficiency >= 70: rank_title, rank_icon = "Productivity Pro", "🛡️"
                elif efficiency >= 40: rank_title, rank_icon = "Busy Bee", "🐝"
                
                c1, c2 = st.columns([1, 2])
                c1.subheader(f"{rank_icon} {rank_title}")
                c2.progress(efficiency / 100, text=f"Sprint Progress: {efficiency:.0f}%")
                
                # Quick Win Motivation Logic
                pending_tasks = df[df["Status"] == "Pending"]
                if not pending_tasks.empty:
                    # Select highest priority task as the 'Fast-Track' target
                    quick_win = pending_tasks[pending_tasks["Priority"] == "High"]
                    if quick_win.empty: quick_win = pending_tasks
                    
                    target_task = quick_win.iloc[0]["Task"]
                    st.info(f"⚡ **Fast-Track Challenge**: Complete '{target_task}' in the next 15 mins to boost your momentum!")
                elif total_count > 0:
                    st.balloons()
                    st.success("🎉 Board Cleared! You're working at light speed today. Time to celebrate!")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📝 Task Editor")
        
        # Add a button to explicitly add a new task
        if st.button("➕ Add New Task", width='stretch'):
            if current_user == "guest":
                st.error("Please log in to add tasks.")
            else:
                # Create a new empty row with default values
                new_row = pd.DataFrame([{
                    "Date": datetime.now().date(),
                    "Task": "New task...",
                    "Status": "Pending",
                    "Priority": "High",
                    "CompletedAt": None,
                    "Owner": current_user,
                    "SharedWith": "" # Default to not shared with anyone
                }])
                
                # Persist to file immediately so it appears after rerun
                if os.path.exists(tools.TODO_FILE):
                    full_df = pd.read_csv(tools.TODO_FILE)
                else:
                    full_df = pd.DataFrame(columns=["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"])
                
                # Ensure required columns exist before concat
                required_cols = ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]
                for col in required_cols:
                    if col not in full_df.columns:
                        full_df[col] = "High" if col == "Priority" else (current_user if col == "Owner" else ("" if col == "SharedWith" else None))
                
                final_df = pd.concat([full_df, new_row], ignore_index=True)
                final_df.to_csv(tools.TODO_FILE, index=False)
                st.rerun() # Rerun to show the new row in the editor

        # Add a temporary 'Delete' column for the editor
        df_editor = df.copy()
        df_editor.insert(0, "🗑️", False)
        
        # Mask sensitive info in the editor while storing original values to restore on save
        original_metadata = df[['Owner', 'SharedWith']].to_dict('index')
        df_editor["Owner"] = df_editor["Owner"].apply(mask_mobile)
        df_editor["SharedWith"] = df_editor["SharedWith"].apply(
            lambda x: ", ".join([mask_mobile(s.strip()) for s in str(x).split(",") if s.strip()]) if x else ""
        )

        # Normalize column dtypes to satisfy Streamlit's data_editor type checks
        df_editor["🗑️"] = df_editor["🗑️"].astype(bool)
        df_editor["Status"] = df_editor["Status"].fillna("Pending").astype(str)
        df_editor["Priority"] = df_editor["Priority"].fillna("High").astype(str)
        if "Date" in df_editor.columns:
            # Ensure Date column is date objects (not strings) for DateColumn
            df_editor["Date"] = pd.to_datetime(df_editor["Date"], errors='coerce').dt.date
        df_editor["Task"] = df_editor["Task"].fillna("").astype(str)
        # CompletedAt should be a datetime (or NaT) for DatetimeColumn
        df_editor["CompletedAt"] = pd.to_datetime(df_editor["CompletedAt"], errors='coerce')
        df_editor["Owner"] = df_editor["Owner"].fillna("").astype(str)
        df_editor["SharedWith"] = df_editor["SharedWith"].fillna("").astype(str)

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
                "Owner": st.column_config.TextColumn("Owner", disabled=True),
                "SharedWith": st.column_config.TextColumn("Shared With (Mobile #s)", help="Comma-separated mobile numbers", default=""),
            },
            num_rows="fixed", # Changed to fixed to prevent accidental row generation
            width='stretch',
            hide_index=True,
            key="todo_editor",
        )

        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("💾 Save Changes", use_container_width=True):
            if current_user == "guest":
                st.error("Please log in to save changes.")
            else:
                # 1. Filter out rows marked for deletion
                save_df = edited_df[edited_df["🗑️"] == False].drop(columns=["🗑️"])
                
                # 2. Restore real Mobile Numbers from masked versions before saving
                for idx, row in save_df.iterrows():
                    if idx in original_metadata:
                        # Restore Owner (Disabled field, so always restore original)
                        save_df.at[idx, 'Owner'] = original_metadata[idx]['Owner']
                        
                        # Restore SharedWith (Check if user entered new numbers or kept the masked ones)
                        current_val = str(row['SharedWith'])
                        if "*" in current_val:
                            # User didn't overwrite with new numbers, restore original list
                            save_df.at[idx, 'SharedWith'] = original_metadata[idx]['SharedWith']
                        # else: user typed new numbers, keep as is
                    else:
                        # New task row (appended via button)
                        save_df.at[idx, 'Owner'] = current_user

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
                
                # Reload full file to ensure we don't overwrite other users' data
                if os.path.exists(tools.TODO_FILE):
                    full_df = pd.read_csv(tools.TODO_FILE)
                    # Ensure required columns exist to avoid KeyError during filtering or processing
                    for col in ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]:
                        if col not in full_df.columns:
                            if col == "Priority": full_df[col] = "High"
                            elif col == "Owner": full_df[col] = "guest"
                            elif col == "SharedWith": full_df[col] = ""
                            else: full_df[col] = None
                    # Cast to string to prevent type mismatch during concat or editing
                    full_df['SharedWith'] = full_df['SharedWith'].fillna('').astype(str).replace('nan', '')
                else:
                    full_df = pd.DataFrame(columns=save_df.columns)
                
                # Logic: Identify rows that belong to the user's view (owned or shared)
                def check_persistence(row):
                    if row['Owner'] == current_user: return True
                    shared_list = [s.strip() for s in str(row.get('SharedWith', '')).split(',') if s.strip()]
                    return current_user in shared_list and current_user != 'guest'

                visible_mask = full_df.apply(check_persistence, axis=1)
                others_tasks = full_df[~visible_mask]
                
                final_df = pd.concat([others_tasks, save_df], ignore_index=True)
                final_df.to_csv(tools.TODO_FILE, index=False)
                st.success("Tasks saved and automatically sorted!")
                st.rerun() # Rerun to reflect changes in the UI and metrics
            
        if btn_col2.button("🗑️ Clear Done", use_container_width=True):
            if current_user == "guest":
                st.error("Please log in to clear done tasks.")
            else:
                if os.path.exists(tools.TODO_FILE):
                    full_df = pd.read_csv(tools.TODO_FILE)
                    # Ensure required columns exist to avoid KeyError: 'Owner'
                    for col in ["Date", "Task", "Status", "Priority", "CompletedAt", "Owner", "SharedWith"]:
                        if col not in full_df.columns:
                            if col == "Priority": full_df[col] = "High"
                            elif col == "Owner": full_df[col] = "guest"
                            elif col == "SharedWith": full_df[col] = ""
                            else: full_df[col] = None

                    # Keep tasks not owned by user OR tasks owned by user that are NOT Done
                    mask = (full_df['Owner'] != current_user) | (full_df['Status'] != 'Done')
                    final_df = full_df[mask]
                    final_df.to_csv(tools.TODO_FILE, index=False)
                
                st.toast("Completed tasks archived.")
                st.rerun()

    with col2:
        st.subheader("📊 Agent Execution")
        
        # Initialize or load chat history from disk
        if "agent_history" not in st.session_state or st.session_state.current_user != st.session_state.get("last_loaded_user", None):
            state = load_chat_state(current_user)
            st.session_state.agent_history = state.get("agent_history", [])
            st.session_state.chat_display = state.get("chat_display", [])
            st.session_state.last_loaded_user = current_user

        if current_user == "guest":
            st.info("Please log in to use the AI assistant.")
            
        # Display previous conversation
        chat_container = st.container(height=300, border=True)
        for i, msg in enumerate(st.session_state.chat_display):
            with chat_container.chat_message(msg["role"]):
                col_text, col_sel = st.columns([0.9, 0.1])
                col_text.write(msg["content"])
                col_sel.checkbox("💾", key=f"sel_{i}", value=True, help="Select for archival", label_visibility="collapsed")

        user_command = st.chat_input("Ask your assistant...")
        
        if user_command:
            if current_user == "guest":
                st.error("Please log in to use the AI assistant.")
            else:
                final_prompt = user_command
                
                # Update UI display
                st.session_state.chat_display.append({
                    "role": "user", 
                    "content": final_prompt,
                    "timestamp": datetime.now().isoformat(),
                    "archived": False
                })
                with chat_container.chat_message("user"):
                    st.write(final_prompt)

                # Capture stdout logs to display the agent's logic in the UI
                log_stream = StringIO()
                old_stdout = sys.stdout
                sys.stdout = log_stream
                
                try:
                    with st.spinner("Assistant is thinking..."):
                        report_content, updated_history = run_autonomous_agent(
                            final_prompt, st.session_state.agent_history, user_id=current_user
                        )
                        st.session_state.agent_history = updated_history
                        st.session_state.chat_display.append({
                            "role": "assistant", 
                            "content": report_content,
                            "timestamp": datetime.now().isoformat(),
                            "archived": False
                        })
                        # Persist state after successful agent execution
                        save_chat_state(st.session_state.agent_history, st.session_state.chat_display, current_user)
                finally:
                    sys.stdout = old_stdout
                
                if report_content:
                    with chat_container.chat_message("assistant"):
                        st.write(report_content)
                    st.rerun() # Refresh to update the task table and metrics

        if st.session_state.chat_display:
            if current_user == "guest":
                st.info("Please log in to archive or clear chat history.")
            else:
                # Allow users to selectively save messages for future reference
                if st.button("💾 Archive Selected Messages", use_container_width=True):
                    selected_indices = [i for i, msg in enumerate(st.session_state.chat_display) if st.session_state.get(f"sel_{i}", False)]
                    
                    if selected_indices:
                        selected_msgs = [
                            f"{st.session_state.chat_display[i]['role'].upper()}: {st.session_state.chat_display[i]['content']}" 
                            for i in selected_indices
                        ]
                        archive_content = "\n".join(selected_msgs)
                        status_msg = tools.log_report(archive_content)

                        if "Success" in status_msg:
                            # Mark selected messages as archived in session state
                            for i in selected_indices:
                                st.session_state.chat_display[i]["archived"] = True
                            
                            # Persist the 'archived' status to disk
                            save_chat_state(st.session_state.agent_history, st.session_state.chat_display, current_user)
                            
                            st.toast(status_msg, icon="✅")
                            time.sleep(1) # Allow user to see the confirmation
                            st.rerun()
                        else:
                            st.error(status_msg)
                    else:
                        st.warning("No messages selected to archive.")

                if st.button("🗑️ Clear Chat History", use_container_width=True):
                    st.session_state.agent_history = []
                    st.session_state.chat_display = []
                    clear_chat_state(current_user)
                    st.rerun()

        # Persistent Log Viewer
        st.divider()
        with st.expander("📖 View Persistent Archives", expanded=False):
            if current_user == "guest":
                st.info("Please log in to view your archives.")
            else:
                archive_file_path = tools.get_archive_file_path(current_user)
                if archive_file_path and os.path.exists(archive_file_path):
                    with open(archive_file_path, "r", encoding="utf-8") as f:
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
                            with open(archive_file_path, "w", encoding="utf-8") as f:
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
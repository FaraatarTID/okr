"""
Timer Component for OKR Application.
Uses st.fragment for isolated refresh without full page reload.
"""
import streamlit as st
from datetime import datetime
from typing import Optional, Callable


def format_elapsed_time(start_time: datetime) -> str:
    """Format elapsed time as HH:MM:SS."""
    if not start_time:
        return "00:00:00"
    
    elapsed = datetime.utcnow() - start_time
    total_seconds = int(elapsed.total_seconds())
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_minutes(total_minutes: int) -> str:
    """Format minutes as human-readable string."""
    if total_minutes < 60:
        return f"{total_minutes}m"
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours}h {mins}m"


# Check if st.fragment is available (Streamlit 1.37+)
try:
    _fragment_decorator = st.fragment
    HAS_FRAGMENT = True
except AttributeError:
    HAS_FRAGMENT = False
    _fragment_decorator = lambda run_every=None: lambda fn: fn


@_fragment_decorator(run_every=1)
def render_timer_display(
    task_id: int,
    task_title: str,
    timer_started_at: Optional[datetime],
    total_time_spent: int,
    on_stop: Callable[[int, str], None],
    on_start: Callable[[int], None]
):
    """
    Render the timer component with isolated refresh.
    
    This component uses st.fragment to update every second
    without causing full page reloads.
    
    Args:
        task_id: ID of the task being timed
        task_title: Title of the task
        timer_started_at: When timer was started (None if not running)
        total_time_spent: Cached total minutes spent
        on_stop: Callback when stop is clicked (task_id, note)
        on_start: Callback when start is clicked (task_id)
    """
    is_running = timer_started_at is not None
    
    with st.container():
        # Header
        st.markdown(f"### ⏱️ Timer: {task_title}")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if is_running:
                elapsed = format_elapsed_time(timer_started_at)
                st.markdown(f"""
                <div style="
                    font-size: 2.5rem;
                    font-weight: bold;
                    color: #4CAF50;
                    text-align: center;
                    padding: 10px;
                    background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
                    border-radius: 10px;
                    font-family: monospace;
                ">
                    {elapsed}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="
                    font-size: 2.5rem;
                    font-weight: bold;
                    color: #666;
                    text-align: center;
                    padding: 10px;
                    background: #f5f5f5;
                    border-radius: 10px;
                    font-family: monospace;
                ">
                    00:00:00
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.metric("Total Logged", format_minutes(total_time_spent))
        
        with col3:
            if is_running:
                if st.button("⏹️ Stop", key=f"stop_timer_{task_id}", type="primary", use_container_width=True):
                    note = st.session_state.get(f"timer_note_{task_id}", "")
                    on_stop(task_id, note)
                    st.rerun()
            else:
                if st.button("▶️ Start", key=f"start_timer_{task_id}", type="primary", use_container_width=True):
                    on_start(task_id)
                    st.rerun()
        
        # Note input (only when running)
        if is_running:
            st.text_input(
                "Work summary (optional)",
                key=f"timer_note_{task_id}",
                placeholder="What are you working on?"
            )


def render_timer_card(
    task_id: int,
    task_title: str,
    timer_started_at: Optional[datetime],
    total_time_spent: int,
    context_info: str = "",
    on_stop: Callable[[int, str], None] = None,
    on_start: Callable[[int], None] = None
):
    """
    Render a compact timer card for display in task lists.
    
    Args:
        task_id: Task ID
        task_title: Task title
        timer_started_at: Timer start time or None
        total_time_spent: Total minutes logged
        context_info: Additional context (e.g., "Objective > KR")
        on_stop: Stop callback
        on_start: Start callback
    """
    is_running = timer_started_at is not None
    
    with st.container():
        cols = st.columns([0.5, 3, 1.5, 1])
        
        with cols[0]:
            if is_running:
                st.markdown("🔴")  # Recording indicator
            else:
                st.markdown("⭕")
        
        with cols[1]:
            st.markdown(f"**{task_title}**")
            if context_info:
                st.caption(context_info)
        
        with cols[2]:
            if is_running:
                elapsed = format_elapsed_time(timer_started_at)
                st.markdown(f"⏱️ `{elapsed}`")
            else:
                st.markdown(f"📊 {format_minutes(total_time_spent)}")
        
        with cols[3]:
            if is_running:
                if on_stop and st.button("Stop", key=f"card_stop_{task_id}"):
                    on_stop(task_id, "")
            else:
                if on_start and st.button("Start", key=f"card_start_{task_id}"):
                    on_start(task_id)


def render_quick_add_dialog(
    tasks: list,
    on_add: Callable[[int, int, str], None]
):
    """
    Render a "Quick Add" dialog for manually logging time.
    
    Args:
        tasks: List of task dicts with id and title
        on_add: Callback (task_id, duration_minutes, note)
    """
    with st.expander("➕ Quick Add Work Log", expanded=False):
        if not tasks:
            st.info("No tasks available. Create tasks first to log time.")
            return
        
        task_options = {t["title"]: t["id"] for t in tasks}
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_task = st.selectbox(
                "Select Task",
                options=list(task_options.keys()),
                key="quick_add_task"
            )
        
        with col2:
            duration = st.number_input(
                "Duration (minutes)",
                min_value=1,
                max_value=480,
                value=30,
                key="quick_add_duration"
            )
        
        note = st.text_input(
            "Note (optional)",
            key="quick_add_note",
            placeholder="What did you work on?"
        )
        
        if st.button("Add Log", type="primary"):
            if selected_task:
                task_id = task_options[selected_task]
                on_add(task_id, duration, note)
                st.success(f"Added {duration}m to '{selected_task}'")
                st.rerun()

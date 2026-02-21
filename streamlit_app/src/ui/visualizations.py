
import streamlit as st
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.models import Task, TaskStatus
from src.utils.time_utils import from_epoch_millis, from_epoch_seconds, utc_now_naive


def _resolve_task_finish_date(deadline: Any, start: datetime) -> tuple[datetime, bool]:
    """
    Resolve task finish datetime from mixed deadline formats.
    Returns (finish_datetime, is_projected).
    """
    if deadline is None:
        return start + timedelta(days=1), True

    if isinstance(deadline, datetime):
        return deadline, False

    # Legacy compatibility: numeric deadline may be epoch seconds or milliseconds.
    if isinstance(deadline, (int, float)):
        numeric = float(deadline)
        if numeric > 10_000_000_000:  # epoch milliseconds
            return from_epoch_millis(numeric), False
        return from_epoch_seconds(numeric), False

    if isinstance(deadline, str):
        stripped = deadline.strip()
        if not stripped:
            return start + timedelta(days=1), True
        try:
            return datetime.fromisoformat(stripped), False
        except ValueError:
            try:
                numeric = float(stripped)
                if numeric > 10_000_000_000:
                    return from_epoch_millis(numeric), False
                return from_epoch_seconds(numeric), False
            except ValueError:
                return start + timedelta(days=1), True

    return start + timedelta(days=1), True


def render_gantt_chart(tasks: List[Task], current_user_role: str, current_username: str, users_map: Dict[int, Any] = None):
    """
    Render a Smart Gantt Chart using Plotly Express.
    
    Args:
        tasks: List of Task SQL objects.
        current_user_role: 'manager' or 'member'.
        current_username: logged in username.
        users_map: Dict of user_id -> User object (for resolving assignee names).
    """
    if not tasks:
        st.info("No tasks found in the active cycle to visualize.")
        return

    # Prepare data for DataFrame
    gantt_data = []
    
    now = utc_now_naive()
    
    for t in tasks:
        # Determine Start Date
        start = t.start_date if t.start_date else t.created_at
        
        # Determine End Date (Deadline or Projected)
        finish = None
        is_projected = False
        
        finish, is_projected = _resolve_task_finish_date(t.deadline, start)
            
        # Determine Assignee Display
        assignee_label = "Unassigned"
        assignee_id = getattr(t, "assignee_id", None)
        if assignee_id and users_map and assignee_id in users_map:
            assignee_obj = users_map[assignee_id]
            assignee_label = (
                getattr(assignee_obj, "display_name", None)
                or getattr(assignee_obj, "username", None)
                or f"User {assignee_id}"
            )
        
        # Color Mapping
        status_color_map = {
            TaskStatus.TODO: "#9E9E9E",       # Grey
            TaskStatus.IN_PROGRESS: "#1E88E5", # Blue
            TaskStatus.DONE: "#43A047",        # Green
            TaskStatus.BLOCKED: "#E53935"      # Red
        }
        color = status_color_map.get(t.status, "#9E9E9E")
        
        gantt_data.append(dict(
            Task=t.title,
            TaskUnique=f"{t.title} ({t.id})", # Unique Y-axis key
            Start=start,
            Finish=finish,
            Status=t.status.value,
            Assignee=assignee_label,
            Description=t.description or "",
            Projected=is_projected,
            Color=color
        ))

    import pandas as pd
    import plotly.express as px
    df = pd.DataFrame(gantt_data)
    
    # Sort by Start date for visual waterfall
    df = df.sort_values(by="Start", ascending=False) # Plotly draws bottom-up? Check.
    # Actually px.timeline draws bottom-to-top by default logic? 
    # If we want first item at TOP, we might need to reverse or use 'autorange="reversed"' which we do below.
    # If autorange="reversed", then first row in DF (index 0) is at Top.
    # So we want Start ascending (earliest first).
    df = df.sort_values(by="Start", ascending=True)

    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="Finish", 
        y="TaskUnique", # Use unique key to force separate lines
        color="Status",
        hover_data=["Task", "Assignee", "Description", "Projected"],
        color_discrete_map={
            "TODO": "#9E9E9E",
            "IN ACTION": "#1E88E5",
            "IN PROGRESS": "#1E88E5", 
            "DONE": "#43A047",
            "BLOCKED": "#E53935"
        },
        template="plotly_white", # Clean look
        height=min(800, 100 + len(df) * 40) # Dynamic height
    )
    
    # Update layout for "Perfect" experience
    fig.update_yaxes(autorange="reversed") # Waterfall top-down means list starts at top
    fig.update_layout(
        title=dict(text="Project Schedule", font=dict(size=20, family="Vazirmatn")),
        font_family="Vazirmatn",
        title_font_family="Vazirmatn",
        hoverlabel=dict(
            font_family="Vazirmatn"
        ),
        xaxis_title="Timeline",
        yaxis_title=None,
        bargap=0.2,
        margin=dict(l=10, r=10, t=60, b=10),
        yaxis=dict(
            tickmode='array',
            tickvals=df['TaskUnique'],
            ticktext=df['Task']
        )
    )
    
    # Add today line
    fig.add_vline(x=now, line_width=1, line_dash="dash", line_color="red", annotation_text="Today")
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Legend / Tips
    st.caption("💡 **Tip:** Bars shown in faded colors indicate projected deadlines (Next Day) where no specific deadline was set.")


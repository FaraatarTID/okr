
import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.models import Task, TaskStatus

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
    
    now = datetime.utcnow()
    
    for t in tasks:
        # Determine Start Date
        start = t.start_date if t.start_date else t.created_at
        
        # Determine End Date (Deadline or Projected)
        finish = None
        is_projected = False
        
        if t.deadline:
            try:
                # Handle potential millisecond timestamp (standard for this app)
                d_val = t.deadline
                if isinstance(d_val, str): d_val = int(d_val)
                finish = datetime.fromtimestamp(d_val / 1000)
            except Exception:
                # Fallback if invalid
                finish = start + timedelta(days=1)
                is_projected = True
        else:
            # Fallback: Start + 1 day
            finish = start + timedelta(days=1)
            is_projected = True
            
        # Determine Assignee Display
        assignee_label = "Unassigned"
        if current_user_role == "member":
             assignee_label = current_username
        else:
             assignee_label = "Unassigned"
        
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
    fig.add_vline(x=now.timestamp() * 1000, line_width=1, line_dash="dash", line_color="red", annotation_text="Today")
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Legend / Tips
    st.caption("💡 **Tip:** Bars shown in faded colors indicate projected deadlines (Next Day) where no specific deadline was set.")


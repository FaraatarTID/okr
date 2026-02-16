"""
AI Service for OKR Application.
Context-aware Gemini analysis with aggregated data preprocessing.
"""
import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st
from src.utils.time_utils import utc_now

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from src.models import Objective, KeyResult, Task, TaskStatus, AnalysisContext

# Load .env from parent directory (okr/) where .streamlit is located
_parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(_parent_dir, ".env"))


def get_api_key() -> Optional[str]:
    """Get Gemini API key from secrets or environment."""
    # Try Streamlit secrets first (with error handling)
    try:
        if hasattr(st, 'secrets') and "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass  # Secrets not configured, fall back to env
    
    return os.getenv("VITE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")



def build_analysis_context(objective: Objective, 
                           key_results: List[KeyResult],
                           tasks: List[Task]) -> AnalysisContext:
    """
    Preprocess and aggregate data before calling Gemini.
    This reduces token usage and provides cleaner context.
    """
    completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    total_minutes = sum(t.total_time_spent for t in tasks)
    kr_progress = [kr.current_value for kr in key_results]
    
    return AnalysisContext(
        objective=objective.title,
        tasks_count=len(tasks),
        completed_tasks=completed_tasks,
        total_minutes_spent=total_minutes,
        kr_progress=kr_progress
    )


def analyze_efficiency_effectiveness(
    key_result: KeyResult,
    tasks: List[Task]
) -> Dict[str, Any]:
    """
    Analyze a Key Result for efficiency (Time Spent vs Estimate) 
    and effectiveness (Task Completion vs KR Progress).
    
    Returns JSON with:
    - efficiency_score (0-100)
    - effectiveness_score (0-100)
    - advice_list (list of recommendations)
    """
    if not GENAI_AVAILABLE:
        return {"error": "google-generativeai not installed"}
    
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}
    
    # Aggregate task data
    total_estimated = sum(t.estimated_minutes for t in tasks)
    total_spent = sum(t.total_time_spent for t in tasks)
    completed_count = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    in_progress_count = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
    
    # Build task details for context
    tasks_context = []
    for t in tasks:
        tasks_context.append({
            "title": t.title,
            "status": t.status.value,
            "estimated_min": t.estimated_minutes,
            "spent_min": t.total_time_spent,
            "start_date": t.start_date.isoformat() if t.start_date else None,
            "deadline": t.deadline # milliseconds or datetime? Model has int usually, checking... Task model has 'deadline'? 
            # In models.py Task has 'deadline' via NodeBase? Yes. NodeBase has deadline: int (timestamp).
            # Let's convert to ISO for AI readability.
        })
        # Wait, I need to check if Task has 'deadline' on the object in this scope. 
        # Yes, Task inherits NodeBase.
    
    # Correction: loops above used t.deadline? No, they didn't use it.
    # Let's re-write the loop properly.
    
    for t in tasks:
        d_iso = None
        if t.deadline:
             try:
                 d_iso = datetime.fromtimestamp(t.deadline / 1000).isoformat()
             except: pass
             
        tasks_context.append({
            "title": t.title,
            "status": t.status.value,
            "estimated_min": t.estimated_minutes,
            "spent_min": t.total_time_spent,
            "start_date": t.start_date.isoformat() if t.start_date else None,
            "deadline": d_iso
        })
    
    context = {
        "key_result": {
            "title": key_result.title,
            "description": key_result.description or "",
            "target_value": key_result.target_value,
            "current_value": key_result.current_value,
            "unit": key_result.unit or "%"
        },
        "metrics": {
            "total_tasks": len(tasks),
            "completed_tasks": completed_count,
            "in_progress_tasks": in_progress_count,
            "total_estimated_minutes": total_estimated,
            "total_spent_minutes": total_spent
        },
        "tasks": tasks_context
    }
    
    prompt = f"""
    You are an expert OKR Analyst. Analyze the following Key Result data.

    KEY RESULT: "{key_result.title}"
    Description: "{key_result.description or 'N/A'}"
    Progress: {key_result.current_value}/{key_result.target_value} {key_result.unit or '%'}

    TASK METRICS:
    - Total Tasks: {len(tasks)}
    - Completed: {completed_count}
    - In Progress: {in_progress_count}
    - Total Estimated Time: {total_estimated} minutes
    - Total Time Spent: {total_spent} minutes

    TASKS DETAIL:
    {json.dumps(tasks_context, indent=2)}

    ---
    ANALYZE TWO DIMENSIONS:

    1. EFFICIENCY (Time Management):
       - Compare Time Spent vs Estimated Time
       - Score 100 = Perfect time management (spent ≈ estimated)
       - Score decreases for significant over/under estimation

    2. EFFECTIVENESS (Goal Achievement):
       - Compare Task Completion Progress vs KR Progress
       - Review Start Dates and Deadlines: Are tasks scheduled realistically? (If dates provided)
       - Note: "Tasks" are now the direct actionable level under a Key Result. "Initiatives" are tags for the Key Result.
       - Are completed tasks moving the KR metric?
       - Score 100 = Perfect alignment between work and results

    REQUIRED OUTPUT (JSON only):
    {{
        "efficiency_score": <number 0-100>,
        "effectiveness_score": <number 0-100>,
        "overall_score": <weighted average, weight efficiency 40%, effectiveness 60%>,
        "advice_list": ["<specific actionable advice 1>", "<advice 2>", ...],
        "gap_analysis": "<What's missing to achieve 100% fulfillment>",
        "summary": "<2 sentence executive summary>"
    }}

    IMPORTANT: Detect the language of the Key Result title. Generate all text in THAT language.
    Return ONLY valid JSON.
    """

    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        
        if not response.text:
            return {"error": "Gemini returned an empty response"}
        
        # Clean response
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        
        data = json.loads(raw_text)
        
        return {
            "efficiency_score": data.get("efficiency_score", 0),
            "effectiveness_score": data.get("effectiveness_score", 0),
            "overall_score": data.get("overall_score", 0),
            "advice_list": data.get("advice_list", []),
            "gap_analysis": data.get("gap_analysis", ""),
            "summary": data.get("summary", ""),
            "analyzed_at": utc_now().isoformat()
        }
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse Gemini response: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def analyze_objective(objective: Objective,
                      key_results: List[KeyResult],
                      all_tasks: List[Task]) -> Dict[str, Any]:
    """
    Comprehensive analysis of an Objective including all its Key Results.
    Aggregates context as specified in the implementation plan.
    """
    if not GENAI_AVAILABLE:
        return {"error": "google-generativeai not installed"}
    
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}
    
    # Build aggregated context
    context = build_analysis_context(objective, key_results, all_tasks)
    
    # Calculate additional metrics
    total_estimated = sum(t.estimated_minutes for t in all_tasks)
    efficiency_ratio = (context.total_minutes_spent / total_estimated * 100) if total_estimated > 0 else 0
    completion_rate = (context.completed_tasks / context.tasks_count * 100) if context.tasks_count > 0 else 0
    
    # KR details
    kr_details = []
    for kr in key_results:
        progress_pct = (kr.current_value / kr.target_value * 100) if kr.target_value > 0 else 0
        kr_details.append({
            "title": kr.title,
            "progress": f"{kr.current_value}/{kr.target_value} {kr.unit or '%'}",
            "progress_pct": round(progress_pct, 1)
        })
    
    prompt = f"""
    You are an expert Strategic OKR Analyst.

    OBJECTIVE: "{objective.title}"
    Description: "{objective.description or 'N/A'}"

    AGGREGATED METRICS:
    - Total Tasks: {context.tasks_count}
    - Completed Tasks: {context.completed_tasks} ({completion_rate:.1f}%)
    - Total Time Spent: {context.total_minutes_spent} minutes
    - Total Estimated Time: {total_estimated} minutes
    - Time Efficiency: {efficiency_ratio:.1f}%

    KEY RESULTS:
    {json.dumps(kr_details, indent=2)}

    ---
    PROVIDE A STRATEGIC ANALYSIS:

    1. Overall objective health
    2. Are the Key Results well-defined and measurable?
    3. Is the task scope sufficient to achieve all KRs?
    4. Time management assessment
    5. Recommendations for improvement

    REQUIRED OUTPUT (JSON):
    {{
        "efficiency_score": <0-100>,
        "effectiveness_score": <0-100>,
        "advice_list": ["<recommendation 1>", "<recommendation 2>", ...],
        "risk_factors": ["<potential risk 1>", ...],
        "summary": "<Executive summary in 2-3 sentences>"
    }}

    Detect and match the language of the Objective title.
    Return ONLY valid JSON.
    """

    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        
        if not response.text:
            return {"error": "Empty response from Gemini"}
        
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        data = json.loads(raw_text)
        
        return {
            "efficiency_score": data.get("efficiency_score", 0),
            "effectiveness_score": data.get("effectiveness_score", 0),
            "advice_list": data.get("advice_list", []),
            "risk_factors": data.get("risk_factors", []),
            "summary": data.get("summary", ""),
            "analyzed_at": utc_now().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# LEGACY DICT-BASED FUNCTIONS (Migrated from services/gemini.py)
# These work with JSON node dictionaries used in app.py
# =============================================================================

def analyze_node(node_id: int, node_type: str = "KEY_RESULT"):
    """
    Analyze a node (typically a Key Result) by fetching its data directly from SQL.
    Replaced legacy dictionary-based version for better performance and consistency.
    """
    from src.crud import get_node
    from src.models import Task, KeyResult, Objective, Goal
    
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}

    if not GENAI_AVAILABLE:
        return {"error": "google-generativeai not installed"}

    # Fetch node with all relationships for context
    node = get_node(node_id, node_type)
    if not node:
        return {"error": f"Node {node_id} ({node_type}) not found"}

    # Identify children and context
    # Usually we analyze Key Results (children = Tasks) or Objectives (children = KRs)
    children = []
    node_type_upper = node_type.upper()
    
    if node_type_upper == "GOAL":
        children = node.objectives
    elif node_type_upper == "OBJECTIVE":
        children = node.key_results
    elif node_type_upper in ["KEY_RESULT", "KEYRESULT"]:
        children = node.tasks
    
    # Prepare current snapshot for storage
    current_snapshot = {
        "title": node.title,
        "metrics": {
            "target": getattr(node, "target_value", 100.0),
            "current": getattr(node, "current_value", 0.0),
            "progress": getattr(node, "progress", 0)
        },
        "scope": []
    }
    
    children_text = ""
    from datetime import datetime
    for child in children:
        c_type = child.__tablename__.upper()
        c_title = child.title
        c_desc = child.description or ""
        c_progress = child.progress or 0
        c_status = "DONE" if c_progress == 100 else "IN PROGRESS"
        
        # Total time spent on this child
        c_time = getattr(child, "total_time_spent", 0)
        
        # Add to snapshot
        current_snapshot["scope"].append({
            "type": c_type,
            "title": c_title,
            "progress": c_progress
        })
        
        # Get recent work history if it's a Task
        work_summ_text = ""
        if c_type == "TASK":
            # Fetch recent logs in a live session to avoid detached lazy loads
            try:
                from src.database import get_session_context
                from sqlmodel import select
                from src.models import WorkLog
                with get_session_context() as s:
                    recent_logs = s.exec(
                        select(WorkLog)
                        .where(WorkLog.task_id == child.id)
                        .order_by(WorkLog.start_time.desc())
                    ).all()[:5]
                summaries = [l.summary for l in recent_logs if getattr(l, 'summary', None)]
                if summaries:
                    work_summ_text = "\n  Recent Work: " + "; ".join(summaries)
            except Exception:
                pass
        
        # Deadline information (robust parsing)
        deadline_info = ""
        dl_val = getattr(child, "deadline", None)
        if dl_val:
            from src.utils.deadline_utils import get_days_remaining
            try:
                dl_ms = None
                d_date = None
                if isinstance(dl_val, datetime):
                    dl_ms = int(dl_val.timestamp() * 1000)
                    d_date = dl_val.date()
                elif isinstance(dl_val, (int, float)):
                    ts = float(dl_val)
                    if ts > 1e10:  # milliseconds
                        dl_ms = int(ts)
                        d_date = datetime.fromtimestamp(ts / 1000.0).date()
                    else:  # seconds
                        dl_ms = int(ts * 1000)
                        d_date = datetime.fromtimestamp(ts).date()
                elif isinstance(dl_val, str):
                    try:
                        ts = float(dl_val)
                        if ts > 1e10:
                            dl_ms = int(ts)
                            d_date = datetime.fromtimestamp(ts / 1000.0).date()
                        else:
                            dl_ms = int(ts * 1000)
                            d_date = datetime.fromtimestamp(ts).date()
                    except Exception:
                        try:
                            dtp = datetime.fromisoformat(dl_val)
                            dl_ms = int(dtp.timestamp() * 1000)
                            d_date = dtp.date()
                        except Exception:
                            dl_ms = None
                if dl_ms and d_date:
                    days = get_days_remaining(dl_ms)
                    deadline_info = f"\n  Deadline: {d_date} ({days} days remaining)"
            except Exception:
                pass

        # Start Date
        start_date_info = ""
        if hasattr(child, "start_date") and child.start_date:
             start_date_info = f"\n  Start Date: {child.start_date.date()}"
        
        children_text += f"- [{c_type}] {c_title}\n  Description: {c_desc}\n  Status: {c_status} ({c_progress}%)\n  Time: {c_time}m{start_date_info}{deadline_info}{work_summ_text}\n"

    prompt = f"""
    You are an expert Strategic OKR Analyst. 
    
    Target Node ({node_type_upper}): "{node.title}"
    Description: "{node.description or 'N/A'}"
    
    CURRENT STATE:
    - Target: {current_snapshot['metrics']['target']}
    - Current: {current_snapshot['metrics']['current']}
    - Progress: {current_snapshot['metrics']['progress']}%
    - Defined Scope (Children):
    {children_text}
    
    ---
    PREVIOUS ANALYSIS RESULTS:
    {json.dumps(node.gemini_analysis, indent=2, ensure_ascii=False) if node.gemini_analysis else "N/A (First Run)"}
    
    ---
    YOUR OBJECTIVE:
    Conduct a rigorous audit. Evaluate dimensions:
    
    1. PROGRESSION & DELTA CHECK:
       - Identify what has changed. If the user addressed previous gaps, acknowledge them.
    
    2. EFFICIENCY (Completeness of Scope): 
       - Is this work actually sufficient to achieve the parent goal?
    
    3. EFFECTIVENESS (Quality of Strategy):
       - Are the defined children the *right* things to do?
    
    REQUIRED OUTPUT (JSON only):
    {{
        "efficiency_score": <number 0-100>,
        "effectiveness_score": <number 0-100>,
        "overall_score": <number 0-100>,
        "deadline_warnings": ["<Something is overdue>", ...],
        "gap_analysis": "<What is missing to reach 100% fulfillment>",
        "quality_assessment": "<Critique of children quality>",
        "proposed_tasks": ["<New Task 1>", "<New Task 2>", ...],
        "summary": "<2 sentence executive summary>"
    }}
    
    Match the language of the title. Return ONLY valid JSON.
    """

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        
        if not response.text:
            return {"error": "Gemini returned an empty response."}
        
        raw_text = response.text.strip()
        # Basic cleanup of markdown markers if any
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].startswith("```"): lines = lines[:-1]
            raw_text = "\n".join(lines).strip()
            
        data = json.loads(raw_text)
        
        return {
            "efficiency_score": data.get("efficiency_score", 0),
            "effectiveness_score": data.get("effectiveness_score", 0),
            "overall_score": data.get("overall_score", 0),
            "deadline_warnings": data.get("deadline_warnings", []),
            "gap_analysis": data.get("gap_analysis", ""),
            "quality_assessment": data.get("quality_assessment", ""),
            "proposed_tasks": data.get("proposed_tasks", []),
            "summary": data.get("summary", ""),
            "analyzed_at": utc_now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_team_health(team_data: dict) -> dict:
    """
    AI Team Coach: Analyze team health and provide actionable coaching tips.
    
    Args:
        team_data: Dictionary containing aggregated team metrics
            - members: list of member stats
            - deadline_stats: aggregate deadline health
            - krs: key result metrics
            - progress_distribution: how work is distributed
    
    Returns:
        Coaching insights with scores and recommendations
    """
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}
    
    if not GENAI_AVAILABLE:
        return {"error": "google-generativeai not installed"}
    
    prompt = f"""
    You are an elite Executive OKR Coach and Team Performance Advisor.
    Your mission: Analyze this team's data and provide strategic coaching to the manager.
    
    === TEAM HEALTH DATA ===
    
    TEAM COMPOSITION:
    {json.dumps(team_data.get('members', []), indent=2, ensure_ascii=False)}
    
    DEADLINE HEALTH:
    - Total tasks with deadlines: {team_data.get('total_with_deadline', 0)}
    - Completed on time: {team_data.get('completed', 0)}
    - On track: {team_data.get('on_track', 0)}
    - At risk: {team_data.get('at_risk', 0)}
    - Overdue: {team_data.get('overdue', 0)}
    
    KEY RESULTS SUMMARY:
    - Total KRs: {team_data.get('total_krs', 0)}
    - At-Risk KRs: {team_data.get('at_risk_krs', 0)}
    - Avg Confidence: {team_data.get('avg_confidence', 0)}/10
    - Data Hygiene: {team_data.get('hygiene_pct', 0)}%
    
    PROGRESS DISTRIBUTION:
    {json.dumps(team_data.get('progress_distribution', []), indent=2, ensure_ascii=False)}
    
    === YOUR COACHING MISSION ===
    
    Analyze this data like a world-class performance coach. Evaluate FIVE dimensions:
    
    1. 🚀 PRODUCTIVITY PULSE - Is the team making consistent progress?
    2. ⏰ DEADLINE DISCIPLINE - How well does the team manage deadlines?
    3. 🎯 STRATEGIC ALIGNMENT - Are people working on the RIGHT things?
    4. ⚖️ WORKLOAD BALANCE - Is work distributed fairly?
    5. 📈 MOMENTUM & MORALE - Is the team accelerating or slowing down?
    
    === REQUIRED OUTPUT (JSON) ===
    {{
        "overall_health_score": <0-100>,
        "health_grade": "<A/B/C/D/F>",
        "headline": "<One powerful sentence summarizing team state>",
        
        "dimensions": {{
            "productivity": {{
                "score": <0-100>,
                "status": "<🟢 Excellent | 🟡 Needs Attention | 🔴 Critical>",
                "insight": "<1-2 sentence observation>",
                "action": "<Specific action the manager should take>"
            }},
            "deadline_discipline": {{ "score": <0-100>, "status": "<🟢 | 🟡 | 🔴>", "insight": "<observation>", "action": "<action>" }},
            "strategic_alignment": {{ "score": <0-100>, "status": "<🟢 | 🟡 | 🔴>", "insight": "<observation>", "action": "<action>" }},
            "workload_balance": {{ "score": <0-100>, "status": "<🟢 | 🟡 | 🔴>", "insight": "<observation>", "action": "<action>" }},
            "momentum": {{ "score": <0-100>, "status": "<🟢 | 🟡 | 🔴>", "insight": "<observation>", "action": "<action>" }}
        }},
        
        "top_priorities": ["<#1 thing the manager should focus on this week>", "<#2 priority>", "<#3 priority>"],
        "quick_wins": ["<Easy fix that will show immediate results>", "<Another quick win>"],
        "watch_out": "<One critical risk to monitor>"
    }}
    
    COACHING STYLE: Be direct but constructive. Use the manager's perspective.
    Detect language from the data and respond in the SAME language.
    Return ONLY valid JSON.
    """
    
    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        
        if not response.text:
            return {"error": "Gemini returned an empty response."}
        
        # Clean response
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        
        data = json.loads(raw_text)
        return {"coaching": data}
        
    except Exception as e:
        return {"error": str(e)}


def generate_weekly_summary(username: str, start_date_str: str, end_date_str: str, stats: dict) -> dict:
    """
    Generate a narrative summary of the week's work.
    
    Args:
        username: Name of the user
        start_date_str: Start date of period
        end_date_str: End date of period
        stats: Dictionary containing:
            - total_minutes: total time worked
            - tasks_completed: count of completed tasks
            - krs_updated: count of KRs updated
            - objectives_text: list of objectives worked on with time
            - key_achievements: list of completed task titles
            - work_logs_text: condensed list of work logs
            
    Returns:
        JSON with 'summary_markdown', 'highlights', 'focus_analysis'
    """
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}
    
    if not GENAI_AVAILABLE:
        return {"error": "google-generativeai not installed"}
        
    prompt = f"""
    You are an Executive Assistant drafting a Weekly Work Report for {username}.
    Period: {start_date_str} to {end_date_str}
    
    === WORK STATISTICS ===
    - Total Time: {stats.get('total_minutes', 0) // 60}h {stats.get('total_minutes', 0) % 60}m
    - Tasks Completed: {stats.get('tasks_completed', 0)}
    - KRs Progressed: {stats.get('krs_updated', 0)}
    
    === KEY ACHIEVEMENTS (Completed Tasks) ===
    {json.dumps(stats.get('key_achievements', []), indent=2, ensure_ascii=False)}
    
    === TIME BY OBJECTIVE ===
    {json.dumps(stats.get('objectives_text', []), indent=2, ensure_ascii=False)}
    
    === DETAILED WORK LOGS ===
    {stats.get('work_logs_text', 'No detailed logs.')}
    
    === YOUR TASK ===
    Write a professional, concise executive summary of the week.
    
    REQUIRED OUTPUT (JSON):
    {{
        "summary_markdown": "<2-3 paragraphs summarizing what was accomplished. Use bolding for key projects. Tone: Professional, confident.>",
        "highlights": [
            "<Bullet point 1: Major win>",
            "<Bullet point 2: Key progress>",
            "<Bullet point 3>"
        ],
        "focus_analysis": "<1 sentence analyzing where most time was spent (Strategic vs Tactical)>"
    }}
    
    Detect language from the work logs and write the summary in the SAME language.
    Return ONLY valid JSON.
    """
    
    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        
        if not response.text:
            return {"error": "Gemini returned an empty response."}
            
        # Clean response
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        return json.loads(raw_text)
        
    except Exception as e:
        return {"error": str(e)}


def suggest_critical_task(task_candidates: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Ask Gemini to pick the single most critical task (urgent + important) from candidates.

    Expected candidate shape:
    {
      "task_ref": "task_123",
      "title": "...",
      "status": "...",
      "progress": 0-100,
      "deadline": "ISO-8601 or null",
      "owner_name": "...",
      "path": "Goal > Objective > KR > Task",
      "attention": "Needs care|On track|Complete",
      "parent_kr_ai_score": 0-100 or null,
      "local_priority_score": number
    }
    """
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}

    if not GENAI_AVAILABLE:
        return {"error": "google-generativeai not installed"}

    normalized_candidates: List[Dict[str, Any]] = []
    for raw in task_candidates or []:
        if not isinstance(raw, dict):
            continue
        task_ref = str(raw.get("task_ref") or raw.get("ref") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not task_ref or not title:
            continue
        normalized_candidates.append(
            {
                "task_ref": task_ref,
                "title": title,
                "status": str(raw.get("status") or ""),
                "progress": raw.get("progress"),
                "deadline": raw.get("deadline"),
                "owner_name": str(raw.get("owner_name") or ""),
                "path": str(raw.get("path") or ""),
                "attention": str(raw.get("attention") or ""),
                "parent_kr_ai_score": raw.get("parent_kr_ai_score"),
                "local_priority_score": raw.get("local_priority_score"),
            }
        )

    if not normalized_candidates:
        return {"error": "No valid task candidates provided."}

    if len(normalized_candidates) > 120:
        normalized_candidates = normalized_candidates[:120]

    context_obj = context if isinstance(context, dict) else {}

    prompt = f"""
    You are an elite execution coach.
    Choose ONE task that should be worked on next (highest combined urgency + strategic importance).

    Decision criteria:
    - Deadline risk (overdue / near due date)
    - Strategic impact (especially if parent KR health is weak)
    - Progress state (stuck or low progress tasks are often more critical)
    - Attention signals and local priority score
    - Avoid already complete tasks unless no better option exists

    CONTEXT:
    {json.dumps(context_obj, ensure_ascii=False, indent=2)}

    TASK CANDIDATES:
    {json.dumps(normalized_candidates, ensure_ascii=False, indent=2)}

    REQUIRED OUTPUT (JSON only):
    {{
      "task_ref": "<exact task_ref from candidates>",
      "reason": "<short, concrete reason in 1-2 sentences>",
      "confidence": <0-100>
    }}

    Return ONLY valid JSON.
    """

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        if not response.text:
            return {"error": "Gemini returned an empty response."}

        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        data = json.loads(raw_text)

        selected_ref_raw = str(data.get("task_ref") or "").strip()
        if not selected_ref_raw:
            return {"error": "AI did not return a task_ref."}

        by_ref = {item["task_ref"]: item for item in normalized_candidates}
        by_ref_lower = {key.lower(): key for key in by_ref}

        selected_ref = by_ref.get(selected_ref_raw)
        if selected_ref is None:
            canonical_ref = by_ref_lower.get(selected_ref_raw.lower())
            selected_ref = by_ref.get(canonical_ref) if canonical_ref else None

        if selected_ref is None:
            return {"error": "AI returned task_ref outside candidate set."}

        reason = str(data.get("reason") or "").strip()
        confidence_val = data.get("confidence")
        confidence = None
        try:
            if confidence_val is not None:
                confidence = max(0, min(100, int(float(confidence_val))))
        except Exception:
            confidence = None

        return {
            "task_ref": selected_ref["task_ref"],
            "reason": reason or "AI marked this as the most urgent and important next step.",
            "confidence": confidence,
        }
    except Exception as exc:
        return {"error": str(exc)}


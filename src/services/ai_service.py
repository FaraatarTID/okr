"""
AI Service for OKR Application.
Context-aware AI analysis with aggregated data preprocessing.
"""

import os
import json
import logging
import types
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv
from src.utils.time_utils import from_epoch_millis, from_epoch_seconds, utc_now

from src.services.ai_provider import (
    generate_json as generate_ai_json,
    get_gemini_api_key,
    is_external_ai_allowed as provider_external_ai_allowed,
)
from src.config_runtime import get_config_value
from src.services.backend_client import is_backend_enabled
from src.services.job_service import run_job_and_wait

from src.models import Objective, KeyResult, Task, TaskStatus

logger = logging.getLogger(__name__)

# Load .env from repository root (okr/)
_parent_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
load_dotenv(os.path.join(_parent_dir, ".env"))


def is_external_ai_allowed() -> bool:
    """Backward-compatible export used by runtime preflight."""
    return provider_external_ai_allowed()


def get_api_key() -> Optional[str]:
    """Backward-compatible export for existing runtime checks."""
    return get_gemini_api_key()


def _run_ai_json_prompt(prompt: str) -> Dict[str, Any]:
    """Invoke configured AI provider and normalize error shape."""
    if is_backend_enabled():
        actor = (
            str(get_config_value("OKR_BACKEND_DEFAULT_ACTOR", "system")).strip()
            or "system"
        )
        response = run_job_and_wait(
            kind="ai.generate_json",
            payload={"prompt": prompt},
            actor_username=actor,
            timeout_seconds=90,
            poll_seconds=1.0,
        )
    else:
        response = generate_ai_json(prompt)
    if isinstance(response, dict):
        return response
    return {"error": "AI provider returned non-dict response."}



def analyze_node(
    node_id: int,
    node_type: Optional[str] = "KEY_RESULT",
    actor_username: Optional[str] = None,
):
    """
    Analyze a node (typically a Key Result) by fetching its data directly from SQL.
    Replaced legacy dictionary-based version for better performance and consistency.
    """
    try:
        return _analyze_node_inner(node_id, node_type, actor_username)
    except PermissionError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception(
            "Unhandled error in analyze_node(%s, %s)", node_id, node_type
        )
        return {"error": f"Node analysis failed: {exc}"}


def _fetch_node_for_analysis(
    node_id: int,
    node_type: str,
    actor_username: Optional[str] = None,
):
    """Try direct PostgreSQL first; fall back to Supabase REST API (HTTPS 443)."""
    from src.crud import get_node

    try:
        node = get_node(node_id, node_type, actor_username=actor_username)
        if not node:
            return {"error": f"Node {node_id} ({node_type}) not found"}
        return node
    except Exception as direct_err:
        logger.warning(
            "Direct DB fetch failed for %s %s: %s — trying REST API fallback",
            node_type, node_id, direct_err,
        )

    try:
        from src.services.supabase_api_mode import (
            is_supabase_api_mode_enabled,
        )
        if not is_supabase_api_mode_enabled():
            raise RuntimeError("Supabase REST API not configured; cannot fall back.")

        rest_result = _fetch_node_via_rest(node_id, node_type, actor_username)
        if rest_result is None:
            return {"error": f"Node {node_id} ({node_type}) not found"}
        return rest_result
    except Exception as rest_err:
        logger.error(
            "REST API fallback also failed for %s %s: %s",
            node_type, node_id, rest_err,
        )
        return {"error": f"Node fetch failed (direct + REST): {rest_err}"}


def _fetch_node_via_rest(
    node_id: int, node_type: str, actor_username: Optional[str] = None
):
    """Fetch a node via Supabase REST API and return a lightweight namespace object."""
    from src.services.supabase_api_mode import _rest_select

    table_map = {
        "GOAL": "goal",
        "OBJECTIVE": "objective",
        "KEY_RESULT": "key_result",
        "KEYRESULT": "key_result",
        "TASK": "task",
    }
    table = table_map.get(node_type)
    if not table:
        return None

    status, rows = _rest_select(
        table,
        query={"id": f"eq.{node_id}", "select": "*"},
    )
    if status >= 400 or not rows:
        return None
    row = rows[0]

    child_table_map = {
        "GOAL": ("objective", "goal_id"),
        "OBJECTIVE": ("key_result", "objective_id"),
        "KEY_RESULT": ("task", "key_result_id"),
        "KEYRESULT": ("task", "key_result_id"),
        "TASK": (None, None),
    }
    child_table, fk_col = child_table_map.get(node_type, (None, None))

    children = []
    if child_table and fk_col:
        _, child_rows = _rest_select(
            child_table,
            query={fk_col: f"eq.{node_id}", "select": "*"},
        )
        children = child_rows or []

    child_attr_map = {
        "GOAL": "objectives",
        "OBJECTIVE": "key_results",
        "KEY_RESULT": "tasks",
        "KEYRESULT": "tasks",
        "TASK": "work_logs",
    }
    child_attr = child_attr_map.get(node_type, "children")

    ns = types.SimpleNamespace(**row)
    setattr(ns, child_attr, [_simple_namespace_from_row(c) for c in children])
    ns.__tablename__ = table.upper()

    return ns


def _simple_namespace_from_row(row: dict):
    """Convert a REST API row dict to a SimpleNamespace with __tablename__."""
    ns = types.SimpleNamespace(**row)
    if "title" in row:
        table = "task" if "deadline" in row and "key_result_id" in row else (
            "key_result" if "target_value" in row else (
                "objective" if "goal_id" in row else "goal"
            )
        )
        ns.__tablename__ = table
    return ns


def _fetch_recent_worklog_summaries(task_id: int) -> list:
    """Try direct DB first for WorkLog summaries; fall back to REST API."""
    try:
        from src.database import get_session_context
        from sqlmodel import select
        from src.models import WorkLog

        with get_session_context() as s:
            recent_logs = s.exec(
                select(WorkLog)
                .where(WorkLog.task_id == task_id)
                .order_by(WorkLog.start_time.desc())
            ).all()[:5]
        return [
            log_row.summary
            for log_row in recent_logs
            if getattr(log_row, "summary", None)
        ]
    except Exception as direct_err:
        logger.debug(
            "Direct DB worklog fetch failed for task %s: %s — trying REST API",
            task_id, direct_err,
        )

    try:
        from src.services.supabase_api_mode import (
            is_supabase_api_mode_enabled, _rest_select,
        )

        if not is_supabase_api_mode_enabled():
            return []
        _, rows = _rest_select(
            "work_log",
            query={
                "task_id": f"eq.{task_id}",
                "select": "summary,start_time",
                "order": "start_time.desc",
                "limit": "5",
            },
        )
        return [r["summary"] for r in rows if r.get("summary")]
    except Exception as rest_err:
        logger.debug(
            "REST API worklog fallback also failed for task %s: %s",
            task_id, rest_err,
        )
        return []


def _analyze_node_inner(
    node_id: int,
    node_type: Optional[str] = "KEY_RESULT",
    actor_username: Optional[str] = None,
):
    node_type_upper = str(node_type or "KEY_RESULT").upper()

    node = _fetch_node_for_analysis(
        node_id, node_type_upper, actor_username=actor_username
    )
    if isinstance(node, dict):
        return node

    # Identify children and context
    # Usually we analyze Key Results (children = Tasks) or Objectives (children = KRs)
    children = []
    if node_type_upper == "GOAL":
        children = node.objectives
    elif node_type_upper == "OBJECTIVE":
        children = node.key_results
    elif node_type_upper in ["KEY_RESULT", "KEYRESULT"]:
        children = node.tasks

    # Prepare current snapshot for storage
    # Goals/Objectives: progress is a computed rollup (not user-set), deadline is cycle-bounded.
    # KRs: progress is measured via check-ins, deadline is not used (cycle-bounded).
    # Tasks: progress is user-set, deadline is meaningful.
    current_snapshot = {
        "title": node.title,
        "metrics": {},
        "scope": [],
    }
    if node_type_upper == "KEY_RESULT":
        current_snapshot["metrics"] = {
            "target": getattr(node, "target_value", 100.0),
            "current": getattr(node, "current_value", 0.0),
            "progress": getattr(node, "progress", 0),
        }
    elif node_type_upper == "TASK":
        deadline_val = getattr(node, "deadline", None)
        current_snapshot["metrics"] = {
            "progress": getattr(node, "progress", 0),
            "deadline": str(deadline_val.date()) if deadline_val else "none",
            "total_time_spent": getattr(node, "total_time_spent", 0),
        }
    # Goals and Objectives have no user-settable metrics — they are rollup containers.

    children_text = ""
    for child in children:
        c_type = child.__tablename__.upper()
        c_title = child.title
        c_desc = child.description or ""
        # Only include progress for KRs and Tasks (meaningful measured values)
        c_progress = child.progress or 0
        c_status = "DONE" if c_progress == 100 else "IN PROGRESS"
        if c_type not in ("KEY_RESULT", "TASK"):
            c_status = "PLANNED" if c_progress == 0 else "IN PROGRESS"

        # Total time spent on this child
        c_time = getattr(child, "total_time_spent", 0)

        # Add to snapshot
        current_snapshot["scope"].append(
            {"type": c_type, "title": c_title, "progress": c_progress}
        )

        # Get recent work history if it's a Task
        work_summ_text = ""
        if c_type == "TASK":
            summaries = _fetch_recent_worklog_summaries(child.id)
            if summaries:
                work_summ_text = "\n  Recent Work: " + "; ".join(summaries)

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
                        d_date = from_epoch_millis(ts).date()
                    else:  # seconds
                        dl_ms = int(ts * 1000)
                        d_date = from_epoch_seconds(ts).date()
                elif isinstance(dl_val, str):
                    try:
                        ts = float(dl_val)
                        if ts > 1e10:
                            dl_ms = int(ts)
                            d_date = from_epoch_millis(ts).date()
                        else:
                            dl_ms = int(ts * 1000)
                            d_date = from_epoch_seconds(ts).date()
                    except Exception as exc:
                        logger.debug(
                            "Failed numeric deadline parse for child '%s': %s",
                            getattr(child, "id", None),
                            exc,
                        )
                        try:
                            dtp = datetime.fromisoformat(dl_val)
                            dl_ms = int(dtp.timestamp() * 1000)
                            d_date = dtp.date()
                        except Exception as nested_exc:
                            logger.debug(
                                "Failed ISO deadline parse for child '%s': %s",
                                getattr(child, "id", None),
                                nested_exc,
                            )
                            dl_ms = None
                if dl_ms and d_date:
                    days = get_days_remaining(dl_ms)
                    deadline_info = f"\n  Deadline: {d_date} ({days} days remaining)"
            except Exception as exc:
                logger.debug(
                    "Failed to parse deadline for child '%s': %s",
                    getattr(child, "id", None),
                    exc,
                )

        # Start Date
        start_date_info = ""
        if hasattr(child, "start_date") and child.start_date:
            start_date_info = f"\n  Start Date: {child.start_date.date()}"

        children_text += f"- [{c_type}] {c_title}\n  Description: {c_desc}\n  Status: {c_status} ({c_progress}%)\n  Time: {c_time}m{start_date_info}{deadline_info}{work_summ_text}\n"

    prompt = f"""
    You are an expert Strategic OKR Analyst.

    OKR METHODOLOGY RULES:
    - Goals and Objectives are time-bounded by the OKR cycle, NOT by individual deadlines.
    - Only Key Results have measurable progress (via check-in sessions).
    - Only Tasks have deadlines.
    - Progress on Goals/Objectives is a computed rollup from child KRs — do NOT treat it as user-set.
    - The user writes insights about progress projections in retro sessions (experiments).

    Target Node ({node_type_upper}): "{node.title}"
    Description: "{node.description or "N/A"}"

    CURRENT STATE:
    {json.dumps(current_snapshot["metrics"], indent=2, ensure_ascii=False)}
    Defined Scope (Children):
    {children_text}

    ---
    PREVIOUS ANALYSIS RESULTS:
    {json.dumps(node.gemini_analysis, indent=2, ensure_ascii=False) if node.gemini_analysis else "N/A (First Run)"}

    ---
    YOUR OBJECTIVE:
    Conduct a rigorous audit. Evaluate dimensions:

    1. PROGRESSION & DELTA CHECK:
       - Identify what has changed. If the user addressed previous gaps, acknowledge them.
       - For KRs: compare current_value vs target_value and check-in history.

    2. EFFICIENCY (Completeness of Scope):
       - Is this work actually sufficient to achieve the parent goal?

    3. EFFECTIVENESS (Quality of Strategy):
       - Are the defined children the *right* things to do?

    CRITICAL: Your proposed_tasks MUST be specific, actionable, OKR-aligned work items.
    Each proposed task must include:
    - What exactly to do (not vague advice like "improve quality")
    - Who should own it (role or responsibility)
    - A concrete deadline or timeframe
    - How it connects to the target KPI movement

    Bad examples: "تعریف دقیق KPIها", "اجرای بازرسی پایه‌ای"
    Good examples: "Set baseline KPI value to X and target to Y by [date], assigned to [role]", "Conduct root-cause analysis on blockers identified in sprint review by [date]"

    REQUIRED OUTPUT (JSON only):
    {{
        "efficiency_score": <number 0-100>,
        "effectiveness_score": <number 0-100>,
        "overall_score": <number 0-100>,
        "deadline_warnings": ["<Something is overdue>", ...],
        "gap_analysis": "<What is missing to reach 100% fulfillment, with specific next steps>",
        "quality_assessment": "<Critique of children quality, with concrete improvement suggestions>",
        "proposed_tasks": ["<Specific actionable task with owner and deadline>", ...],
        "summary": "<2 sentence executive summary>"
    }}

    Match the language of the title. Return ONLY valid JSON.
    """

    data = _run_ai_json_prompt(prompt)
    if "error" in data:
        return {"error": data.get("error")}

    return {
        "efficiency_score": data.get("efficiency_score", 0),
        "effectiveness_score": data.get("effectiveness_score", 0),
        "overall_score": data.get("overall_score", 0),
        "deadline_warnings": data.get("deadline_warnings", []),
        "gap_analysis": data.get("gap_analysis", ""),
        "quality_assessment": data.get("quality_assessment", ""),
        "proposed_tasks": data.get("proposed_tasks", []),
        "summary": data.get("summary", ""),
        "analyzed_at": utc_now().isoformat(),
    }


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
    prompt = f"""
    You are an elite Executive OKR Coach and Team Performance Advisor.
    Your mission: Analyze this team's data and provide strategic coaching to the manager.
    
    === TEAM HEALTH DATA ===
    
    TEAM COMPOSITION:
    {json.dumps(team_data.get("members", []), indent=2, ensure_ascii=False)}
    
    DEADLINE HEALTH:
    - Total tasks with deadlines: {team_data.get("total_with_deadline", 0)}
    - Completed on time: {team_data.get("completed", 0)}
    - On track: {team_data.get("on_track", 0)}
    - At risk: {team_data.get("at_risk", 0)}
    - Overdue: {team_data.get("overdue", 0)}
    
    KEY RESULTS SUMMARY:
    - Total KRs: {team_data.get("total_krs", 0)}
    - At-Risk KRs: {team_data.get("at_risk_krs", 0)}
    - Avg Confidence: {team_data.get("avg_confidence", 0)}/10
    - Data Hygiene: {team_data.get("hygiene_pct", 0)}%
    
    PROGRESS DISTRIBUTION:
    {json.dumps(team_data.get("progress_distribution", []), indent=2, ensure_ascii=False)}
    
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

    data = _run_ai_json_prompt(prompt)
    if "error" in data:
        return {"error": data.get("error")}
    return {"coaching": data}


def generate_predictive_outlook(
    burnout_data: dict,
    strategy_gaps: list,
    cycle_title: str = "Current Cycle",
) -> Dict[str, Any]:
    """
    Ask configured AI provider to generate a strategic "Predictive Outlook" based
    on their burnout risk snapshot and any strategy gaps in their cycle.

    Returns a JSON dict with:
      - outlook_summary: 2-3 sentence narrative
      - risk_mitigation: list of actionable recommendations
      - strategic_pivots: list of suggested priority shifts
      - confidence_level: 0-100
    """
    gap_summaries = []
    for g in strategy_gaps[:5]:
        gap_summaries.append(
            f"- {g.get('title', '?')}: {g.get('gap_type', '?')} "
            f"(severity {g.get('severity', 0)}, progress {g.get('progress', 0)}%)"
        )

    prompt = f"""
    You are a strategic OKR advisor. Based on the data below, produce a
    "Predictive Outlook" for the user's quarter.

    CYCLE: "{cycle_title}"

    BURNOUT RISK SNAPSHOT:
    - Risk Score: {burnout_data.get("risk_score", 0)} / 100
    - Risk Label: {burnout_data.get("risk_label", "Unknown")}
    - Avg Daily Focus: {burnout_data.get("avg_daily_minutes", 0)} minutes
    - Tasks Completed (14d): {burnout_data.get("completed_tasks", 0)}
    - Work Days Active: {burnout_data.get("work_days", 0)}

    STRATEGY GAPS (top objectives at risk):
    {chr(10).join(gap_summaries) if gap_summaries else "None detected."}

    ---
    PRODUCE (JSON only):
    {{
        "outlook_summary": "<2-3 sentence strategic narrative>",
        "risk_mitigation": ["<actionable recommendation 1>", ...],
        "strategic_pivots": ["<priority shift suggestion 1>", ...],
        "confidence_level": <0-100>
    }}

    IMPORTANT: Match the language of the cycle title. Return ONLY valid JSON.
    """

    data = _run_ai_json_prompt(prompt)
    if "error" in data:
        return {"error": data.get("error")}

    return {
        "outlook_summary": data.get("outlook_summary", ""),
        "risk_mitigation": data.get("risk_mitigation", []),
        "strategic_pivots": data.get("strategic_pivots", []),
        "confidence_level": data.get("confidence_level", 50),
        "generated_at": utc_now().isoformat(),
    }

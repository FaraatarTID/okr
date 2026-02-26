"""
AI Service for OKR Application.
Context-aware AI analysis with aggregated data preprocessing.
"""

import os
import json
import logging
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

from src.models import Objective, KeyResult, Task, TaskStatus, AnalysisContext

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


def build_analysis_context(
    objective: Objective, key_results: List[KeyResult], tasks: List[Task]
) -> AnalysisContext:
    """
    Preprocess and aggregate data before calling configured AI provider.
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
        kr_progress=kr_progress,
    )


def analyze_efficiency_effectiveness(
    key_result: KeyResult, tasks: List[Task]
) -> Dict[str, Any]:
    """
    Analyze a Key Result for efficiency (Time Spent vs Estimate)
    and effectiveness (Task Completion vs KR Progress).

    Returns JSON with:
    - efficiency_score (0-100)
    - effectiveness_score (0-100)
    - advice_list (list of recommendations)
    """
    # Aggregate task data
    total_estimated = sum(t.estimated_minutes for t in tasks)
    total_spent = sum(t.total_time_spent for t in tasks)
    completed_count = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    in_progress_count = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)

    # Build task details for context
    tasks_context = []
    for t in tasks:
        d_iso = None
        if t.deadline:
            try:
                d_iso = from_epoch_millis(t.deadline).isoformat()
            except Exception as exc:
                logger.debug(
                    "Failed to parse task deadline as epoch millis for task '%s': %s",
                    getattr(t, "id", None),
                    exc,
                )
                d_iso = None

        tasks_context.append(
            {
                "title": t.title,
                "status": t.status.value,
                "estimated_min": t.estimated_minutes,
                "spent_min": t.total_time_spent,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "deadline": d_iso,
            }
        )

    prompt = f"""
    You are an expert OKR Analyst. Analyze the following Key Result data.

    KEY RESULT: "{key_result.title}"
    Description: "{key_result.description or "N/A"}"
    Progress: {key_result.current_value}/{key_result.target_value} {key_result.unit or "%"}

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

    data = _run_ai_json_prompt(prompt)
    if "error" in data:
        return {"error": data.get("error")}

    return {
        "efficiency_score": data.get("efficiency_score", 0),
        "effectiveness_score": data.get("effectiveness_score", 0),
        "overall_score": data.get("overall_score", 0),
        "advice_list": data.get("advice_list", []),
        "gap_analysis": data.get("gap_analysis", ""),
        "summary": data.get("summary", ""),
        "analyzed_at": utc_now().isoformat(),
    }


def analyze_objective(
    objective: Objective, key_results: List[KeyResult], all_tasks: List[Task]
) -> Dict[str, Any]:
    """
    Comprehensive analysis of an Objective including all its Key Results.
    Aggregates context as specified in the implementation plan.
    """
    # Build aggregated context
    context = build_analysis_context(objective, key_results, all_tasks)

    # Calculate additional metrics
    total_estimated = sum(t.estimated_minutes for t in all_tasks)
    efficiency_ratio = (
        (context.total_minutes_spent / total_estimated * 100)
        if total_estimated > 0
        else 0
    )
    completion_rate = (
        (context.completed_tasks / context.tasks_count * 100)
        if context.tasks_count > 0
        else 0
    )

    # KR details
    kr_details = []
    for kr in key_results:
        progress_pct = (
            (kr.current_value / kr.target_value * 100) if kr.target_value > 0 else 0
        )
        kr_details.append(
            {
                "title": kr.title,
                "progress": f"{kr.current_value}/{kr.target_value} {kr.unit or '%'}",
                "progress_pct": round(progress_pct, 1),
            }
        )

    prompt = f"""
    You are an expert Strategic OKR Analyst.

    OBJECTIVE: "{objective.title}"
    Description: "{objective.description or "N/A"}"

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

    data = _run_ai_json_prompt(prompt)
    if "error" in data:
        return {"error": data.get("error")}

    return {
        "efficiency_score": data.get("efficiency_score", 0),
        "effectiveness_score": data.get("effectiveness_score", 0),
        "advice_list": data.get("advice_list", []),
        "risk_factors": data.get("risk_factors", []),
        "summary": data.get("summary", ""),
        "analyzed_at": utc_now().isoformat(),
    }


# =============================================================================
# LEGACY DICT-BASED FUNCTIONS (Migrated from services/gemini.py)
# These work with JSON node dictionaries used in app.py
# =============================================================================


def analyze_node(
    node_id: int,
    node_type: Optional[str] = "KEY_RESULT",
    actor_username: Optional[str] = None,
):
    """
    Analyze a node (typically a Key Result) by fetching its data directly from SQL.
    Replaced legacy dictionary-based version for better performance and consistency.
    """
    from src.crud import get_node

    node_type_upper = str(node_type or "KEY_RESULT").upper()

    # Fetch node with all relationships for context (RBAC-aware when actor is provided)
    try:
        node = get_node(node_id, node_type_upper, actor_username=actor_username)
    except PermissionError as exc:
        return {"error": str(exc)}
    if not node:
        return {"error": f"Node {node_id} ({node_type_upper}) not found"}

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
    current_snapshot = {
        "title": node.title,
        "metrics": {
            "target": getattr(node, "target_value", 100.0),
            "current": getattr(node, "current_value", 0.0),
            "progress": getattr(node, "progress", 0),
        },
        "scope": [],
    }

    children_text = ""
    for child in children:
        c_type = child.__tablename__.upper()
        c_title = child.title
        c_desc = child.description or ""
        c_progress = child.progress or 0
        c_status = "DONE" if c_progress == 100 else "IN PROGRESS"

        # Total time spent on this child
        c_time = getattr(child, "total_time_spent", 0)

        # Add to snapshot
        current_snapshot["scope"].append(
            {"type": c_type, "title": c_title, "progress": c_progress}
        )

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
                summaries = [
                    log_row.summary
                    for log_row in recent_logs
                    if getattr(log_row, "summary", None)
                ]
                if summaries:
                    work_summ_text = "\n  Recent Work: " + "; ".join(summaries)
            except Exception as exc:
                logger.debug(
                    "Failed to load recent worklog summaries for child '%s': %s",
                    getattr(child, "id", None),
                    exc,
                )

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
    
    Target Node ({node_type_upper}): "{node.title}"
    Description: "{node.description or "N/A"}"
    
    CURRENT STATE:
    - Target: {current_snapshot["metrics"]["target"]}
    - Current: {current_snapshot["metrics"]["current"]}
    - Progress: {current_snapshot["metrics"]["progress"]}%
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


def generate_weekly_summary(
    username: str, start_date_str: str, end_date_str: str, stats: dict
) -> dict:
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
    prompt = f"""
    You are an Executive Assistant drafting a Weekly Work Report for {username}.
    Period: {start_date_str} to {end_date_str}
    
    === WORK STATISTICS ===
    - Total Time: {stats.get("total_minutes", 0) // 60}h {stats.get("total_minutes", 0) % 60}m
    - Tasks Completed: {stats.get("tasks_completed", 0)}
    - KRs Progressed: {stats.get("krs_updated", 0)}
    
    === KEY ACHIEVEMENTS (Completed Tasks) ===
    {json.dumps(stats.get("key_achievements", []), indent=2, ensure_ascii=False)}
    
    === TIME BY OBJECTIVE ===
    {json.dumps(stats.get("objectives_text", []), indent=2, ensure_ascii=False)}
    
    === DETAILED WORK LOGS ===
    {stats.get("work_logs_text", "No detailed logs.")}
    
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

    return _run_ai_json_prompt(prompt)


def suggest_critical_task(
    task_candidates: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Ask configured AI provider to pick the single most critical task.

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

    data = _run_ai_json_prompt(prompt)
    if "error" in data:
        return {"error": data.get("error")}

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
    except Exception as exc:
        logger.debug("Failed to parse AI confidence '%s': %s", confidence_val, exc)
        confidence = None

    return {
        "task_ref": selected_ref["task_ref"],
        "reason": reason
        or "AI marked this as the most urgent and important next step.",
        "confidence": confidence,
    }


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

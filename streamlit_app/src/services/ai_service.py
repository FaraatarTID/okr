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
            "spent_min": t.total_time_spent
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
            "analyzed_at": datetime.utcnow().isoformat()
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
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}



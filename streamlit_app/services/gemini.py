import os
import json
from google import genai
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

def get_api_key():
    # Priority: Streamlit Secrets > Environment Variables
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return os.getenv("VITE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

def analyze_node(node_id, all_nodes):
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}

    node = all_nodes.get(node_id)
    if not node:
        return {"error": "Node not found"}

    children = [all_nodes[cid] for cid in node.get("children", []) if cid in all_nodes]
    
    # Prepare current snapshot for storage
    current_snapshot = {
        "title": node.get("title"),
        "metrics": {
            "target": node.get("target_value", 100.0),
            "current": node.get("current_value", 0.0),
            "progress": node.get("progress", 0)
        },
        "scope": []
    }
    
    children_text = ""
    for child in children:
        c_type = child.get("type", "ITEM").upper()
        c_title = child.get("title", "Untitled")
        c_desc = child.get("description", "")
        c_progress = child.get("progress", 0)
        c_status = "DONE" if c_progress == 100 else "IN PROGRESS"
        c_time = child.get("timeSpent", 0)
        
        # Add to snapshot
        current_snapshot["scope"].append({
            "type": c_type,
            "title": c_title,
            "progress": c_progress
        })
        
        # Get recent work history
        work_summ_text = ""
        if "workLog" in child and child["workLog"]:
            # Last 5 summaries
            recent_logs = sorted(child["workLog"], key=lambda x: x.get("endedAt", 0), reverse=True)[:5]
            summaries = [l.get("summary") for l in recent_logs if l.get("summary")]
            if summaries:
                work_summ_text = "\n  Recent Work: " + "; ".join(summaries)
        
        # Deadline information
        deadline_info = ""
        if child.get("deadline"):
            from utils.deadline_utils import get_deadline_status, get_days_remaining
            _, status_label, health = get_deadline_status(child)
            days = get_days_remaining(child.get("deadline"))
            deadline_info = f"\n  Deadline: {status_label} ({days} days remaining, health: {health}%)"
        
        children_text += f"- [{c_type}] {c_title}\n  Description: {c_desc}\n  Status: {c_status} ({c_progress}%)\n  Time: {c_time}m{deadline_info}{work_summ_text}\n"

    prompt = f"""
    You are an expert Strategic OKR Analyst. 
    
    Target Key Result: "{node.get('title')}"
    Description: "{node.get('description', 'N/A')}"
    
    CURRENT STATE:
    - Target: {current_snapshot['metrics']['target']} {node.get('unit', '%')}
    - Current: {current_snapshot['metrics']['current']} {node.get('unit', '%')}
    - Progress: {current_snapshot['metrics']['progress']}%
    - Defined Scope:
    {children_text}
    
    ---
    PREVIOUS STATE SNAPSHOT (Captured during last audit):
    {json.dumps(node.get('geminiLastSnapshot', {}), indent=2, ensure_ascii=False) if node.get('geminiLastSnapshot') else "N/A (First Run)"}
    
    PREVIOUS ANALYSIS RESULTS:
    {json.dumps(node.get('geminiAnalysis', {}), indent=2, ensure_ascii=False) if node.get('geminiAnalysis') else "N/A (First Run)"}
    
    ---
    YOUR OBJECTIVE:
    Conduct a rigorous audit of this Key Result. You must evaluate FOUR dimensions:
    
    0. DEADLINE HEALTH (Urgency Analysis):
       - Review all tasks with deadlines. Flag any that are "At Risk" or "Overdue".
       - Tasks that are overdue without 100% completion are critical failures.
       - If a task's deadline has passed but progress < 100%, this is a RED FLAG.
       - Consider deadline pressure in your overall recommendations and urgency of the gap analysis.
    
    1. PROGRESSION & DELTA CHECK (The "Memory" Step):
       - Compare the "CURRENT STATE" with the "PREVIOUS STATE SNAPSHOT".
       - Identify what has changed: Have new tasks been added? Has the metric value increased?
       - If the user addressed a gap you identified in the "PREVIOUS ANALYSIS", you MUST start your summary by acknowledging it.
       - Increment scores if previously identified gaps have been filled.
    
    2. EFFICIENCY (Completeness of Scope): 
       - Look at the "Current Defined Scope". Is this work actually sufficient to achieve the Key Result 100%?
       - Note: In this system, "Initiatives" are tags for Key Results, and "Tasks" are the direct actionable level under a Key Result.
       - If tasks are missing, the Efficiency score must be lowered.
       - Efficiency Score = (Work Done) / (Total Work Required including missing tasks).
    
    3. EFFECTIVENESS (Quality of Strategy):
       - Are the defined tasks the *right* things to do? Are the descriptions and methods sound?
       - A high effectiveness score means the strategy is smart and likely to succeed.
    
    4. PROGRESS ESTIMATION (The "New Value" Step):
       - Calculate a "suggested_current_value" for this Key Result.
       - Base this on the progress of defined tasks AND the target metric.
       - If tasks represent 100% of the work required (High Efficiency) and are 50% done, the suggested value should be roughly 50% of the target.
       - If Efficiency is low, the suggestion should be conservative.
    
    REQUIRED OUTPUT (JSON):
    {
        "efficiency_score": <number 0-100>,
        "effectiveness_score": <number 0-100>,
        "overall_score": <number 0-100 input weighted average>,
        "suggested_current_value": <number, AI estimation of current progress in the unit of the KR>,
        "deadline_warnings": ["<Task X is overdue by N days>", "<Task Y is at risk>", ...],
        "gap_analysis": "<Concise explanation of what is missing to reach 100% fulfillment (in the SAME language as the Key Result Title)>",
        "quality_assessment": "<Concise critique of the current tasks' quality (in the SAME language as the Key Result Title)>",
        "proposed_tasks": ["<New Task 1>", "<New Task 2>", ...],
        "summary": "<2 sentence executive summary (in the SAME language as the Key Result Title)>"
    }
    
    IMPORTANT: Detect the language of the Key Result Title and Description. All generated text (gap_analysis, quality_assessment, summary, proposed_tasks) MUST be in that SAME language.
    In your summary and gap analysis, make specific reference to the "Current Metric Progress" numbers (e.g., "At 20% progress", "800 units remaining to target") to show the analysis is data-driven.
    
    Provide strictly valid JSON.
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
        
        # Validate response
        if not response.text:
            return {"error": "Gemini returned an empty response. This might be due to safety filters or service issues."}
        
        # Try to clean the response if it contains markdown code blocks
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        data = json.loads(raw_text)
        
        return {
            "analysis": {
                "efficiency_score": data.get("efficiency_score", 0),
                "effectiveness_score": data.get("effectiveness_score", 0),
                "overall_score": data.get("overall_score", 0),
                "suggested_current_value": data.get("suggested_current_value", node.get("current_value", 0.0)),
                "deadline_warnings": data.get("deadline_warnings", []),
                "gap_analysis": data.get("gap_analysis", ""),
                "quality_assessment": data.get("quality_assessment", ""),
                "proposed_tasks": data.get("proposed_tasks", []),
                "summary": data.get("summary", "")
            },
            "snapshot": current_snapshot
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
    
    1. 🚀 PRODUCTIVITY PULSE
       - Is the team making consistent progress?
       - Are tasks being completed or stalling?
       - Score 0-100 based on activity and completion rates.
    
    2. ⏰ DEADLINE DISCIPLINE
       - How well does the team manage deadlines?
       - Are there patterns of procrastination or consistent delivery?
       - Critical if overdue > 0.
    
    3. 🎯 STRATEGIC ALIGNMENT
       - Are people working on the RIGHT things?
       - Is work concentrated on high-priority Key Results?
       - Consider confidence scores and at-risk KRs.
    
    4. ⚖️ WORKLOAD BALANCE
       - Is work distributed fairly across the team?
       - Are some members overloaded while others are idle?
       - Look at task counts and progress variations.
    
    5. 📈 MOMENTUM & MORALE
       - Is the team accelerating or slowing down?
       - Based on data hygiene and update frequency.
       - High hygiene = engaged team.
    
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
            "deadline_discipline": {{
                "score": <0-100>,
                "status": "<🟢 | 🟡 | 🔴>",
                "insight": "<observation>",
                "action": "<action>"
            }},
            "strategic_alignment": {{
                "score": <0-100>,
                "status": "<🟢 | 🟡 | 🔴>",
                "insight": "<observation>",
                "action": "<action>"
            }},
            "workload_balance": {{
                "score": <0-100>,
                "status": "<🟢 | 🟡 | 🔴>",
                "insight": "<observation>",
                "action": "<action>"
            }},
            "momentum": {{
                "score": <0-100>,
                "status": "<🟢 | 🟡 | 🔴>",
                "insight": "<observation>",
                "action": "<action>"
            }}
        }},
        
        "top_priorities": [
            "<#1 thing the manager should focus on this week>",
            "<#2 priority>",
            "<#3 priority>"
        ],
        
        "quick_wins": [
            "<Easy fix that will show immediate results>",
            "<Another quick win>"
        ],
        
        "watch_out": "<One critical risk to monitor>"
    }}
    
    COACHING STYLE:
    - Be direct but constructive
    - Use the manager's perspective ("Your team...", "Consider...")
    - Make recommendations SPECIFIC and ACTIONABLE
    - If data shows problems, don't sugarcoat - but offer solutions
    - Detect language from the data and respond in the SAME language
    
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

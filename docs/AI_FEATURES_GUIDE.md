# AI Features Guide: Mastering the Intelligence Layer

Documentation HQ: [README](../README.md)

This guide explains the AI capabilities embedded in the OKR application and how to use them effectively. The system uses advanced Large Language Models (LLMs) to act as an analyst, coach, and assistant.

---

## 1. Core AI Features

### 🔍 Key Result Analyst (Efficiency vs. Effectiveness)

**What it does:**
Instead of just showing a progress bar, the AI analyzes _how_ you are achieving it. It looks at your Tasks, Time Spent, and Estimates.

**The Scores:**

- **Efficiency Score (Time)**: measures how well you stick to your time estimates.
  - _Low Score?_ You might be underestimating tasks or getting distracted.
- **Effectiveness Score (Impact)**: measures if your completed tasks are actually driving the Key Result progress.
  - _Low Score?_ You are finishing tasks, but the KR isn't moving. You might be working on the wrong things.

**How to use:**

1. Open any **Key Result**.
2. Click the **"Analyze"** or **"Magic"** button.
3. Review the **Advice List** for specific actions to improve.

### 🧠 Strategic Objective Review

**What it does:**
This is a high-level strategic audit. It looks at an Objective and all its contained Key Results and Tasks to answer: _"Is this strategy sound?"_

**Outputs:**

- **Risk Assessment**: Identifies if the defined KRs are sufficient to meet the Objective.
- **Scope Gap**: Warns if you simply don't have enough tasks planned to hit the targets.

### 👨‍🏫 Team Performance Coach (For Managers)

**What it does:**
Acts as a virtual Chief of Staff for managers. It aggregates data from all team members to find patterns humans might miss.

**Dimensions Analyzed:**

1. **Productivity Pulse**: Is the team accelerating or slowing down?
2. **Deadline Discipline**: Are tasks consistently overdue?
3. **Burnout Risk**: Is work distributed unevenly?

**How to use:**

- Navigate to the **Leadership Dashboard**.
- The AI Coach will provide a "Health Grade" (A-F) and 3 top priorities for you to focus on this week.

### 📝 Smart Weekly Summary

**What it does:**
Drafts your "Weekly Report" for you. It reads through all your completed tasks, work logs, and check-ins to write a professional narrative.

**Why use it:**

- Saves time on administrative reporting.
- Ensures you don't forget to mention small but important wins.
- **Context Aware**: It detects the language of your tasks (English or Persian) and writes the summary in the same language.

### 🎯 AI Suggested Next (Prioritization)

**What it does:**
When you don't know what to do next, the AI picks the single most "Critical" task based on:

- Urgency (Deadlines)
- Importance (Parent KR priority)
- Momentum (Recent work)

---

## 2. Best Practices for Best Results

The AI is only as smart as the data you give it. Follow these rules to get "Hallucination-Free" high-quality advice:

### ✅ Do: Write Contextual Titles

- **Bad:** "Fix bug"
- **Good:** "Fix race condition in progress rollup logic"
  _Why? The AI needs to understand the complexity to judge efficiency._

### ✅ Do: Use Estimates

- Always set `Estimated Minutes` on tasks.
- The AI uses this to calculate your **Efficiency Score**.
- If you don't estimate, the AI assumes "0 estimation" and your efficiency score will be inaccurate.

### ✅ Do: Update Progress Regularly

- Don't wait until Friday to update everything.
- Real-time updates help the **Suggested Next** engine give you relevant recommendations.

### ❌ Don't: Leave "orphaned" tasks

- Ensure every task is linked to a Key Result.
- Orphaned tasks confuse the Strategic Review agent.

---

## 3. Privacy & Security

- **Data Safety**: We use enterprise-grade APIs. Your data is processed for analysis and then discarded; it is not used to train public models.
- **Human in the Loop**: AI suggestions are just _suggestions_. You always have the final say within the system.
- **Transparency**: Every AI insight comes with a "Why?" or detailed breakdown. We don't do "Black Box" magic.

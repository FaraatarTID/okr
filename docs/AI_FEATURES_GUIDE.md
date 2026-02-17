# AI Features Guide: The Strategic Intelligence Anthology

Documentation HQ: [README](../README.md)

This guide provides authoritative instructions on the Intelligence Layer, strictly aligned with the `RAG` architecture, `ai_service.py` logic, and the literal AI tools available in the UI.

---

## 1. Technical Foundation: The RAG Architecture

The AI in this system operates on **Retrieval-Augmented Generation (RAG)** as implemented in the `src/services/` directory.

### A) Semantic Integrity (Zero Hallucination)

- **Context Retrieval**: When you request an analysis, the AI service fetches the literal text from your `KeyResult` and related `Task` records. It is architecturally prevented from generating content outside this retrieved context.
- **Literal Citations**: Strategic reports include citations linked to specific `Node ID`s. This allows you to machine-verify any AI claim against the original database entry.

### B) Vector-Based Understanding

Your goals and tasks are converted into mathematical signatures (Vectors) in the background.

- **Outcome**: This allows the **Suggested Next** tool to identify semantically related work even if the wording differs between levels of the hierarchy.

---

## 2. Literal AI Capabilities (Code-Defined Tools)

The AI features are grouped into three primary functional areas:

### A) The Magic Wand (Analysis & Decomposition)

Located in the **Inspector** (right sidebar), this tool interacts with the `KeyResult` and `Objective` models via the `GeminiService`.

- **Capability**: Analyze metadata, recommend tactical tasks, and evaluate the clarity of your objective naming.
- **Workflow**: Click a node -> Open Inspector -> Click Magic Wand.

### B) Suggested Next (Priority Engine)

Located in the **Top Header**, this tool uses the `get_suggested_next` logic in `crud.py`.

- **Ranking Logic**: It ranks tasks based on:
  1. Active running session.
  2. `Needs care` urgency (Progress < 40% or Overdue).
  3. Ownership and actionability.
  4. Current progress levels.

### C) Effectiveness Scoring (Precision Banding)

Stored in the `KeyResult.gemini_analysis` field.

- **Capability**: After a `WorkLog` session is completed via the **Commit Spotlight**, the AI evaluates the description of the work against the parent goal's strategic intent.
- **Metric**: Scores are mapped to a precision band:
  - **0.0 - 0.3**: Failure/Mismatch ( Effort did not move the needle).
  - **0.7 - 1.0**: Success/Impact (Effort directly contributed to KR metrics).
- **Lifecycle Awareness**: The AI Progress Sync strictly **skips** nodes in the `DRAFT` state. This prevents work-in-progress from polluting the organizational intelligence layer.

---

## 3. The 90-Day AI Assistance Lifecycle

### Phase 1: The Architect (Weeks 1-2)

- **Tool**: Magic Wand.
- **Action**: Use the AI to decompose high-level `Objectives` into quantitative `Key Results` and initial `Task` lists.

### Phase 2: The Tactical Coach (Weeks 3-10)

- **Tool**: Suggested Next & Effectiveness Score.
- **Action**: Use the priority engine daily to decide focus. Review effectiveness scores weekly to identify if effort is being wasted on "Low Value" admin work.

### Phase 3: The Strategic Analyst (Weeks 11-13)

- **Tool**: Strategic Gap Analysis.
- **Action**: The AI scans the `Goal` tree to find "Ghost Goals"—objectives with 0% progress but high strategic priority. Use this to re-allocate final sprint resources.

---

## 4. Prompt Engineering for the Magic Wand

To get higher-quality outputs from the Magic Wand, use terminal-style specificity:

- **Quantification Request**: _"Analyze this KR. Suggest 3 quantitative pillars I should track to prove success."_
- **Blocker Diagnosis**: _"Identify the primary technical risk in this task list based on the current progress lag."_
- **Narrative Synthesis**: _"Summarize the last 4 weeks of task logs into a 3-sentence achievement report for leadership."_

---

## 5. Security & Isolation (Ethics of Intelligence)

- **Transit Security**: All requests to the Gemini engine are encrypted via TLS 1.3.
- **Non-Training Policy**: Your `objective` and `task` metadata is never used to train public models.
- **Privacy Gating**: The AI respects `RBAC`. It cannot retrieve content from a `Goal` or `Library` document that the current `user_id` does not have permission to view.

---

_The goal is verifiable transparency. The AI suggests, but the human decides._

---

## 6. The Intelligence Mentor: From AI Tools to Expert Insight

### A) The "Master Prompter" Cookbook (Magic Wand Scenarios)

To get high-applicability results from the **Magic Wand**, use these 3 specific prompt patterns:

1. **The Tactical Breakdown**: _"I am blocked by [Technical Detail]. Decompose this Key Result into 5 micro-tasks that bypass this bottleneck using existing resources."_
2. **The Strategic Alignment Check**: _"Compare this KR's title with the parent Objective. Identify any semantic gaps where my current tasks aren't actually contributing to the target metric."_
3. **The Executive Summary**: _"Synthesize my last 10 WorkLogs. Create a 3-bullet accomplishment list formatted for a direct manager who values [Efficiency/Innovation/Reliability]."_

### B) The Trust-Verify Protocol (Audit Discipline)

The AI uses **RAG** (Retrieval-Augmented Generation), meaning it only knows what is in the database.

- **The Protocol**: Whenever the AI provides a "Strategic Gap Analysis," click the linked **Node ID**. Verify if the cited `Goal` or `Task` actually supports the claim.
- **Human Oversight**: If the AI suggests a task that is technically impossible (hallucination risk), use the **Inspector** to manually edit the node. Your manual correction "trains" the semantic context for the next cycle.

### C) The AI Feedback Loop: "Refining Your Habit"

Success in this platform is measured by the **Effectiveness Score** (stored in `gemini_analysis`).

1. **The Gap Discovery**: Look for scores below 5/10. This signals a "Focus Mismatch"—your logged work doesn't match your strategic goal.
2. **The Adjustment**: Use the **Suggested Next** tool to purposefully pick a task that the AI identifies as "High Impact."
3. **The Result**: As your scores move toward 9/10, your visual presence in the **Leadership Dashboard** shifts from a "Busy-work" profile to an "Elite Execution" profile.

### D) Pro-Tips for AI Partnership

- **Task Naming Mastery**: The AI is only as smart as your task titles. Use a [Verb] + [Subject] + [Outcome] format (e.g., _"Optimized DB Index to reduce Atlas latency"_).
- **The "Invisible" Analyst**: Remember that the AI is constantly ranking your tasks in the background. Every `WorkLog` summary you write is used to refine the **Suggested Next** accuracy.
- **Context is King**: If the AI is giving vague advice, use the **Inspector** to add more depth to the `Description` field of your parent Goal.

---

_The goal is verifiable transparency. The AI suggests, but the human decides._

---

## 7. Epistemic Foundations: The Trust-Verify Architecture

### A) RAG Logic vs. Hallucination

Unlike generic chatbots, this system uses **Retrieval-Augmented Generation (RAG)**.

- **The Evidence Layer**: Before answering, the AI queries the **Vector Store** for literal `WorkLogs`, `KeyResult` descriptions, and `Objective` titles. It is anchored to your specific organizational data.
- **Hallucination Safety**: If the AI cannot find a citation in your database, it is instructed to express "Epistemic Humility" (e.g., _"I don't have enough data on your previous cycle to answer that"_).
- **The Citation Standard**: Every summary produced by the **AI Weekly Summary** tool is machine-audited against the database. If you see a claim without a `Node ID` or `log_id` reference, treat it as a suggestion that requires human verification.

### B) Organizational Memory & Vector Knowledge

Every time you edit a task or write a clear `WorkLog`, you are "training" the organizational memory.

- **The Feedback Loop**: Your manual corrections in the **Inspector** are indexed by the **Semantic Engine**. Over time, the **Suggested Next** tool becomes hyper-accurate to your specific departmental jargon and business logic.
- **Long-Term Context**: Because the system tracks multiple `Cycles`, it can identify "Strategic Drift" across years, something no manual spreadsheet can achieve.

---

## 8. The Intelligence Lifecycle (The 13-Week AI Evolution)

The AI's role shifts dynamically as you move through the 90-day program.

### Phase 1: The Tactical Architect (Weeks 1-2)

In the planning phase, the AI acts as a **Structural Consultant**.

- **Role**: Helping you break "Vague Dreams" into "Quantitative Results."
- **Key Tool**: The **Magic Wand** (Decomposition). Use it to ensure your KRs are measurable and support the parent Objective.

### Phase 2: The High-Velocity Coach (Weeks 3-10)

During the middle of the quarter, the AI shifts to **Habit & Momentum Coaching**.

- **Role**: Analyzing your execution speed and focus alignment.
- **Key Tool**: The **Effectiveness Score**. Look for the AI's "Strategic Gap Analysis" to find tasks that are absorbing time without moving the KR percentage.

### Phase 3: The Strategic Auditor (Weeks 11-13)

As the quarter ends, the AI becomes an **Impact Analyst**.

- **Role**: Synthesizing thousands of data points into a high-level "Executive Narrative."
- **Key Tool**: **Leadership Dashboard** summaries. Use the AI to generate a "Lessons Learned" report that identifies why certain branches "failed" and others "succeeded."

---

## 9. Security, Privacy & Epistemic Ethics

- **Zero-Trust Access**: The AI is strictly bound by your user role. A `Member` cannot ask the AI to summarize the `Strategic Dashboard` of another department.
- **The Dialogue Starter**: Always remember that AI analysis is a **Dialogue Starter**, not a Final Verdict. Use the AI to identity the "Question," but use your human expertise to provide the "Answer."
- **Data Sovereignty**: Your organizational data stays within your private `Vector Store`. It is not used to train global models.

---

## 10. The AI Scrum Master Masterclass: Predictive Velocity

In an Agile environment, the AI is more than a search engine; it is your **Automated Scrum Master**. It analyzes your "Velocity" (the speed at which you complete tasks) to help you plan your next sprint.

### A) Understanding Predictive Velocity (Step-by-Step)

1. **The Data Intake**: Every time you stop the **Timer**, the system records the `total_time_spent` against the `estimated_minutes`.
2. **The Calculation**: The AI calculates the "Fudge Factor" (the difference between your estimates and reality).
3. **The Prediction**: In the **Suggested Next** list, the AI ranks tasks not just by priority, but by "Likelihood of Completion." It prioritizes tasks that fit within your typical high-focus windows.

### B) Using the AI for Sprint Retrospectives (Step-by-Step)

During your bi-weekly retrospective, invite the AI to the table:

1. **The Prompt**: Use the **Magic Wand** on your parent Objective. Ask: _"Analyze my velocity for the last 14 days. Identify the top 3 'Time Thrives' (tasks that went faster than planned) and top 3 'Time Sinks' (unexpected bottlenecks)."_
2. **The Insight**: The AI will provide a **Semantic Analysis** of your road-blocks. If it identifies a pattern (e.g., _"You are consistently slower on UI-related tasks"_), use this to adjust your estimates for the next sprint.
3. **The Action**: Click **Refine Objective**. Have the AI rewrite your child tasks to bypass the Sink-holes it identified.

### C) AI-Led Refinement masterclass

Don't let your backlog grow stale. Every Monday morning:

1. **Step 1**: Open the **Inspector** for an objective with >10 children nodes.
2. **Step 2**: Click the **Decomposition** tool. Ask: _"Identify 3 redundant tasks in this backlog that do not directly move the 'current_value' metrics."_
3. **Step 3**: Archive the suggested nodes. This creates a "Lean Backlog" that keeps your Atlas Map focused on results, not busy-work.

---

_Augment your intent. Execute with intelligence. Grounded in RAG, refined by humans._

---

## 11. AI Integrity & Calibration Masterclass

This section explains how to audit the AI's internal logic and "train" it to match your organization's specific tactical style.

### A) RAG & Citation Auditing (Step-by-Step)

Trust, but verify. The AI uses **Retrieval-Augmented Generation (RAG)** to ensure its reports are grounded in literal evidence.

1. **Step 1: The Citation Source**: Whenever the AI provides a summary of a `Key Result`, look for the numeric citations (e.g., `[1]`).
2. **Step 2: The Deep-Link**: Click on the citation or the **Node ID**.
3. **Step 3: Verification**: Open the **Inspector** for that node and compare the `WorkLog` entries with the AI's summary. If the AI claimed "High Velocity" but the logs show "Low Duration," use the **Notes** field to provide the AI with corrective context.

### B) Vector Store Synchronization (Technical Check)

Your AI's "Intelligence" is only as fresh as its **Vector Store**.

1. **The Sync Indicator**: Look at the **Sync Status** in the header. If the last sync was >24 hours ago, your AI is "Hallucinating from the Past."
2. **The Manual Force**: Go to the Admin Panel and trigger a **Vector Re-Index**.
3. **Technical Outcome**: This forces the `VectorService` to convert every word in your database into multi-dimensional coordinates (Embeddings). This enables the AI to "See" connections between distant tasks that you might have missed.

### C) AI-Human Calibration (Step-by-Step)

The AI has a "Cold Start" problem; it doesn't know your company's unique culture. Use these steps to "Teach" it.

1. **The Context Injection**: Every 30 days, re-open your top-level `Objective`.
2. **The Step**: Update the `description` with a "Style Paragraph" (e.g., _"In this department, we prioritize security over speed. Any time sink related to security audits is actually a 'Time Thrive'."_)
3. **The Result**: The AI will read this new description during its next **Effectiveness Scoring** run. You will see your scores rise as the AI aligns its "Values" with yours.

---

_The Expert Analyst. Augmenting human intelligence with technical precision._

---

---

## 12. Master’s Playbook: Epistemic Defense & Strategic Auditing

This final section transforms you from a consumer of AI insights into an **Architect of AI Strategy**. It focuses on the high-level defense mechanisms needed to maintain absolute organizational truth.

### A) The Epistemic Defense (Anti-Hallucination)

Even the best RAG systems can be misinterpreted. Follow this protocol for high-stakes quarterly reporting.

1. **Adversarial Verification**: Whenever the AI generates a "Strategic Summary," intentionally ask it to find evidence _against_ its own claim.
   - _The Step_: Use the **Inspector** Magic Wand. Ask: _"Identify any work log that contradicts this high-velocity claim."_
2. **The Grounding Loop**: If the AI cannot find contradictory evidence, check the **Citation Logic** for the source document's `last_modified` date. If the source is older than the cycle, the AI is likely projecting past success onto current failure.

### B) Prompt Engineering for Enterprise Leaders

Professional prompting is about reducing ambiguity to zero. Use this 3-step "Master Template" for your quarterly audits.

1. **Step 1: The Persona**: Start with: _"Act as an Adversarial Strategy Auditor with deep access to the OKR WorkLogs."_
2. **Step 2: The Constraint**: Add: _"Evaluate the following Key Result. Ignore qualitative descriptions. Focus only on the ratio of `duration` to `current_value` movement."_
3. **Step 3: The Deliverable**: End with: _"Identify the single biggest logical fallacy in the current 90-day plan that could lead to missing the end-of-quarter target."_

### C) AI-Led Organizational Resilience

Use the AI as a continuous watchdog for the organization’s health.

- **The Strategic Alignment Audit**: Every 30 days, ask the AI to perform a "Vector Alignment Check" between the CEO's root Objective and every "Member" task.
- **The Outcome**: Use the AI's list of "Low-Alignment Tasks" to initiate the **Backlog Grooming** protocol in the Admin Guide.

---

_The Master Strategist. Defending the truth. Auditing the future._

---

_Augment your intent. Execute with intelligence. Grounded in RAG, refined by humans. Mastered by you._

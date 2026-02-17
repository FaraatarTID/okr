# OKR Lifecycle Guide

This document outlines the lifecycle of Objectives and Key Results (OKRs) in the Faraatar OKR system. The lifecycle ensures that OKRs follow a structured path from ideation to completion.

## 🔄 The Lifecycle States

Each OKR node (Objective or Key Result) moves through four distinct states.

### 1. 📝 DRAFT

- **Purpose**: Initial planning and brainstorming phase.
- **Behavior**: Progress is not yet "official." Draft OKRs are visually distinct (Grey pulse in Atlas).
- **Best Practice**: Use this state while you are still negotiating targets or defining the scope with your team.

### 2. 🚀 ACTIVE

- **Purpose**: Implementation phase where progress is actively tracked.
- **Behavior**: These OKRs represent the current commitments for the cycle. Progress updates affect health scores and analytics.
- **Constraint**: An Objective **cannot** be activated unless it has at least one Key Result defined.

### 3. ⚖️ GRADING

- **Purpose**: End-of-cycle review and scoring adjustment.
- **Behavior**: Nodes in this state are flagged for attention (Orange/Risk) to remind owners to perform a **Final Reflection**.
- **Activities**: Owners should review the final achievement, adjust scores if necessary, and write their learning insights in the "Final Reflection" field.

### 4. 📁 ARCHIVED

- **Purpose**: Historical record.
- **Behavior**: OKRs are closed and read-only. They are moved to a neutral "On Track" visual state to signify completion.
- **Recovery**: If a mistake was made, nodes can be moved back to ACTIVE from ARCHIVED.

---

## 🌊 Cascade Logic

To maintain consistency and reduce manual overhead, the system implements **State Cascading**:

- When you change the state of an **Objective**, all its child **Key Results** are automatically updated to the same state.
- **DRAFT Exclusion**: Important! Nodes in the `DRAFT` state are **excluded** from all progress rollups. Your Goal progress will not change until the Objectives are moved to `ACTIVE`.

---

## 🔗 Organizational Alignment (DAG Overlay)

Beyond the parent-child hierarchy (Goal -> Objective -> KR), the system supports **Cross-Team Alignment**. This allows Objectives to support or relate to each other horizontally or vertically across different goals.

### Vertical & Horizontal Links

In the Objective Inspector, you can manage these relationships:

- **Supports (Parent)**: This objective contributes to the success of a higher-level or peer objective.
- **Supported by (Child)**: Other objectives contribute to this one.

### 🛡️ Directed Acyclic Graph (DAG) Enforcement

To prevent illogical "circular dependencies" (e.g., A supports B, B supports C, and C supports A), the system uses a **DAG Enforcement Engine**.

- Any link that would create a cycle is **automatically blocked**.
- This ensures a clear, traceable path of accountability throughout the organization.

---

## 🎯 Scoring & Progress Modes

Objectives support two distinct modes of progress calculation, configurable in the Inspector:

### 1. Unweighted (Default)

- **Logic**: All Key Results contribute equally to the Objective's progress.
- **Use Case**: When every KR is of equal tactical importance.

### 2. Weighted

- **Logic**: Each Key Result is assigned a `Weight` (e.g., 2.0 vs 1.0). Progress is calculated as a weighted average.
- **Use Case**: When specific metrics (e.g., "Revenue") are significantly more important than others (e.g., "Documentation").

---

## 💡 How to Manage These Features

1.  **Change State**: Use the "Lifecycle & Closing" section in the Inspector.
2.  **Add Alignment**: Use the "Organizational Alignment" section in the Objective Inspector to link to other objectives.
3.  **Set Weights**: In the KR section of the Inspector, adjust the "Weight" slider.
4.  **Set Score Mode**: In the Objective section of the Inspector, toggle between "Weighted" and "Unweighted".

---

## 📝 Final Reflection

When moving a node to `GRADING` or `ARCHIVED`, use the **Final Reflection** field to document:

- What went well?
- What obstacles were encountered?
- What are the key learnings for the next cycle?

This data is preserved as organizational memory and is indexed by the AI for future strategic analysis.

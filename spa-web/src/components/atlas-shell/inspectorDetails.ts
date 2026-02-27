"use client";

import type {
  AtlasGoalSnapshot,
  AtlasIndexNode,
  AtlasKeyResultSnapshot,
  AtlasObjectiveSnapshot,
  AtlasTaskSnapshot,
} from "@/lib/atlas";

type InspectorDetailFormatters = {
  formatOptionalDate: (value: unknown) => string;
  formatOptionalNumber: (value: unknown) => string;
};

export function selectedNodeDetails(
  meta: AtlasIndexNode,
  { formatOptionalDate, formatOptionalNumber }: InspectorDetailFormatters,
): Array<[string, string]> {
  if (meta.type === "TASK") {
    const task = meta.node as AtlasTaskSnapshot;
    return [
      ["Status", String(task.status || "-")],
      ["Deadline", formatOptionalDate(task.deadline)],
      ["Timer Started", formatOptionalDate(task.timer_started_at)],
      ["Total Time (min)", formatOptionalNumber(task.total_time_spent)],
      ["Assignee", task.assignee_id ? `#${task.assignee_id}` : "-"],
    ];
  }

  if (meta.type === "KEY_RESULT") {
    const keyResult = meta.node as AtlasKeyResultSnapshot;
    return [
      ["Metric Type", String(keyResult.metric_type || "-")],
      ["Start Value", formatOptionalNumber(keyResult.start_value)],
      ["Current Value", formatOptionalNumber(keyResult.current_value)],
      ["Target Value", formatOptionalNumber(keyResult.target_value)],
      ["Unit", String(keyResult.unit || "-")],
      ["AI Score", formatOptionalNumber(keyResult.ai_overall_score)],
      ["AI Deadline State", String(keyResult.ai_deadline_state || "-")],
      ["Task Count", `${(keyResult.tasks || []).length}`],
    ];
  }

  if (meta.type === "OBJECTIVE") {
    const objective = meta.node as AtlasObjectiveSnapshot;
    return [
      ["Score Mode", String(objective.score_mode || "-")],
      ["Weight", formatOptionalNumber(objective.weight)],
      ["Key Result Count", `${(objective.key_results || []).length}`],
    ];
  }

  const goal = meta.node as AtlasGoalSnapshot;
  return [
    ["Owner", meta.ownerName],
    ["Objective Count", `${(goal.objectives || []).length}`],
  ];
}

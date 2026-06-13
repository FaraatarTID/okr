import { describe, expect, it } from "vitest";

import {
  cycleDisplayLabel,
  cycleOptionLabel,
  cyclePeriodLabel,
  normalizeTaskStatus,
  parseOwnerIds,
  quarterLabel,
  timelineStatusLabel,
} from "@/components/atlas-shell/shellUiUtils";

describe("shellUiUtils", () => {
  it("parses owner-id input and validates positive integers", () => {
    expect(parseOwnerIds("")).toEqual({ value: undefined, error: "" });
    expect(parseOwnerIds("1, 2, 2, 3")).toEqual({ value: [1, 2, 3], error: "" });
    expect(parseOwnerIds("1, a")).toEqual({
      value: undefined,
      error: "Owner IDs must be comma-separated positive integers.",
    });
    expect(parseOwnerIds("0,2")).toEqual({
      value: undefined,
      error: "Owner IDs must be comma-separated positive integers.",
    });
  });

  it("builds cycle labels from dates/titles", () => {
    expect(quarterLabel("2026-01-15")).toBe("Q1-2026");
    expect(quarterLabel("bad")).toBe("");

    expect(cyclePeriodLabel({ start_date: "2026-01-01", end_date: "2026-03-31" })).toBe("Q1-2026");
    expect(cyclePeriodLabel({ start_date: "2026-01-01", end_date: "2026-07-01" })).toBe(
      "Q1-2026 to Q3-2026",
    );
    expect(cyclePeriodLabel(null)).toBe("");

    expect(cycleDisplayLabel(null)).toBe("Resolving...");
    expect(cycleDisplayLabel({ id: 5, title: "Q2 launch", start_date: null, end_date: null })).toBe(
      "Q2 launch",
    );
    expect(cycleDisplayLabel({ id: 9, title: "", start_date: null, end_date: null })).toBe("Cycle 9");
    expect(
      cycleOptionLabel({
        id: 2,
        title: "",
        start_date: "2026-01-01",
        end_date: "2026-03-31",
        is_active: true,
      }),
    ).toBe("Q1-2026 (active)");
  });

  it("normalizes task status and timeline labels", () => {
    expect(normalizeTaskStatus("in action")).toBe("IN_PROGRESS");
    expect(normalizeTaskStatus("IN PROGRESS")).toBe("IN_PROGRESS");
    expect(normalizeTaskStatus("done")).toBe("DONE");
    expect(normalizeTaskStatus("unknown")).toBe("TODO");

    expect(timelineStatusLabel("IN_PROGRESS")).toBe("In Progress");
    expect(timelineStatusLabel("DONE")).toBe("Done");
    expect(timelineStatusLabel("BLOCKED")).toBe("Blocked");
    expect(timelineStatusLabel("TODO")).toBe("Todo");
  });
});

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RitualModePanel from "@/components/atlas-shell/RitualModePanel";

function makeProps(overrides: Record<string, unknown> = {}) {
  const kr = {
    id: 5,
    title: "Improve reliability",
    progress: 42,
    current_value: 17.5,
    objective: { title: "Stabilize release flow" },
  };

  return {
    ritualStep: 1 as 1 | 2 | 3,
    setRitualStep: vi.fn(),
    cycleLabel: "Q1 2026",
    ritualKrs: [kr],
    ritualSubmittedCount: 0,
    ritualReviewLogs: [{ duration_minutes: 30 }, { duration_minutes: 45 }],
    ritualReviewExperiments: [],
    toDateShortLabel: (value: Date) => value.toISOString().slice(0, 10),
    ritualReviewRange: {
      start: new Date("2026-01-01T00:00:00.000Z"),
      end: new Date("2026-01-07T00:00:00.000Z"),
    },
    retroDraft: { content: "", sentiment: "" },
    setRetroDraft: vi.fn(),
    handleRetroCreate: vi.fn(async () => {}),
    startOfWeekIso: () => "2026-01-01",
    modeActionPending: false,
    ritualCheckInDrafts: {
      5: {
        value: "",
        confidence: "CONFIDENT" as const,
        comment: "",
        variationType: "COMMON_CAUSE" as const,
        specialCauseNote: "",
        experimentId: "",
      },
    },
    ritualExperimentsByKr: {
      5: [
        { id: 101, key_result_id: 5, hypothesis: "Reduce queue time", status: "RUNNING" as const },
        { id: 102, key_result_id: 5, hypothesis: "Tighten triage", status: "PLANNED" as const },
        { id: 103, key_result_id: 5, hypothesis: "Archive stale tasks", status: "DECIDED" as const, decision: "ADOPT" as const },
      ],
    },
    ritualExperimentDrafts: {
      5: {
        hypothesis: "",
        changeDescription: "",
        expectedEffectDirection: "" as const,
        expectedEffectSize: "",
      },
    },
    ritualExperimentFormOpen: { 5: true },
    setRitualExperimentFormOpen: vi.fn(),
    ritualExperimentPending: { 5: false },
    ritualExperimentError: {},
    ritualExperimentMessage: {},
    ritualExperimentCloseDrafts: { 101: { decision: "ITERATE" as const, rationale: "" } },
    ritualExperimentActionPending: {},
    updateRitualExperimentCloseDraft: vi.fn(),
    ritualExperimentActionError: {},
    ritualExperimentActionMessage: {},
    updateRitualCheckInDraft: vi.fn(),
    updateRitualExperimentDraft: vi.fn(),
    handleRitualExperimentCreate: vi.fn(async () => {}),
    handleRitualExperimentStart: vi.fn(async () => {}),
    handleRitualExperimentClose: vi.fn(async () => {}),
    formatOptionalNumber: (value: unknown) => String(value ?? "-"),
    ritualCheckInPending: {},
    handleRitualCheckInSubmit: vi.fn(async () => {}),
    ritualCheckInError: {},
    ritualCheckInMessage: {},
    weeklyPlanData: { priority_1: "Lock auth", priority_2: "Stabilize CI", priority_3: "Expand tests" },
    weeklyDraft: { p1: "", p2: "", p3: "" },
    setWeeklyDraft: vi.fn(),
    handleWeeklyPlanSave: vi.fn(async () => {}),
    endOfWeekIso: () => "2026-01-07",
    ...overrides,
  };
}

describe("RitualModePanel", () => {
  it("wires review-step retrospective actions", async () => {
    const user = userEvent.setup();
    const setRetroDraft = vi.fn();
    const retroTransitions: Array<{ content: string; sentiment: string }> = [];
    setRetroDraft.mockImplementation((update) => {
      if (typeof update === "function") {
        retroTransitions.push(update({ content: "", sentiment: "steady" }));
      }
    });
    const handleRetroCreate = vi.fn(async () => {});
    const setRitualStep = vi.fn();

    render(
      <RitualModePanel
        {...makeProps({
          ritualStep: 1,
          setRetroDraft,
          handleRetroCreate,
          setRitualStep,
          ritualReviewExperiments: [{ id: 77, key_result_id: 5, hypothesis: "Improve flow", status: "RUNNING" }],
        })}
      />,
    );

    expect(screen.getByText(/Review window:/i)).toBeInTheDocument();
    expect(screen.getByText(/7-day focus:/i)).toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText(
        "What moved this week? What blocked progress? What will you change next week?",
      ),
      { target: { value: "Closed auth boundary gap." } },
    );
    expect(retroTransitions[0].content).toBe("Closed auth boundary gap.");

    await user.click(screen.getByRole("button", { name: "Save Retrospective" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(handleRetroCreate).toHaveBeenCalledWith("ritual", "2026-01-01");
    expect(setRitualStep).toHaveBeenCalled();
  });

  it("wires check-in and experiment lifecycle actions", async () => {
    const user = userEvent.setup();
    const updateRitualCheckInDraft = vi.fn();
    const setRitualExperimentFormOpen = vi.fn();
    const updateRitualExperimentDraft = vi.fn();
    const handleRitualExperimentCreate = vi.fn(async () => {});
    const handleRitualExperimentStart = vi.fn(async () => {});
    const updateRitualExperimentCloseDraft = vi.fn();
    const handleRitualExperimentClose = vi.fn(async () => {});
    const handleRitualCheckInSubmit = vi.fn(async () => {});

    render(
      <RitualModePanel
        {...makeProps({
          ritualStep: 2,
          updateRitualCheckInDraft,
          setRitualExperimentFormOpen,
          updateRitualExperimentDraft,
          handleRitualExperimentCreate,
          handleRitualExperimentStart,
          updateRitualExperimentCloseDraft,
          handleRitualExperimentClose,
          handleRitualCheckInSubmit,
        })}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Enter numeric value"), { target: { value: "18.2" } });
    expect(updateRitualCheckInDraft).toHaveBeenCalledWith(5, { value: "18.2" });

    fireEvent.change(screen.getByDisplayValue("No linked experiment"), { target: { value: "101" } });
    expect(updateRitualCheckInDraft).toHaveBeenCalledWith(5, { experimentId: "101" });

    await user.click(screen.getByRole("button", { name: "Hide Experiment Form" }));
    expect(setRitualExperimentFormOpen).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByPlaceholderText("Hypothesis"), {
      target: { value: "Increase daily throughput by reducing handoff delay" },
    });
    expect(updateRitualExperimentDraft).toHaveBeenCalledWith(5, {
      hypothesis: "Increase daily throughput by reducing handoff delay",
    });

    await user.click(screen.getByRole("button", { name: "Create Experiment" }));
    await user.click(screen.getByRole("button", { name: "Start" }));
    fireEvent.change(screen.getByDisplayValue("Iterate"), { target: { value: "ADOPT" } });
    fireEvent.change(screen.getByPlaceholderText("Decision rationale (required)"), {
      target: { value: "Hit expected gain and improved stability." },
    });
    await user.click(screen.getByRole("button", { name: "Close Experiment" }));
    await user.click(screen.getByRole("button", { name: "Submit Check-In" }));

    expect(handleRitualExperimentCreate).toHaveBeenCalledWith(expect.objectContaining({ id: 5 }));
    expect(handleRitualExperimentStart).toHaveBeenCalledWith(102);
    expect(updateRitualExperimentCloseDraft).toHaveBeenCalledWith(101, { decision: "ADOPT" });
    expect(updateRitualExperimentCloseDraft).toHaveBeenCalledWith(101, {
      rationale: "Hit expected gain and improved stability.",
    });
    expect(handleRitualExperimentClose).toHaveBeenCalledWith(101);
    expect(handleRitualCheckInSubmit).toHaveBeenCalledWith(expect.objectContaining({ id: 5 }));
    expect(screen.getByText(/Decision: ADOPT/i)).toBeInTheDocument();
  });

  it("wires plan-step updates and completion action", async () => {
    const user = userEvent.setup();
    const setWeeklyDraft = vi.fn();
    const weeklyTransitions: Array<{ p1: string; p2: string; p3: string }> = [];
    setWeeklyDraft.mockImplementation((update) => {
      if (typeof update === "function") {
        weeklyTransitions.push(update({ p1: "", p2: "hold", p3: "" }));
      }
    });
    const handleWeeklyPlanSave = vi.fn(async () => {});
    const setRitualStep = vi.fn();

    render(
      <RitualModePanel
        {...makeProps({
          ritualStep: 3,
          setWeeklyDraft,
          handleWeeklyPlanSave,
          setRitualStep,
        })}
      />,
    );

    expect(screen.getByText(/Current plan/i)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Priority 1 (required)"), {
      target: { value: "Finalize rollout guardrails" },
    });
    expect(weeklyTransitions[0]).toEqual({
      p1: "Finalize rollout guardrails",
      p2: "hold",
      p3: "",
    });

    await user.click(screen.getByRole("button", { name: "Finish Check-In" }));
    expect(handleWeeklyPlanSave).toHaveBeenCalledWith("ritual");

    const nextButton = screen.getByRole("button", { name: "Next" });
    expect(nextButton).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Back" }));

    const backUpdate = setRitualStep.mock.calls[0][0] as (prev: 1 | 2 | 3) => 1 | 2 | 3;
    expect(backUpdate(3)).toBe(2);
  });
});

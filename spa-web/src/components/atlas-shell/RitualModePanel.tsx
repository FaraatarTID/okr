"use client";

import type { Dispatch, SetStateAction } from "react";
import { rtlStyle } from "@/lib/rtl";

type WorkLogReadView = {
  duration_minutes?: number | null;
};

type RitualReviewRangeView = {
  start: Date;
  end: Date;
};

type RetroDraftView = {
  content: string;
  sentiment: string;
};

type WeeklyPlanDataView = {
  priority_1?: string | null;
  priority_2?: string | null;
  priority_3?: string | null;
} | null;

type WeeklyDraftView = {
  p1: string;
  p2: string;
  p3: string;
};

type ExperimentDecisionTypeView = "ADOPT" | "ITERATE" | "ABANDON";

type RitualExperimentView = {
  id: number;
  key_result_id: number;
  hypothesis?: string | null;
  status?: "PLANNED" | "RUNNING" | "DECIDED" | null;
  decision?: ExperimentDecisionTypeView | null;
};

type RitualKrView = {
  id: number;
  title?: string | null;
  progress?: number | null;
  current_value?: number | null;
  objective?: { title?: string | null } | null;
};

type CheckInDraftView = {
  value: string;
  confidence: string;
  comment: string;
  variationType: "COMMON_CAUSE" | "SPECIAL_CAUSE";
  specialCauseNote: string;
  experimentId: string;
};

type ExperimentDraftView = {
  hypothesis: string;
  changeDescription: string;
  expectedEffectDirection: "" | "UP" | "DOWN";
  expectedEffectSize: string;
};

type ExperimentCloseDraftView = {
  decision: ExperimentDecisionTypeView;
  rationale: string;
};

type RitualModePanelProps = {
  ritualStep: 1 | 2 | 3;
  setRitualStep: Dispatch<SetStateAction<1 | 2 | 3>>;
  cycleLabel: string;
  ritualKrs: RitualKrView[];
  ritualSubmittedCount: number;
  ritualReviewLogs: WorkLogReadView[];
  ritualReviewExperiments: RitualExperimentView[];
  toDateShortLabel: (value: Date) => string;
  ritualReviewRange: RitualReviewRangeView;
  retroDraft: RetroDraftView;
  setRetroDraft: Dispatch<SetStateAction<RetroDraftView>>;
  handleRetroCreate: (mode?: "ritual" | "retrobox", weekStartDate?: string) => Promise<void>;
  startOfWeekIso: () => string;
  modeActionPending: boolean;
  ritualCheckInDrafts: Record<number, CheckInDraftView>;
  ritualExperimentsByKr: Record<number, RitualExperimentView[]>;
  ritualExperimentDrafts: Record<number, ExperimentDraftView>;
  ritualExperimentFormOpen: Record<number, boolean>;
  setRitualExperimentFormOpen: Dispatch<SetStateAction<Record<number, boolean>>>;
  ritualExperimentPending: Record<number, boolean>;
  ritualExperimentError: Record<number, string>;
  ritualExperimentMessage: Record<number, string>;
  ritualExperimentCloseDrafts: Record<number, ExperimentCloseDraftView>;
  ritualExperimentActionPending: Record<number, boolean>;
  updateRitualExperimentCloseDraft: (
    experimentId: number,
    patch: Partial<ExperimentCloseDraftView>,
  ) => void;
  ritualExperimentActionError: Record<number, string>;
  ritualExperimentActionMessage: Record<number, string>;
  updateRitualCheckInDraft: (krId: number, patch: Partial<CheckInDraftView>) => void;
  updateRitualExperimentDraft: (krId: number, patch: Partial<ExperimentDraftView>) => void;
  handleRitualExperimentCreate: (kr: RitualKrView) => Promise<void>;
  handleRitualExperimentStart: (experimentId: number) => Promise<void>;
  handleRitualExperimentClose: (experimentId: number) => Promise<void>;
  formatOptionalNumber: (value: unknown) => string;
  ritualCheckInPending: Record<number, boolean>;
  handleRitualCheckInSubmit: (kr: RitualKrView) => Promise<void>;
  ritualCheckInError: Record<number, string>;
  ritualCheckInMessage: Record<number, string>;
  weeklyPlanData: WeeklyPlanDataView;
  weeklyDraft: WeeklyDraftView;
  setWeeklyDraft: Dispatch<SetStateAction<WeeklyDraftView>>;
  handleWeeklyPlanSave: (sourceMode?: "weekly" | "ritual") => Promise<void>;
  endOfWeekIso: () => string;
};

export default function RitualModePanel({
  ritualStep,
  setRitualStep,
  cycleLabel,
  ritualKrs,
  ritualSubmittedCount,
  ritualReviewLogs,
  ritualReviewExperiments,
  toDateShortLabel,
  ritualReviewRange,
  retroDraft,
  setRetroDraft,
  handleRetroCreate,
  startOfWeekIso,
  modeActionPending,
  ritualCheckInDrafts,
  ritualExperimentsByKr,
  ritualExperimentDrafts,
  ritualExperimentFormOpen,
  setRitualExperimentFormOpen,
  ritualExperimentPending,
  ritualExperimentError,
  ritualExperimentMessage,
  ritualExperimentCloseDrafts,
  ritualExperimentActionPending,
  updateRitualExperimentCloseDraft,
  ritualExperimentActionError,
  ritualExperimentActionMessage,
  updateRitualCheckInDraft,
  updateRitualExperimentDraft,
  handleRitualExperimentCreate,
  handleRitualExperimentStart,
  handleRitualExperimentClose,
  formatOptionalNumber,
  ritualCheckInPending,
  handleRitualCheckInSubmit,
  ritualCheckInError,
  ritualCheckInMessage,
  weeklyPlanData,
  weeklyDraft,
  setWeeklyDraft,
  handleWeeklyPlanSave,
  endOfWeekIso,
}: RitualModePanelProps) {
  return (
          <div style={{ marginTop: "0.5rem" }}>
            <div className="checkin-stepper">
              <button
                type="button"
                className="primary-button"
                aria-current={ritualStep === 1 ? "step" : undefined}
                onClick={() => setRitualStep(1)}
              >
                1. Review
              </button>
              <button
                type="button"
                className="primary-button"
                aria-current={ritualStep === 2 ? "step" : undefined}
                onClick={() => setRitualStep(2)}
              >
                2. Check-Ins
              </button>
              <button
                type="button"
                className="primary-button"
                aria-current={ritualStep === 3 ? "step" : undefined}
                onClick={() => setRitualStep(3)}
              >
                3. Plan
              </button>
            </div>

            <div className="atlas-rollup" style={{ marginTop: "0.45rem" }}>
              <span>Cycle: {cycleLabel}</span>
              <span>KRs needing check-in: {ritualKrs.length}</span>
              <span>
                Submitted: {ritualSubmittedCount}/{ritualKrs.length}
              </span>
              <span>Remaining: {Math.max(0, ritualKrs.length - ritualSubmittedCount)}</span>
              <span>
                7-day focus:{" "}
                {Math.round(
                  ritualReviewLogs.reduce((sum, item) => sum + Number(item.duration_minutes || 0), 0),
                )}{" "}
                minutes
              </span>
              <span>Experiments reviewed: {ritualReviewExperiments.length}</span>
            </div>

            {ritualStep === 1 ? (
              <div style={{ marginTop: "0.55rem" }}>
                <p style={{ margin: 0, color: "var(--ink-soft)" }}>
                  Review window: {toDateShortLabel(ritualReviewRange.start)} to{" "}
                  {toDateShortLabel(ritualReviewRange.end)}
                </p>

                <div style={{ marginTop: "0.5rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.55rem" }}>
                  <p className="kicker" style={{ margin: 0 }}>Retrospective</p>
                  <textarea
                    className="input"
                    value={retroDraft.content}
                    onChange={(event) => setRetroDraft((prev) => ({ ...prev, content: event.target.value }))}
                    rows={4}
                    placeholder="What moved this week? What blocked progress? What will you change next week?"
                    style={{ marginTop: "0.35rem" }}
                  />
                  <input
                    className="input"
                    value={retroDraft.sentiment}
                    onChange={(event) => setRetroDraft((prev) => ({ ...prev, sentiment: event.target.value }))}
                    placeholder="Sentiment (optional)"
                    style={{ marginTop: "0.35rem" }}
                  />
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => void handleRetroCreate("ritual", startOfWeekIso())}
                    disabled={modeActionPending}
                    style={{ marginTop: "0.42rem" }}
                  >
                    {modeActionPending ? "Saving..." : "Save Retrospective"}
                  </button>
                </div>

                <div style={{ marginTop: "0.5rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.55rem" }}>
                  <p className="kicker" style={{ margin: 0 }}>Experiments Reviewed</p>
                  <div className="atlas-node-list" style={{ marginTop: "0.35rem", maxHeight: "28vh" }}>
                    {ritualReviewExperiments.length ? (
                      ritualReviewExperiments.map((exp) => (
                        <div key={exp.id} style={{ padding: "0.38rem 0", borderBottom: "1px solid var(--line)" }}>
                          <strong>#{exp.id} • {String(exp.status || "PLANNED")}</strong>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                            KR #{exp.key_result_id}
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                            {String(exp.hypothesis || "").trim() || "No hypothesis captured."}
                          </div>
                        </div>
                      ))
                    ) : (
                      <p style={{ margin: 0, color: "var(--ink-soft)" }}>
                        No experiments in this review window.
                      </p>
                    )}
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.5rem" }}>
                  <button className="primary-button" type="button" onClick={() => setRitualStep(2)}>
                    Next: Check-Ins
                  </button>
                </div>
              </div>
            ) : null}

            {ritualStep === 2 ? (
              <>
                <div style={{ marginTop: "0.45rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.45rem", background: "var(--surface)" }}>
                  <p className="kicker" style={{ margin: 0 }}>Check-In Guide</p>
                  <p style={{ margin: "0.2rem 0 0", fontSize: "0.78rem", color: "var(--ink-soft)" }}>
                    For each KR: enter the current metric value and classify the change.
                    <br />
                    <strong>Common Cause</strong> = normal system behavior. Optionally link to a running experiment.
                    <br />
                    <strong>Special Cause</strong> = exceptional event. Add a note explaining what happened.
                    <br />
                    If the AI projection differs from your actual progress, you planned too much or too little work — write this insight in your retro (Step 1).
                  </p>
                </div>

                <div className="atlas-node-list" style={{ marginTop: "0.45rem", maxHeight: "52vh" }}>
                  {ritualKrs.length ? (
                    ritualKrs.map((kr) => {
                    const draft = ritualCheckInDrafts[kr.id];
                    const experiments = ritualExperimentsByKr[kr.id] || [];
                    const experimentDraft = ritualExperimentDrafts[kr.id] || {
                      hypothesis: "",
                      changeDescription: "",
                      expectedEffectDirection: "",
                      expectedEffectSize: "",
                    };
                    const runningExperiments = experiments.filter(
                      (exp) => String(exp.status || "").toUpperCase() === "RUNNING",
                    );
                    const variationType = draft?.variationType || "COMMON_CAUSE";
                    const isSaved = Boolean(ritualCheckInMessage[kr.id]);
                    return (
                      <div
                        key={kr.id}
                        className={`checkin-kr-card${isSaved ? " is-saved" : ""}`}
                        style={{ padding: "0.5rem 0", borderBottom: "1px solid var(--line)" }}
                      >
                        <div style={{ display: "flex", gap: "0.45rem", alignItems: "center", flexWrap: "wrap" }}>
                          <strong>{kr.title || `KR #${kr.id}`}</strong>
                          {isSaved ? (
                            <span style={{ fontSize: "0.74rem", color: "var(--accent)" }}>Saved</span>
                          ) : null}
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                          Progress {Math.round(Number(kr.progress || 0))}% • {kr.objective?.title || "No objective"}
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)", marginTop: "0.15rem" }}>
                          Current value: {formatOptionalNumber(kr.current_value)}
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.35rem", marginTop: "0.4rem" }}>
                          <input
                            className="input"
                            value={draft?.value || ""}
                            onChange={(event) => updateRitualCheckInDraft(kr.id, { value: event.target.value })}
                            placeholder="Metric value"
                          />
                          <input
                            className="input"
                            value={draft?.confidence || ""}
                            onChange={(event) => updateRitualCheckInDraft(kr.id, { confidence: event.target.value })}
                            placeholder="Confidence (0-10)"
                          />
                        </div>

                        <textarea
                          className="input"
                          value={draft?.comment || ""}
                          onChange={(event) => updateRitualCheckInDraft(kr.id, { comment: event.target.value })}
                          placeholder="Check-in comment (required when confidence is 0-5)"
                          rows={2}
                          style={{ marginTop: "0.35rem" }}
                        />

                        <select
                          className="input"
                          value={variationType}
                          onChange={(event) =>
                            updateRitualCheckInDraft(kr.id, {
                              variationType: event.target.value as "COMMON_CAUSE" | "SPECIAL_CAUSE",
                            })
                          }
                          style={{ marginTop: "0.35rem" }}
                        >
                          <option value="COMMON_CAUSE">Common cause</option>
                          <option value="SPECIAL_CAUSE">Special cause</option>
                        </select>

                        {variationType === "SPECIAL_CAUSE" ? (
                          <input
                            className="input"
                            value={draft?.specialCauseNote || ""}
                            onChange={(event) =>
                              updateRitualCheckInDraft(kr.id, { specialCauseNote: event.target.value })
                            }
                            placeholder="Special-cause note (required)"
                            style={{ marginTop: "0.35rem" }}
                          />
                        ) : (
                          <div style={{ marginTop: "0.35rem" }}>
                            <select
                              className="input"
                              value={draft?.experimentId || ""}
                              onChange={(event) =>
                                updateRitualCheckInDraft(kr.id, { experimentId: event.target.value })
                              }
                            >
                              <option value="">No linked experiment</option>
                              {runningExperiments.map((exp) => (
                                <option key={exp.id} value={exp.id}>
                                  #{exp.id} • RUNNING •{" "}
                                  {String(exp.hypothesis || "").slice(0, 72)}
                                </option>
                              ))}
                            </select>
                            <div style={{ display: "flex", gap: "0.35rem", marginTop: "0.35rem", flexWrap: "wrap" }}>
                              <button
                                className="primary-button"
                                type="button"
                                onClick={() =>
                                  setRitualExperimentFormOpen((prev) => ({
                                    ...prev,
                                    [kr.id]: !prev[kr.id],
                                  }))
                                }
                              >
                                {ritualExperimentFormOpen[kr.id] ? "Hide Experiment Form" : "Create Experiment"}
                              </button>
                            </div>
                            {ritualExperimentFormOpen[kr.id] ? (
                              <div style={{ marginTop: "0.35rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.45rem" }}>
                                <input
                                  className="input"
                                  value={experimentDraft.hypothesis}
                                  onChange={(event) =>
                                    updateRitualExperimentDraft(kr.id, { hypothesis: event.target.value })
                                  }
                                  placeholder="Hypothesis"
                                />
                                <input
                                  className="input"
                                  value={experimentDraft.changeDescription}
                                  onChange={(event) =>
                                    updateRitualExperimentDraft(kr.id, { changeDescription: event.target.value })
                                  }
                                  placeholder="Change description"
                                  style={{ marginTop: "0.35rem" }}
                                />
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.35rem", marginTop: "0.35rem" }}>
                                  <select
                                    className="input"
                                    value={experimentDraft.expectedEffectDirection}
                                    onChange={(event) =>
                                      updateRitualExperimentDraft(kr.id, {
                                        expectedEffectDirection: event.target.value as "" | "UP" | "DOWN",
                                      })
                                    }
                                  >
                                    <option value="">Effect direction (optional)</option>
                                    <option value="UP">Up</option>
                                    <option value="DOWN">Down</option>
                                  </select>
                                  <input
                                    className="input"
                                    value={experimentDraft.expectedEffectSize}
                                    onChange={(event) =>
                                      updateRitualExperimentDraft(kr.id, { expectedEffectSize: event.target.value })
                                    }
                                    placeholder="Effect size (optional)"
                                  />
                                </div>
                                <button
                                  className="primary-button"
                                  type="button"
                                  onClick={() => void handleRitualExperimentCreate(kr)}
                                  disabled={Boolean(ritualExperimentPending[kr.id])}
                                  style={{ marginTop: "0.4rem" }}
                                >
                                  {ritualExperimentPending[kr.id] ? "Creating..." : "Create Experiment"}
                                </button>
                                {ritualExperimentError[kr.id] ? (
                                  <p style={{ margin: "0.28rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
                                    {ritualExperimentError[kr.id]}
                                  </p>
                                ) : null}
                                {ritualExperimentMessage[kr.id] ? (
                                  <p style={{ margin: "0.28rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
                                    {ritualExperimentMessage[kr.id]}
                                  </p>
                                ) : null}
                              </div>
                            ) : null}
                            <div
                              style={{
                                marginTop: "0.35rem",
                                border: "1px solid var(--line)",
                                borderRadius: 10,
                                padding: "0.45rem",
                              }}
                            >
                              <p className="kicker" style={{ margin: 0 }}>
                                Experiment Lifecycle
                              </p>
                              {experiments.length ? (
                                <div style={{ marginTop: "0.28rem", display: "grid", gap: "0.35rem" }}>
                                  {experiments.map((exp) => {
                                    const expId = Number(exp.id);
                                    const status = String(exp.status || "PLANNED").toUpperCase();
                                    const closeDraft = ritualExperimentCloseDrafts[expId] || {
                                      decision: "ITERATE" as ExperimentDecisionTypeView,
                                      rationale: "",
                                    };
                                    const actionPending = Boolean(ritualExperimentActionPending[expId]);
                                    return (
                                      <div
                                        key={expId}
                                        style={{
                                          border: "1px solid var(--line)",
                                          borderRadius: 8,
                                          padding: "0.38rem",
                                          background: "var(--surface)",
                                        }}
                                      >
                                        <div style={{ display: "flex", gap: "0.35rem", alignItems: "center", flexWrap: "wrap" }}>
                                          <strong>#{expId}</strong>
                                          <span style={{ fontSize: "0.74rem", color: "var(--ink-soft)" }}>
                                            {status}
                                          </span>
                                        </div>
                                        <div style={{ marginTop: "0.18rem", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                                          {String(exp.hypothesis || "").trim() || "No hypothesis captured."}
                                        </div>

                                        {status === "PLANNED" ? (
                                          <button
                                            className="primary-button"
                                            type="button"
                                            onClick={() => void handleRitualExperimentStart(expId)}
                                            disabled={actionPending}
                                            style={{ marginTop: "0.32rem" }}
                                          >
                                            {actionPending ? "Starting..." : "Start"}
                                          </button>
                                        ) : null}

                                        {status === "RUNNING" ? (
                                          <div style={{ marginTop: "0.32rem", display: "grid", gap: "0.28rem" }}>
                                            <select
                                              className="input"
                                              value={closeDraft.decision}
                                              onChange={(event) =>
                                                updateRitualExperimentCloseDraft(expId, {
                                                  decision: event.target.value as ExperimentDecisionTypeView,
                                                })
                                              }
                                            >
                                              <option value="ADOPT">Adopt</option>
                                              <option value="ITERATE">Iterate</option>
                                              <option value="ABANDON">Abandon</option>
                                            </select>
                                            <textarea
                                              className="input"
                                              value={closeDraft.rationale}
                                              onChange={(event) =>
                                                updateRitualExperimentCloseDraft(expId, {
                                                  rationale: event.target.value,
                                                })
                                              }
                                              rows={2}
                                              placeholder="Decision rationale (required)"
                                            />
                                            <button
                                              className="primary-button"
                                              type="button"
                                              onClick={() => void handleRitualExperimentClose(expId)}
                                              disabled={actionPending}
                                            >
                                              {actionPending ? "Closing..." : "Close Experiment"}
                                            </button>
                                          </div>
                                        ) : null}

                                        {status === "DECIDED" ? (
                                          <p style={{ margin: "0.28rem 0 0", fontSize: "0.78rem", color: "var(--ink-soft)" }}>
                                            Decision: {String(exp.decision || "N/A")}
                                          </p>
                                        ) : null}

                                        {ritualExperimentActionError[expId] ? (
                                          <p style={{ margin: "0.28rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
                                            {ritualExperimentActionError[expId]}
                                          </p>
                                        ) : null}
                                        {ritualExperimentActionMessage[expId] ? (
                                          <p style={{ margin: "0.28rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
                                            {ritualExperimentActionMessage[expId]}
                                          </p>
                                        ) : null}
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <p style={{ margin: "0.32rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem" }}>
                                  No experiments created for this KR yet.
                                </p>
                              )}
                            </div>
                          </div>
                        )}

                        <button
                          className="primary-button"
                          type="button"
                          style={{ marginTop: "0.4rem" }}
                          onClick={() => void handleRitualCheckInSubmit(kr)}
                          disabled={Boolean(ritualCheckInPending[kr.id])}
                        >
                          {ritualCheckInPending[kr.id] ? "Saving..." : "Submit Check-In"}
                        </button>
                        {ritualCheckInError[kr.id] ? (
                          <p style={{ margin: "0.28rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
                            {ritualCheckInError[kr.id]}
                          </p>
                        ) : null}
                        {ritualCheckInMessage[kr.id] ? (
                          <p style={{ margin: "0.28rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
                            {ritualCheckInMessage[kr.id]}
                          </p>
                        ) : null}
                      </div>
                    );
                    })
                  ) : (
                    <p style={{ margin: 0, color: "var(--ink-soft)" }}>All clear for this cycle.</p>
                  )}
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.45rem" }}>
                  <button className="primary-button" type="button" onClick={() => setRitualStep(3)}>
                    Next: Plan
                  </button>
                </div>
              </>
            ) : null}

            {ritualStep === 3 ? (
              <div style={{ marginTop: "0.5rem" }}>
                <p style={{ margin: 0, color: "var(--ink-soft)" }}>
                  Week: {startOfWeekIso()} to {endOfWeekIso()}
                </p>
                {weeklyPlanData ? (
                  <div style={{ marginTop: "0.35rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.5rem" }}>
                    <strong>Current plan</strong>
                    <p style={{ margin: "0.24rem 0 0" }}>1. {weeklyPlanData.priority_1 || "-"}</p>
                    <p style={{ margin: "0.2rem 0 0" }}>2. {weeklyPlanData.priority_2 || "-"}</p>
                    <p style={{ margin: "0.2rem 0 0" }}>3. {weeklyPlanData.priority_3 || "-"}</p>
                  </div>
                ) : null}
                <div style={{ marginTop: "0.42rem", display: "grid", gap: "0.35rem" }}>
                  <input className="input" value={weeklyDraft.p1} onChange={(event) => setWeeklyDraft((prev) => ({ ...prev, p1: event.target.value }))} placeholder="Priority 1 (required)" />
                  <input className="input" value={weeklyDraft.p2} onChange={(event) => setWeeklyDraft((prev) => ({ ...prev, p2: event.target.value }))} placeholder="Priority 2" />
                  <input className="input" value={weeklyDraft.p3} onChange={(event) => setWeeklyDraft((prev) => ({ ...prev, p3: event.target.value }))} placeholder="Priority 3" />
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => void handleWeeklyPlanSave("ritual")}
                    disabled={modeActionPending}
                    style={{ marginTop: "0.1rem" }}
                  >
                    {modeActionPending ? "Saving..." : "Finish Check-In"}
                  </button>
                </div>
              </div>
            ) : null}

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.6rem", gap: "0.5rem" }}>
              <button
                className="primary-button"
                type="button"
                onClick={() => setRitualStep((prev) => (prev > 1 ? ((prev - 1) as 1 | 2 | 3) : prev))}
                disabled={ritualStep === 1}
              >
                Back
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={() => setRitualStep((prev) => (prev < 3 ? ((prev + 1) as 1 | 2 | 3) : prev))}
                disabled={ritualStep === 3}
              >
                Next
              </button>
            </div>
          </div>
  );
}



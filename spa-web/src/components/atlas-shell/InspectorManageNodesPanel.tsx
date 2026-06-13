"use client";

type CreateTypeView = "goal" | "objective" | "key_result" | "task";

type NodeCreateDraftView = {
  createType: CreateTypeView;
  title: string;
  description: string;
  cycleId: string;
  tags: string;
  targetValue: string;
  unit: string;
  estimatedMinutes: string;
  assigneeId: string;
};

type CreateContextView = {
  goalId: number | null;
  objectiveId: number | null;
  keyResultId: number | null;
};

type InspectorManageNodesPanelProps = {
  createDraft: NodeCreateDraftView;
  onCreateDraftChange: (patch: Partial<NodeCreateDraftView>) => void;
  createContext: CreateContextView;
  canCreateForContext: boolean;
  createTypeLabel: (createType: CreateTypeView) => string;
  cycleLabel: string;
  onCreateNode: () => void;
  createPending: boolean;
  hasUser: boolean;
  createError: string;
  createMessage: string;
  deleteError: string;
  deleteMessage: string;
};

export default function InspectorManageNodesPanel({
  createDraft,
  onCreateDraftChange,
  createContext,
  canCreateForContext,
  createTypeLabel,
  cycleLabel,
  onCreateNode,
  createPending,
  hasUser,
  createError,
  createMessage,
  deleteError,
  deleteMessage,
}: InspectorManageNodesPanelProps) {
  return (
    <div
      style={{
        marginTop: "0.72rem",
        border: "1px solid var(--line)",
        borderRadius: 10,
        background: "var(--surface)",
        padding: "0.55rem 0.6rem",
      }}
    >
      <p className="kicker" style={{ margin: 0 }}>
        Manage Nodes
      </p>
      <p style={{ margin: "0.24rem 0 0.3rem", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
        Create Goal/Objective/Key Result/Task nodes.
      </p>

      <label
        htmlFor="create-type"
        style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
      >
        Create Type
      </label>
      <select
        id="create-type"
        className="input"
        value={createDraft.createType}
        onChange={(event) => onCreateDraftChange({ createType: event.target.value as CreateTypeView })}
        style={{ marginTop: "0.2rem" }}
      >
        <option value="goal">Goal</option>
        <option value="objective">Objective</option>
        <option value="key_result">Key Result</option>
        <option value="task">Task</option>
      </select>

      <label
        htmlFor="create-title"
        style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
      >
        {createTypeLabel(createDraft.createType)} Title
      </label>
      <input
        id="create-title"
        className="input"
        value={createDraft.title}
        onChange={(event) => onCreateDraftChange({ title: event.target.value })}
        style={{ marginTop: "0.2rem" }}
      />

      <label
        htmlFor="create-description"
        style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
      >
        Description
      </label>
      <input
        id="create-description"
        className="input"
        value={createDraft.description}
        onChange={(event) => onCreateDraftChange({ description: event.target.value })}
        style={{ marginTop: "0.2rem" }}
      />

      {createDraft.createType === "goal" ? (
        <>
          <p style={{ margin: "0.36rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
            Cycle: {cycleLabel}
          </p>
          <label
            htmlFor="create-goal-tags"
            style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
          >
            Strategy Tags (optional, comma-separated)
          </label>
          <input
            id="create-goal-tags"
            className="input"
            value={createDraft.tags}
            onChange={(event) => onCreateDraftChange({ tags: event.target.value })}
            style={{ marginTop: "0.2rem" }}
          />
        </>
      ) : null}

      {createDraft.createType === "objective" ? (
        <p style={{ margin: "0.36rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
          Parent Goal ID: {createContext.goalId ?? "-"}
        </p>
      ) : null}

      {createDraft.createType === "key_result" ? (
        <>
          <p style={{ margin: "0.36rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
            Parent Objective ID: {createContext.objectiveId ?? "-"}
          </p>
          <label
            htmlFor="create-kr-target"
            style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
          >
            Target Value
          </label>
          <input
            id="create-kr-target"
            className="input"
            value={createDraft.targetValue}
            onChange={(event) => onCreateDraftChange({ targetValue: event.target.value })}
            style={{ marginTop: "0.2rem" }}
          />
          <label
            htmlFor="create-kr-unit"
            style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
          >
            Unit
          </label>
          <input
            id="create-kr-unit"
            className="input"
            value={createDraft.unit}
            onChange={(event) => onCreateDraftChange({ unit: event.target.value })}
            style={{ marginTop: "0.2rem" }}
          />
          <label
            htmlFor="create-kr-tags"
            style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
          >
            Initiative Tags (optional, comma-separated)
          </label>
          <input
            id="create-kr-tags"
            className="input"
            value={createDraft.tags}
            onChange={(event) => onCreateDraftChange({ tags: event.target.value })}
            style={{ marginTop: "0.2rem" }}
          />
        </>
      ) : null}

      {createDraft.createType === "task" ? (
        <>
          <p style={{ margin: "0.36rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
            Parent Key Result ID: {createContext.keyResultId ?? "-"}
          </p>
          <label
            htmlFor="create-task-estimate"
            style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
          >
            Estimated Minutes
          </label>
          <input
            id="create-task-estimate"
            className="input"
            value={createDraft.estimatedMinutes}
            onChange={(event) => onCreateDraftChange({ estimatedMinutes: event.target.value })}
            style={{ marginTop: "0.2rem" }}
          />
          <label
            htmlFor="create-task-assignee"
            style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
          >
            Assignee ID (optional)
          </label>
          <input
            id="create-task-assignee"
            className="input"
            value={createDraft.assigneeId}
            onChange={(event) => onCreateDraftChange({ assigneeId: event.target.value })}
            style={{ marginTop: "0.2rem" }}
          />
        </>
      ) : null}

      {!canCreateForContext && createDraft.createType !== "goal" ? (
        <p style={{ margin: "0.36rem 0 0", color: "var(--warn)", fontSize: "0.82rem" }}>
          Current selection does not provide a valid parent for this create type.
        </p>
      ) : null}

      <div style={{ marginTop: "0.46rem" }}>
        <button
          className="primary-button"
          type="button"
          onClick={onCreateNode}
          disabled={createPending || !hasUser || !canCreateForContext}
        >
          {createPending ? "Creating..." : `Create ${createTypeLabel(createDraft.createType)}`}
        </button>
      </div>

      {createError ? (
        <p style={{ margin: "0.34rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {createError}
        </p>
      ) : null}
      {createMessage ? (
        <p style={{ margin: "0.34rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
          {createMessage}
        </p>
      ) : null}
      {deleteError ? (
        <p style={{ margin: "0.34rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {deleteError}
        </p>
      ) : null}
      {deleteMessage ? (
        <p style={{ margin: "0.34rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
          {deleteMessage}
        </p>
      ) : null}
    </div>
  );
}

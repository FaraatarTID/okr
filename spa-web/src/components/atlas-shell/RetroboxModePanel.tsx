"use client";

type RetroDraftView = {
  content: string;
  sentiment: string;
};

type RetroItemView = {
  id: number;
  week_start_date?: string | null;
  sentiment?: string | null;
  content?: string | null;
};

type RetroboxModePanelProps = {
  retroDraft: RetroDraftView;
  onRetroDraftChange: (patch: Partial<RetroDraftView>) => void;
  modeActionPending: boolean;
  onAddRetrospective: () => void;
  retroItems: RetroItemView[];
  formatOptionalDate: (value: unknown) => string;
};

export default function RetroboxModePanel({
  retroDraft,
  onRetroDraftChange,
  modeActionPending,
  onAddRetrospective,
  retroItems,
  formatOptionalDate,
}: RetroboxModePanelProps) {
  return (
    <div style={{ marginTop: "0.5rem" }}>
      <label style={{ fontSize: "0.82rem", color: "var(--ink-soft)" }}>Retro content</label>
      <textarea
        className="input"
        value={retroDraft.content}
        onChange={(event) => onRetroDraftChange({ content: event.target.value })}
        rows={4}
      />
      <label style={{ fontSize: "0.82rem", color: "var(--ink-soft)" }}>Sentiment (optional)</label>
      <input
        className="input"
        value={retroDraft.sentiment}
        onChange={(event) => onRetroDraftChange({ sentiment: event.target.value })}
      />
      <button
        className="primary-button"
        type="button"
        onClick={onAddRetrospective}
        disabled={modeActionPending}
        style={{ marginTop: "0.5rem" }}
      >
        {modeActionPending ? "Saving..." : "Add retrospective"}
      </button>
      <div className="atlas-node-list" style={{ marginTop: "0.55rem", maxHeight: "42vh" }}>
        {retroItems.length ? (
          retroItems.map((retro) => (
            <div key={retro.id} style={{ padding: "0.42rem 0", borderBottom: "1px solid var(--line)" }}>
              <div style={{ fontSize: "0.78rem", color: "var(--ink-soft)" }}>
                {formatOptionalDate(retro.week_start_date)} • {retro.sentiment || "n/a"}
              </div>
              <p style={{ margin: "0.2rem 0 0", whiteSpace: "pre-wrap" }}>{retro.content || ""}</p>
            </div>
          ))
        ) : (
          <p style={{ margin: 0, color: "var(--ink-soft)" }}>No retrospectives yet.</p>
        )}
      </div>
    </div>
  );
}

"use client";

type SidebarItemView = {
  id: string;
  label: string;
  mode: string;
  path: string;
};

type AtlasModeControlsPanelProps = {
  cycleLabel: string;
  snapshotPending: boolean;
  cycleId: string;
  onCycleIdChange: (value: string) => void;
  ownerIdsInput: string;
  onOwnerIdsInputChange: (value: string) => void;
  mode: string;
  onModeChange: (mode: string) => void;
  sidebarItems: SidebarItemView[];
  lens: string;
  onLensChange: (lens: string) => void;
  parsedOwnerIdsError: string;
  cycleResolveError: string;
  snapshotError: string;
};

export default function AtlasModeControlsPanel({
  cycleLabel,
  snapshotPending,
  cycleId,
  onCycleIdChange,
  ownerIdsInput,
  onOwnerIdsInputChange,
  mode,
  onModeChange,
  sidebarItems,
  lens,
  onLensChange,
  parsedOwnerIdsError,
  cycleResolveError,
  snapshotError,
}: AtlasModeControlsPanelProps) {
  return (
    <section className="panel" style={{ marginBottom: "0.9rem", padding: "0.75rem 0.9rem" }}>
      <div style={{ fontSize: "0.82rem", color: "var(--ink-soft)" }}>
        Cycle: <strong>{cycleLabel}</strong>
        {snapshotPending ? " • Loading..." : " • Auto-sync every 45s"}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: "0.55rem",
          marginTop: "0.5rem",
        }}
      >
        <div>
          <label htmlFor="cycle-id" style={{ display: "block", fontSize: "0.76rem", color: "var(--ink-soft)" }}>
            Cycle ID
          </label>
          <input
            id="cycle-id"
            className="input"
            value={cycleId}
            onChange={(event) => onCycleIdChange(event.target.value.trim())}
            placeholder="e.g. 1"
            style={{ marginTop: "0.2rem" }}
          />
        </div>
        <div>
          <label htmlFor="owner-ids" style={{ display: "block", fontSize: "0.76rem", color: "var(--ink-soft)" }}>
            Owner IDs (optional)
          </label>
          <input
            id="owner-ids"
            className="input"
            value={ownerIdsInput}
            onChange={(event) => onOwnerIdsInputChange(event.target.value)}
            placeholder="e.g. 1,2,3"
            style={{ marginTop: "0.2rem" }}
          />
        </div>
        <div>
          <label htmlFor="mode" style={{ display: "block", fontSize: "0.76rem", color: "var(--ink-soft)" }}>
            Mode
          </label>
          <select
            id="mode"
            className="input"
            value={mode}
            onChange={(event) => onModeChange(event.target.value)}
            style={{ marginTop: "0.2rem" }}
          >
            {sidebarItems.map((item) => (
              <option key={`mode-${item.mode}`} value={item.mode}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="lens" style={{ display: "block", fontSize: "0.76rem", color: "var(--ink-soft)" }}>
            Lens
          </label>
          <select
            id="lens"
            className="input"
            value={lens}
            onChange={(event) => onLensChange(event.target.value)}
            style={{ marginTop: "0.2rem" }}
          >
            <option value="Scope">Scope</option>
            <option value="Branch">Branch</option>
          </select>
        </div>
      </div>
      {parsedOwnerIdsError ? (
        <p style={{ margin: "0.25rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {parsedOwnerIdsError}
        </p>
      ) : null}
      {cycleResolveError ? (
        <p style={{ margin: "0.25rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {cycleResolveError}
        </p>
      ) : null}
      {snapshotError ? (
        <p style={{ margin: "0.25rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {snapshotError}
        </p>
      ) : null}
    </section>
  );
}

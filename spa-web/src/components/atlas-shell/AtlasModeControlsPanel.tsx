"use client";

import { useMemo, useState } from "react";

type OwnerFilterOption = {
  id: number;
  label: string;
};

type CycleOption = {
  id: number;
  label: string;
};

type AtlasModeControlsPanelProps = {
  cycleLabel: string;
  snapshotPending: boolean;
  snapshotPollIntervalMs: number;
  cycleId: string;
  cycleOptions: CycleOption[];
  canManageCycleSelection: boolean;
  onCycleIdChange: (value: string) => void;
  ownerIdsInput: string;
  onOwnerIdsInputChange: (value: string) => void;
  canManageOwnerFilter: boolean;
  ownerFilterOptions: OwnerFilterOption[];
  selectedOwnerIds: number[];
  lens: string;
  onLensChange: (lens: string) => void;
  parsedOwnerIdsError: string;
  cycleResolveError: string;
  snapshotError: string;
};

export default function AtlasModeControlsPanel({
  cycleLabel,
  snapshotPending,
  snapshotPollIntervalMs,
  cycleId,
  cycleOptions,
  canManageCycleSelection,
  onCycleIdChange,
  ownerIdsInput,
  onOwnerIdsInputChange,
  canManageOwnerFilter,
  ownerFilterOptions,
  selectedOwnerIds,
  lens,
  onLensChange,
  parsedOwnerIdsError,
  cycleResolveError,
  snapshotError,
}: AtlasModeControlsPanelProps) {
  const [ownerSearchInput, setOwnerSearchInput] = useState("");
  const [ownerPickerError, setOwnerPickerError] = useState("");

  const ownerSuggestions = useMemo(() => {
    const query = ownerSearchInput.trim().toLowerCase();
    return ownerFilterOptions
      .filter((option) => !selectedOwnerIds.includes(option.id))
      .filter((option) => {
        if (!query) {
          return true;
        }
        return option.label.toLowerCase().includes(query) || String(option.id).includes(query);
      })
      .slice(0, 20);
  }, [ownerFilterOptions, ownerSearchInput, selectedOwnerIds]);

  const selectedOwnerPills = useMemo(() => {
    const labelById = new Map<number, string>();
    for (const option of ownerFilterOptions) {
      labelById.set(option.id, option.label);
    }
    return selectedOwnerIds.map((ownerId) => ({
      id: ownerId,
      label: labelById.get(ownerId) || "Unknown owner",
    }));
  }, [ownerFilterOptions, selectedOwnerIds]);

  const applyOwnerIds = (ids: number[]): void => {
    const next = Array.from(new Set(ids.filter((value) => Number.isFinite(value) && value > 0)));
    onOwnerIdsInputChange(next.join(","));
  };

  const addOwnerFilter = (): void => {
    const raw = ownerSearchInput.trim();
    if (!raw) {
      return;
    }
    const normalized = raw.toLowerCase();
    const matchesByName = ownerFilterOptions.filter((option) => option.label.toLowerCase() === normalized);
    let parsedId: number | null = null;
    if (matchesByName.length === 1) {
      parsedId = matchesByName[0].id;
    } else if (matchesByName.length > 1) {
      setOwnerPickerError("Multiple owners match that name. Refine the name and try again.");
      return;
    } else {
      const taggedMatch = raw.match(/#(\d+)\)$/);
      if (taggedMatch) {
        const fallbackParsed = Number.parseInt(taggedMatch[1], 10);
        parsedId = Number.isFinite(fallbackParsed) && fallbackParsed > 0 ? fallbackParsed : null;
      }
    }
    if (parsedId === null || !Number.isFinite(parsedId) || parsedId <= 0) {
      setOwnerPickerError("Select a valid owner from suggestions.");
      return;
    }
    const parsedOwnerId = parsedId;
    if (selectedOwnerIds.includes(parsedOwnerId)) {
      setOwnerPickerError("That owner is already in the filter.");
      return;
    }
    setOwnerPickerError("");
    applyOwnerIds([...selectedOwnerIds, parsedOwnerId]);
    setOwnerSearchInput("");
  };

  const removeOwnerFilter = (ownerId: number): void => {
    setOwnerPickerError("");
    applyOwnerIds(selectedOwnerIds.filter((id) => id !== ownerId));
  };

  const clearOwnerFilter = (): void => {
    setOwnerPickerError("");
    setOwnerSearchInput("");
    applyOwnerIds([]);
  };

  const pollSeconds = Math.max(1, Math.floor(snapshotPollIntervalMs / 1000));

  return (
    <section className="panel" style={{ marginBottom: "0.9rem", padding: "0.75rem 0.9rem" }}>
      <div style={{ fontSize: "0.82rem", color: "var(--ink-soft)" }}>
        Cycle: <strong>{cycleLabel}</strong>
        {snapshotPending ? " * Loading..." : ` * Auto-sync every ${pollSeconds}s`}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: canManageOwnerFilter ? "repeat(3, minmax(0, 1fr))" : "repeat(2, minmax(0, 1fr))",
          gap: "0.55rem",
          marginTop: "0.5rem",
        }}
      >
        <div>
          <label htmlFor="cycle-id" style={{ display: "block", fontSize: "0.76rem", color: "var(--ink-soft)" }}>
            Cycle
          </label>
          <select
            id="cycle-id"
            className="input"
            value={cycleId}
            onChange={(event) => onCycleIdChange(event.target.value)}
            disabled={!canManageCycleSelection}
            style={{ marginTop: "0.2rem" }}
          >
            <option value="">Select cycle</option>
            {cycleOptions.map((option) => (
              <option key={`cycle-option-${option.id}`} value={String(option.id)}>
                {option.label}
              </option>
            ))}
          </select>
          {!canManageCycleSelection ? (
            <p style={{ margin: "0.22rem 0 0", fontSize: "0.74rem", color: "var(--ink-soft)" }}>
              Cycle is managed by your manager/admin.
            </p>
          ) : null}
        </div>

        {canManageOwnerFilter ? (
          <div>
            <label htmlFor="owner-ids" style={{ display: "block", fontSize: "0.76rem", color: "var(--ink-soft)" }}>
              Owner Filter
            </label>
            <div style={{ display: "flex", gap: "0.35rem", marginTop: "0.2rem" }}>
              <input
                id="owner-ids"
                className="input"
                list="owner-filter-options"
                value={ownerSearchInput}
                onChange={(event) => {
                  setOwnerPickerError("");
                  setOwnerSearchInput(event.target.value);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addOwnerFilter();
                  }
                }}
                placeholder="Search by owner name"
              />
              <button className="primary-button" type="button" onClick={addOwnerFilter}>
                Add
              </button>
              <button className="primary-button" type="button" onClick={clearOwnerFilter} disabled={!ownerIdsInput.trim()}>
                Clear
              </button>
            </div>
            <datalist id="owner-filter-options">
              {ownerSuggestions.map((option) => (
                <option key={`owner-option-${option.id}`} value={option.label} />
              ))}
            </datalist>
            <p style={{ margin: "0.22rem 0 0", fontSize: "0.74rem", color: "var(--ink-soft)" }}>
              Leave empty to include all owners.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.28rem" }}>
              {selectedOwnerPills.length ? (
                selectedOwnerPills.map((owner) => (
                  <button
                    key={`owner-pill-${owner.id}`}
                    className="primary-button"
                    type="button"
                    onClick={() => removeOwnerFilter(owner.id)}
                    title={`Remove ${owner.label}`}
                    style={{ padding: "0.2rem 0.42rem", fontSize: "0.74rem" }}
                  >
                    {owner.label} x
                  </button>
                ))
              ) : (
                <span style={{ fontSize: "0.74rem", color: "var(--ink-soft)" }}>All owners</span>
              )}
            </div>
          </div>
        ) : null}

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
            <option value="focus">Focus</option>
            <option value="health">Health</option>
            <option value="owner">Owner</option>
          </select>
          <p style={{ margin: "0.22rem 0 0", fontSize: "0.74rem", color: "var(--ink-soft)" }}>
            Focus keeps hierarchy order. Health ranks riskier items first. Owner groups by owner.
          </p>
        </div>
      </div>
      {canManageOwnerFilter && parsedOwnerIdsError ? (
        <p style={{ margin: "0.25rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {parsedOwnerIdsError}
        </p>
      ) : null}
      {canManageOwnerFilter && ownerPickerError ? (
        <p style={{ margin: "0.25rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {ownerPickerError}
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

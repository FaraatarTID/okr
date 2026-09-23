import { act, render, screen } from "@testing-library/react";
import dynamic from "next/dynamic";
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";

import { ShellAccessGate } from "@/components/AtlasShell";

describe("ShellAccessGate", () => {
  it.each(["anonymous", "forced password change", "denied admin mode"])(
    "does not render protected chrome while access is closed for %s",
    () => {
      render(
        <ShellAccessGate accessReady={false}>
          <nav aria-label="Workspace navigation">Protected navigation</nav>
        </ShellAccessGate>,
      );

      expect(screen.queryByRole("navigation", { name: "Workspace navigation" })).toBeNull();
      expect(screen.getByRole("status")).toBeInTheDocument();
    },
  );

  it("renders protected chrome after the access decision allows the user", () => {
    render(
      <ShellAccessGate accessReady={true}>
        <nav aria-label="Workspace navigation">Protected navigation</nav>
      </ShellAccessGate>,
    );

    expect(screen.getByRole("navigation", { name: "Workspace navigation" })).toBeInTheDocument();
  });

  it("keeps shell navigation usable while a deferred panel chunk resolves", async () => {
    let resolvePanel: (module: { default: () => ReactElement }) => void = () => undefined;
    const panelModule = new Promise<{ default: () => ReactElement }>((resolve) => {
      resolvePanel = resolve;
    });
    const DeferredPanel = dynamic(() => panelModule, {
      loading: () => <div role="status">Loading panel chunk…</div>,
    });

    render(
      <ShellAccessGate accessReady={true}>
        <nav aria-label="Workspace navigation">
          <button type="button">Open another workspace mode</button>
        </nav>
        <DeferredPanel />
      </ShellAccessGate>,
    );

    expect(screen.getByRole("button", { name: "Open another workspace mode" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/loading panel chunk/i);

    await act(async () => {
      resolvePanel({ default: () => <section>Deferred timeline panel</section> });
      await panelModule;
    });

    expect(await screen.findByText("Deferred timeline panel")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open another workspace mode" })).toBeInTheDocument();
  });
});

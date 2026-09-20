import { createElement } from "react";
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ShellLayout from "@/app/(shell)/layout";

/**
 * Acceptance test for C8 (a): navigating between routes must not remount the
 * shell.
 *
 * The shell used to be rendered by each of the eight route files, so moving
 * between two routes unmounted one subtree and mounted another, re-running the
 * whole boot sequence (auth bootstrap, snapshot lifecycle, deep-link bootstrap)
 * and discarding all component state.
 *
 * `AtlasShell` is mocked so the count is exact and cheap: this asserts the
 * mounting structure, which is what changed. Rendering the real shell would
 * require 25 hook mocks and would test the shell's internals instead of where it
 * is mounted.
 *
 * How this maps onto real navigation: `ShellLayout` is the layout for the whole
 * `(shell)` group, and Next.js keeps a segment's layout mounted while swapping
 * only `children` when a sibling route is entered. Rendering the layout once and
 * changing its `children` prop is that same operation, so a second
 * `ShellLayout` render carrying a new route's children must not re-run the
 * shell's body.
 */

const shellState = vi.hoisted(() => ({ mounts: 0 }));

vi.mock("@/components/AtlasShell", () => ({
  default: function MockAtlasShell() {
    shellState.mounts += 1;
    return createElement("div", { "data-testid": "atlas-shell" });
  },
}));

function route(routePath: string) {
  return createElement("div", { "data-testid": "route", "data-route": routePath });
}

describe("(shell) layout owns the single shell mount", () => {
  it("adds no further shell mount as children change across navigations", () => {
    shellState.mounts = 0;

    const { rerender, getByTestId } = render(
      createElement(ShellLayout, null, route("/weekly")),
    );

    // Deliberately a delta, not an absolute count. React may invoke a component
    // body more than once per commit in the test environment (React 19 renders
    // the initial commit twice under these conditions), so any fixed baseline
    // like "exactly 1" asserts React's internals rather than this fix. The
    // property that matters is that entering another route adds nothing.
    const afterMount = shellState.mounts;
    expect(afterMount).toBeGreaterThanOrEqual(1);
    expect(getByTestId("atlas-shell")).toBeInTheDocument();

    // A navigation inside the group: same layout instance, new route children.
    rerender(createElement(ShellLayout, null, route("/timeline")));
    expect(shellState.mounts).toBe(afterMount);
    expect(getByTestId("route")).toHaveAttribute("data-route", "/timeline");

    // And again, to make sure the count is not merely lagging one render.
    rerender(createElement(ShellLayout, null, route("/admin")));
    rerender(createElement(ShellLayout, null, route("/daily")));
    expect(shellState.mounts).toBe(afterMount);
    expect(getByTestId("route")).toHaveAttribute("data-route", "/daily");
  });

  it("renders the shell as a sibling of the route children, not instead of them", () => {
    shellState.mounts = 0;

    const { container, getByTestId } = render(
      createElement(ShellLayout, null, route("/dashboard")),
    );

    expect(shellState.mounts).toBeGreaterThanOrEqual(1);
    expect(getByTestId("atlas-shell")).toBeInTheDocument();
    expect(getByTestId("route")).toBeInTheDocument();
    // The wrapper the routes used to provide is preserved for layout purposes.
    expect(container.querySelector(".spa-route-shell")).not.toBeNull();
  });
});

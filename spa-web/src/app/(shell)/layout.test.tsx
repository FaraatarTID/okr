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
 * `AtlasShell` is mocked so this stays cheap and asserts where the shell is
 * mounted rather than the shell's internals: rendering the real component would
 * need ~25 hook mocks. No other test in this repo renders the real shell, so the
 * mock changes nothing about existing coverage.
 *
 * How this maps onto real navigation: `ShellLayout` is the layout for the whole
 * `(shell)` group, and Next.js keeps a segment's layout mounted while swapping
 * only `children` when a sibling route is entered. Rendering the layout once and
 * changing its `children` prop is that same operation.
 *
 * The assertion is deliberately about the DOM node's identity rather than a
 * render count. An earlier version counted invocations of the mock and compared
 * an absolute number, then a delta; both were wrong, because React may invoke a
 * component body more than once per commit and the count is therefore not a
 * mount count. A remount destroys the old node and produces a new one, so
 * identity is exact evidence of "still mounted" regardless of how many times
 * React re-renders.
 */

vi.mock("@/components/AtlasShell", () => ({
  default: function MockAtlasShell() {
    return createElement("div", { "data-testid": "atlas-shell" });
  },
}));

function route(routePath: string) {
  return createElement("div", { "data-testid": "route", "data-route": routePath });
}

const shellNode = (container: HTMLElement): Element | null =>
  container.querySelector('[data-testid="atlas-shell"]');

describe("(shell) layout owns the single shell mount", () => {
  it("keeps the same shell node mounted while children change across navigations", () => {
    const { container, rerender, getByTestId } = render(
      createElement(ShellLayout, null, route("/weekly")),
    );

    const mountedShell = shellNode(container);
    expect(mountedShell).not.toBeNull();
    expect(getByTestId("route")).toHaveAttribute("data-route", "/weekly");

    // A navigation inside the group: same layout instance, new route children.
    // A remount would replace the shell element with a different one.
    rerender(createElement(ShellLayout, null, route("/timeline")));
    expect(shellNode(container)).toBe(mountedShell);
    expect(getByTestId("route")).toHaveAttribute("data-route", "/timeline");

    // And again, to make sure identity is not merely lagging one render.
    rerender(createElement(ShellLayout, null, route("/admin")));
    expect(shellNode(container)).toBe(mountedShell);

    rerender(createElement(ShellLayout, null, route("/daily")));
    expect(shellNode(container)).toBe(mountedShell);
    expect(getByTestId("route")).toHaveAttribute("data-route", "/daily");
  });

  it("renders exactly one shell, as a sibling of the route children", () => {
    const { container, getByTestId } = render(
      createElement(ShellLayout, null, route("/dashboard")),
    );

    expect(container.querySelectorAll('[data-testid="atlas-shell"]')).toHaveLength(1);
    expect(getByTestId("route")).toBeInTheDocument();
    // The wrapper the routes used to provide is preserved for layout purposes.
    expect(container.querySelector(".spa-route-shell")).not.toBeNull();
  });

  it("unmounts the shell when the layout itself unmounts", () => {
    // The counterpart to the identity check: proves the assertion above can
    // actually detect a remount rather than being vacuously true.
    const { container, unmount } = render(
      createElement(ShellLayout, null, route("/weekly")),
    );
    const before = shellNode(container);
    expect(before).not.toBeNull();

    unmount();
    expect(shellNode(container)).toBeNull();

    const { container: fresh } = render(
      createElement(ShellLayout, null, route("/weekly")),
    );
    expect(shellNode(fresh)).not.toBe(before);
  });
});

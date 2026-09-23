import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RootError from "@/app/error";
import ShellError from "@/app/(shell)/error";
import ShellLoading from "@/app/(shell)/loading";
import NotFound from "@/app/not-found";

describe("App Router recovery UI", () => {
  it("offers reset recovery for an application error", () => {
    const reset = vi.fn();
    render(<RootError error={new Error("shell failure")} reset={reset} />);

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(reset).toHaveBeenCalledOnce();
  });

  it("offers reset recovery for a shell page error", () => {
    const reset = vi.fn();
    render(<ShellError error={new Error("page failure")} reset={reset} />);

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(reset).toHaveBeenCalledOnce();
  });

  it("shows an accessible pending state for shell route transitions", () => {
    render(<ShellLoading />);

    expect(screen.getByRole("status")).toHaveTextContent(/loading workspace/i);
  });

  it("explains an unknown route and offers a home recovery path", () => {
    render(<NotFound />);

    expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go to workspace/i })).toHaveAttribute("href", "/");
  });
});

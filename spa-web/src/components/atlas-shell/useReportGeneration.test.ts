import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import * as jobPolling from "@/components/atlas-shell/jobPolling";
import useReportGeneration from "@/components/atlas-shell/useReportGeneration";

vi.mock("@/lib/api", () => ({
  readBackendQuery: vi.fn(),
  submitBackendJob: vi.fn(),
}));

vi.mock("@/components/atlas-shell/jobPolling", () => ({
  waitForBackendJobResult: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

describe("useReportGeneration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    if (!("createObjectURL" in URL)) {
      Object.defineProperty(URL, "createObjectURL", {
        value: () => "blob:test-url",
        writable: true,
        configurable: true,
      });
    }
    if (!("revokeObjectURL" in URL)) {
      Object.defineProperty(URL, "revokeObjectURL", {
        value: () => undefined,
        writable: true,
        configurable: true,
      });
    }
  });

  it("generates AI summary from successful async job result", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const submitBackendJobMock = vi.mocked(api.submitBackendJob);
    const waitForBackendJobResultMock = vi.mocked(jobPolling.waitForBackendJobResult);
    readBackendQueryMock.mockResolvedValue({
      work_logs: [{ id: 1, task: { title: "Task A" }, duration_minutes: 35, start_time: "2026-02-28T10:00:00Z" }],
    } as never);
    submitBackendJobMock.mockResolvedValue({ id: "job-1" } as never);
    waitForBackendJobResultMock.mockResolvedValue({
      status: "SUCCEEDED",
      result: {
        summary_markdown: "## Summary",
        highlights: ["Did work"],
        focus_analysis: "Mostly strategic.",
      },
    } as never);

    const { result } = renderHook(() =>
      useReportGeneration({
        user: baseUser,
        mode: "weekly",
        parsedCycleId: 7,
        formatOptionalDate: (value) => String(value || ""),
      }),
    );

    await act(async () => {
      await result.current.handleReportAiSummaryGenerate();
    });

    expect(submitBackendJobMock).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice", kind: "ai.generate_json" }),
    );
    await waitFor(() => expect(result.current.reportAiSummary?.summaryMarkdown).toContain("Summary"));
    expect(result.current.reportAiError).toBe("");
  });

  it("exports html report without using async job backend", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const submitBackendJobMock = vi.mocked(api.submitBackendJob);
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:test-report");
    const revokeObjectUrlSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    readBackendQueryMock.mockResolvedValue({
      work_logs: [{ id: 1, task: { title: "Task A" }, duration_minutes: 20, start_time: "2026-02-28T09:00:00Z" }],
    } as never);

    const { result } = renderHook(() =>
      useReportGeneration({
        user: baseUser,
        mode: "daily",
        parsedCycleId: 7,
        formatOptionalDate: (value) => String(value || ""),
      }),
    );

    await act(async () => {
      await result.current.handleReportExport("html");
    });

    expect(readBackendQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "work_logs.by_range" }),
    );
    expect(submitBackendJobMock).not.toHaveBeenCalled();
    expect(createObjectUrlSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalled();
    expect(result.current.reportExportError).toBe("");
  });

  it("falls back to html and sets error when pdf payload is unavailable", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const submitBackendJobMock = vi.mocked(api.submitBackendJob);
    const waitForBackendJobResultMock = vi.mocked(jobPolling.waitForBackendJobResult);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test-report");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    readBackendQueryMock.mockResolvedValue({
      work_logs: [{ id: 1, task: { title: "Task A" }, duration_minutes: 45, start_time: "2026-02-28T09:00:00Z" }],
    } as never);
    submitBackendJobMock.mockResolvedValue({ id: "job-pdf" } as never);
    waitForBackendJobResultMock.mockResolvedValue({
      status: "SUCCEEDED",
      result: {},
      error_text: "PDF backend unavailable",
    } as never);

    const { result } = renderHook(() =>
      useReportGeneration({
        user: baseUser,
        mode: "weekly",
        parsedCycleId: 7,
        formatOptionalDate: (value) => String(value || ""),
      }),
    );

    await act(async () => {
      await result.current.handleReportExport("pdf");
    });

    expect(waitForBackendJobResultMock).toHaveBeenCalledWith(baseUser, "job-pdf");
    expect(result.current.reportExportError).toContain("PDF backend unavailable");
  });
});

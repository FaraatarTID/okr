"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  readBackendQuery,
  submitBackendJob,
  type AuthUser,
} from "@/lib/api";
import {
  parseReportAiSummary,
  type ReportAiSummaryView,
} from "@/components/atlas-shell/shellAnalyticsUtils";
import { waitForBackendJobResult } from "@/components/atlas-shell/jobPolling";

type WorkLogRead = {
  id: number;
  task_id?: number | null;
  duration_minutes?: number | null;
  start_time?: string | null;
  summary?: string | null;
  task?: { title?: string | null } | null;
};

type UseReportGenerationInput = {
  user: AuthUser | null;
  mode: string;
  parsedCycleId: number | null;
  formatOptionalDate: (value: unknown) => string;
};

function triggerDownloadFromBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function buildSimpleReportHtml(
  logs: WorkLogRead[],
  title: string,
  formatOptionalDate: (value: unknown) => string,
): string {
  const rows = logs
    .map((log) => {
      const task = String(log.task?.title || `Task #${log.task_id || "-"}`);
      const duration = Math.round(Number(log.duration_minutes || 0));
      const started = String(formatOptionalDate(log.start_time));
      const summary = String(log.summary || "-");
      return `<tr><td>${task}</td><td>${duration}</td><td>${started}</td><td>${summary}</td></tr>`;
    })
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title></head><body><h2>${title}</h2><table border="1" cellspacing="0" cellpadding="6"><thead><tr><th>Task</th><th>Minutes</th><th>Start</th><th>Summary</th></tr></thead><tbody>${rows}</tbody></table></body></html>`;
}

export default function useReportGeneration({
  user,
  mode,
  parsedCycleId,
  formatOptionalDate,
}: UseReportGenerationInput) {
  const [reportExportPending, setReportExportPending] = useState(false);
  const [reportExportError, setReportExportError] = useState("");
  const [reportAiPending, setReportAiPending] = useState(false);
  const [reportAiError, setReportAiError] = useState("");
  const [reportAiSummary, setReportAiSummary] = useState<ReportAiSummaryView | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    setReportAiSummary(null);
    setReportAiError("");
  }, [parsedCycleId]);

  useEffect(() => {
    if (mode !== "weekly" && mode !== "daily") {
      setReportAiSummary(null);
      setReportAiError("");
    }
  }, [mode]);

  const handleReportExport = useCallback(
    async (format: "pdf" | "html"): Promise<void> => {
      if (!user) {
        return;
      }
      setReportExportPending(true);
      setReportExportError("");
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const now = new Date();
        const start = new Date(now);
        if (mode === "daily") {
          start.setHours(0, 0, 0, 0);
        } else {
          start.setDate(start.getDate() - 6);
          start.setHours(0, 0, 0, 0);
        }
        const end = new Date(now);
        end.setHours(23, 59, 59, 999);
        const logPayload = await readBackendQuery({
          actor_username: user.username,
          kind: "work_logs.by_range",
          params: {
            user_id: user.id,
            start_date: start.toISOString(),
            end_date: end.toISOString(),
          },
        });
        const logs = ((logPayload.work_logs as WorkLogRead[]) || []).slice(0, 500);
        const reportItems = logs.map((log) => ({
          Task: String(log.task?.title || `Task #${log.task_id || "-"}`),
          "Duration (m)": Math.round(Number(log.duration_minutes || 0)),
          Date: String(log.start_time || ""),
          Time: String(log.start_time || ""),
          Summary: String(log.summary || ""),
          Objective: "-",
          KeyResult: "-",
        }));
        const objectiveStats: Record<string, number> = {};
        const totalTime = `${Math.round(logs.reduce((sum, row) => sum + Number(row.duration_minutes || 0), 0))} min`;
        const fileStamp = new Date().toISOString().slice(0, 10);
        const reportTitle = mode === "daily" ? "Daily Work Report" : "Weekly Work Report";
        if (format === "html") {
          const html = buildSimpleReportHtml(logs, reportTitle, formatOptionalDate);
          triggerDownloadFromBlob(new Blob([html], { type: "text/html" }), `${mode}_report_${fileStamp}.html`);
          return;
        }

        const submitted = await submitBackendJob({
          actor_username: user.username,
          kind: "pdf.weekly",
          payload: {
            report_items: reportItems,
            objective_stats: objectiveStats,
            total_time_str: totalTime,
            key_results: [],
            direction: "LTR",
            title: reportTitle,
            time_label: mode === "daily" ? "Today" : "Last 7 Days",
            report_summary: "",
            achievements: [],
          },
        });
        const done = await waitForBackendJobResult(user, submitted.id, { signal: controller.signal });
        const resultPayload = done.result || {};
        const encoded = String((resultPayload as Record<string, unknown>).content_b64 || "");
        if (!encoded) {
          const fallbackHtml = buildSimpleReportHtml(logs, reportTitle, formatOptionalDate);
          triggerDownloadFromBlob(new Blob([fallbackHtml], { type: "text/html" }), `${mode}_report_${fileStamp}.html`);
          setReportExportError(String(done.error_text || "PDF export unavailable; downloaded HTML fallback."));
          return;
        }
        const binary = atob(encoded);
        const bytes = new Uint8Array(binary.length);
        for (let idx = 0; idx < binary.length; idx += 1) {
          bytes[idx] = binary.charCodeAt(idx);
        }
        triggerDownloadFromBlob(new Blob([bytes], { type: "application/pdf" }), `${mode}_report_${fileStamp}.pdf`);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setReportExportError(String(error instanceof Error ? error.message : error));
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setReportExportPending(false);
      }
    },
    [formatOptionalDate, mode, user],
  );

  const handleReportAiSummaryGenerate = useCallback(async (): Promise<void> => {
    if (!user) {
      return;
    }
    setReportAiPending(true);
    setReportAiError("");
    setReportAiSummary(null);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const now = new Date();
      const start = new Date(now);
      if (mode === "daily") {
        start.setHours(0, 0, 0, 0);
      } else {
        start.setDate(start.getDate() - 6);
        start.setHours(0, 0, 0, 0);
      }
      const end = new Date(now);
      end.setHours(23, 59, 59, 999);
      const logPayload = await readBackendQuery({
        actor_username: user.username,
        kind: "work_logs.by_range",
        params: {
          user_id: user.id,
          start_date: start.toISOString(),
          end_date: end.toISOString(),
        },
      });
      const logs = ((logPayload.work_logs as WorkLogRead[]) || []).slice(0, 300);
      const normalizedLogs = logs.map((log) => ({
        task: String(log.task?.title || `Task #${log.task_id || "-"}`),
        duration_minutes: Math.round(Number(log.duration_minutes || 0)),
        start_time: log.start_time || null,
        summary: String(log.summary || "").trim(),
      }));
      const totalMinutes = Math.round(
        normalizedLogs.reduce((sum, row) => sum + Number(row.duration_minutes || 0), 0),
      );
      const prompt = [
        "Return strict JSON only with keys: summary_markdown, highlights, focus_analysis.",
        "summary_markdown should be a concise executive summary in markdown.",
        "highlights should be an array of 3-7 short bullet points.",
        "focus_analysis should be one sentence about strategic vs tactical focus.",
        `report_mode=${mode}`,
        `window_start=${start.toISOString()}`,
        `window_end=${end.toISOString()}`,
        `total_minutes=${totalMinutes}`,
        `logs=${JSON.stringify(normalizedLogs)}`,
      ].join("\n");
      const submitted = await submitBackendJob({
        actor_username: user.username,
        kind: "ai.generate_json",
        payload: { prompt },
      });
      const done = await waitForBackendJobResult(user, submitted.id, { signal: controller.signal });
      if (String(done.status || "").toLowerCase() !== "succeeded") {
        throw new Error(String(done.error_text || "AI report summary generation failed."));
      }
      const summary = parseReportAiSummary(done.result || {});
      if (!summary.summaryMarkdown && !summary.highlights.length && !summary.focusAnalysis) {
        throw new Error("AI response did not contain a usable report summary payload.");
      }
      setReportAiSummary(summary);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setReportAiError(String(error instanceof Error ? error.message : error));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
      setReportAiPending(false);
    }
  }, [mode, user]);

  return {
    reportExportPending,
    reportExportError,
    reportAiPending,
    reportAiError,
    reportAiSummary,
    handleReportExport,
    handleReportAiSummaryGenerate,
  };
}

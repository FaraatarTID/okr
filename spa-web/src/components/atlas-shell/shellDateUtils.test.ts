import { describe, expect, it } from "vitest";

import {
  endOfWeekIso,
  formatElapsedClock,
  formatOptionalDate,
  formatOptionalNumber,
  parseDateOrNull,
  reviewWindow,
  startOfWeekIso,
  toDateInputValue,
  toIsoEnd,
  toIsoStart,
} from "@/components/atlas-shell/shellDateUtils";

describe("shellDateUtils", () => {
  it("normalizes backend datetime strings to UTC", () => {
    expect(parseDateOrNull("2026-01-05 09:00:00")?.toISOString()).toBe("2026-01-05T09:00:00.000Z");
    expect(parseDateOrNull("2026-01-05T09:00:00.987654")?.toISOString()).toBe(
      "2026-01-05T09:00:00.987Z",
    );
    expect(parseDateOrNull("2026-01-05T09:00:00+02:00")?.toISOString()).toBe("2026-01-05T07:00:00.000Z");
    expect(parseDateOrNull("not-a-date")).toBeNull();
  });

  it("formats optional values safely", () => {
    expect(formatOptionalNumber(12.5)).toBe("12.5");
    expect(formatOptionalNumber("12")).toBe("-");
    expect(formatOptionalDate("")).toBe("-");
    expect(formatOptionalDate("not-a-date")).toBe("not-a-date");
  });

  it("builds date-input and ISO boundary values", () => {
    expect(toDateInputValue("2026-02-01T14:00:00Z")).toBe("2026-02-01");
    expect(toDateInputValue("bad")).toBe("");
    expect(toIsoStart("2026-02-01")).toBe("2026-02-01T00:00:00Z");
    expect(toIsoEnd("2026-02-01")).toBe("2026-02-01T23:59:59Z");
  });

  it("produces week boundaries using Monday as start", () => {
    const sunday = new Date("2026-01-04T12:00:00Z");
    expect(startOfWeekIso(sunday)).toBe("2025-12-29");
    expect(endOfWeekIso(sunday)).toBe("2026-01-04");

    const thursday = new Date("2026-01-08T12:00:00Z");
    expect(startOfWeekIso(thursday)).toBe("2026-01-05");
    expect(endOfWeekIso(thursday)).toBe("2026-01-11");
  });

  it("formats elapsed clock values with zero padding", () => {
    expect(formatElapsedClock(0)).toBe("00:00:00");
    expect(formatElapsedClock(65)).toBe("00:01:05");
    expect(formatElapsedClock(3661)).toBe("01:01:01");
    expect(formatElapsedClock(-5)).toBe("00:00:00");
  });

  it("returns a bounded review window with day boundaries", () => {
    const window = reviewWindow();
    expect(window.start.getTime()).toBeLessThan(window.end.getTime());
    expect(window.start.getHours()).toBe(0);
    expect(window.start.getMinutes()).toBe(0);
    expect(window.end.getHours()).toBe(23);
    expect(window.end.getMinutes()).toBe(59);
  });
});

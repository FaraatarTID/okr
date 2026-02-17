# Atlas AI Features Guide (English)

Documentation HQ: [README](../README.md)

This guide explains how to use Atlas AI features correctly so results are reliable and actionable.

---

## 1) Why this guide matters

AI is powerful here, but output quality depends on operation quality.

If you run AI features with clear scope, safe controls, and a review step, you get:
- better prioritization
- fewer false jumps in progress
- more trust in map indicators (`Needs care`, `On track`, `Complete`)

If you skip those controls, output quality drops.

---

## 2) AI capabilities in Atlas

1. `AI Strategic Analysis` on Key Results:
- Generates KR-level analysis (scores, warnings, suggestions).

2. `AI Progress Sync` in Atlas map sidebar:
- Refreshes AI analysis for KRs in current map scope.
- Can also update KR progress from AI overall score (optional and controlled).

3. `AI Suggested Next`:
- Recommends one next critical task from in-scope candidates.

4. Health explainability:
- Map hover includes `Why: ...`.
- Focus and Inspector show status rationale text.

5. Admin-only diagnostics:
- `Show Health Debug` exposes the rule source and health state table.

---

## 3) What determines map health indicators

Map labels (`Needs care`, `On track`, `Complete`) are rule-driven and explainable:

1. For `KEY_RESULT`:
- AI deadline warnings have highest priority.
- AI overall score is next.
- Then standard status/progress rules.

2. For `TASK` and non-KR nodes:
- Task workflow/deadline/progress rules.
- Parent nodes can inherit `Needs care` from children.

Use the rationale text to validate why a node got its status.

---

## 4) AI Progress Sync: safest operating flow

Recommended sequence every time:

1. Set map scope/lens first.
2. Enable `Apply AI overall score to KR progress` only if you want KR progress changes.
3. Turn on `Preview mode (no writes)` first.
4. Set `Max KR progress delta` (start conservative, e.g. `15-25`).
5. Keep `Allow progress decreases` off unless you intentionally want downward corrections.
6. Run `AI Progress Sync`.
7. Review `Last AI Sync Details`.
8. If output looks correct, rerun with preview off.

---

## 5) Control panel semantics (important)

1. `Preview mode (no writes)`:
- Runs full analysis and decisions.
- Does not write analysis/progress to DB.

2. `Max KR progress delta`:
- Limits allowed progress change per KR in one run.
- Large jumps are blocked and reported.

3. `Allow progress decreases`:
- If off, any AI proposal lower than current progress is blocked.

4. `Undo Last AI Progress Apply`:
- Reverts last applied KR progress batch (time-limited window).
- Use immediately if a run applied undesired changes.

5. `Last AI Sync Details` table:
- Shows `Current`, `AI Score`, `Proposed`, `Delta`, `Action`, `Reason`.
- This is your operational audit trail for each run.

---

## 6) Role-based best practice

1. Member:
- Use AI to choose focus, not to bypass task-level judgment.

2. Manager:
- Use preview-first policy before cross-team progress updates.
- Review blocked/skipped reasons before rerun.

3. Admin:
- Define a default policy for your org (delta cap, decrease policy, cadence).
- Keep `Show Health Debug` for diagnostics only.

---

## 7) Common mistakes to avoid

1. Running with broad scope + apply-on without preview.
2. Setting very high delta caps without review.
3. Treating AI suggestion as mandatory instead of decision support.
4. Ignoring blocked/skipped reasons in sync details.

---

## 8) Quick cadence recommendation

1. Daily:
- Use `AI Suggested Next` for focus selection.

2. Mid-week:
- Run preview sync for correction.

3. End of week:
- Run final sync with controlled apply policy, then review reports/retro.

---

## 9) Troubleshooting

1. AI output missing:
- Verify Gemini API key and service availability.
- Narrow scope and retry.

2. Unexpected progress outcomes:
- Check `Last AI Sync Details` reasons.
- Use undo if needed, then rerun with stricter policy.

3. Health label seems wrong:
- Read `Why this status` / `Status rationale`.
- Admin can open `Show Health Debug` for source-level verification.


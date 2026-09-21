# Learning Loop
Documentation HQ: [README](../README.md)

Single source of truth for the Learning Loop user workflow. Keep EN and FA sections in sync in the same PR.

## EN

### Purpose
The Learning Loop turns weekly KR updates into controlled improvement:
- Every check-in must classify variation with `VariationType`.
- `COMMON_CAUSE` updates can link to an active `Experiment`.
- `SPECIAL_CAUSE` updates require a short note and cannot link to experiments.
- Weekly retro decisions close experiments and persist institutional outcomes.

### Weekly Check-In Flow

#### Step 1: Review Week
- Open Weekly Check-In and go to `Step 1 (Review Week)`.
- Use the `Experiments Reviewed This Week` section to review:
  - experiments with `ExperimentStatus.RUNNING`, and
  - experiments that ended in this retro window.
- Record one decision per experiment (`ADOPT`, `REVERT`, `ITERATE`, `UNKNOWN`) with optional rationale.
- On submit, each chosen decision:
  - writes/updates `RetroExperimentOutcome`, and
  - closes the experiment to `ExperimentStatus.DECIDED` via `close_experiment`.

#### Step 2: Update KRs
- Open `Step 2 (Update KRs)`.
- For each KR check-in, variation classification is required:
  - choose `Common Cause` or `Special Cause` (mapped to `VariationType`).
- `Common Cause` path:
  - optionally link a RUNNING experiment, or
  - create one inline via `Start New Experiment`.
- Inline create path:
  - `Common Cause -> Start New Experiment`
  - fill hypothesis + change description (+ optional expected direction/size)
  - submit to create experiment, then it is set to `ExperimentStatus.RUNNING`.
- `Special Cause` path:
  - enter `special_cause_note` (minimum 5 chars),
  - experiment link is not allowed and is cleared.

#### Step 3: Plan Next Week
- Complete planning priorities as usual.
- This step does not create or close experiments directly.

### Troubleshooting

#### No experiments to review this week
If `Step 1` shows `No experiments to review this week`:
- Create experiments from `Step 2` under `Common Cause -> Start New Experiment`.
- Confirm listing rule:
  - all `RUNNING` experiments appear, and
  - experiments with `end_at` inside the current retro window appear.
- If you only logged `SPECIAL_CAUSE` check-ins this week, no new experiment will be created.

### Glossary
| Product Term |
|---|
| Common Cause |
| Special Cause |
| Experiment |
| Decision |
| Retro Outcome |

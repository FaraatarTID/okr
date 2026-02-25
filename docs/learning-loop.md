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
| Product Term | Persian Standard |
|---|---|
| Common Cause | Ø¹Ù„Øª Ù…Ø´ØªØ±Ú© |
| Special Cause | Ø¹Ù„Øª ÙˆÛŒÚ˜Ù‡ |
| Experiment | Ø¢Ø²Ù…Ø§ÛŒØ´ |
| Decision | ØªØµÙ…ÛŒÙ… |
| Retro Outcome | Ø®Ø±ÙˆØ¬ÛŒ Ø¨Ø§Ø²Ù†Ú¯Ø±ÛŒ |

## FA

### Purpose
Learning Loop Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù‡ÙØªÚ¯ÛŒ KR Ø±Ø§ Ø¨Ù‡ Ú†Ø±Ø®Ù‡ Ø¨Ù‡Ø¨ÙˆØ¯ Ú©Ù†ØªØ±Ù„â€ŒØ´Ø¯Ù‡ ØªØ¨Ø¯ÛŒÙ„ Ù…ÛŒâ€ŒÚ©Ù†Ø¯:
- Ù‡Ø± check-in Ø¨Ø§ÛŒØ¯ Ù†ÙˆØ¹ ØªØºÛŒÛŒØ± Ø±Ø§ Ø¨Ø§ `VariationType` Ù…Ø´Ø®Øµ Ú©Ù†Ø¯.
- Ø¯Ø± `COMMON_CAUSE` Ù…ÛŒâ€ŒØªÙˆØ§Ù† check-in Ø±Ø§ Ø¨Ù‡ `Experiment` ÙØ¹Ø§Ù„ Ù…ØªØµÙ„ Ú©Ø±Ø¯.
- Ø¯Ø± `SPECIAL_CAUSE` Ø«Ø¨Øª ØªÙˆØ¶ÛŒØ­ Ú©ÙˆØªØ§Ù‡ Ø§Ø¬Ø¨Ø§Ø±ÛŒ Ø§Ø³Øª Ùˆ Ø§ØªØµØ§Ù„ Ø¨Ù‡ experiment Ù…Ø¬Ø§Ø² Ù†ÛŒØ³Øª.
- ØªØµÙ…ÛŒÙ…â€ŒÙ‡Ø§ÛŒ Ø¨Ø§Ø²Ù†Ú¯Ø±ÛŒ Ù‡ÙØªÚ¯ÛŒØŒ experiment Ø±Ø§ Ù…ÛŒâ€ŒØ¨Ù†Ø¯Ù†Ø¯ Ùˆ Ø®Ø±ÙˆØ¬ÛŒ Ø³Ø§Ø²Ù…Ø§Ù†ÛŒ Ø±Ø§ Ø«Ø¨Øª Ù…ÛŒâ€ŒÚ©Ù†Ù†Ø¯.

### Weekly Check-In Flow

#### Step 1: Review Week
- Weekly Check-In Ø±Ø§ Ø¨Ø§Ø² Ú©Ù†ÛŒØ¯ Ùˆ Ø¨Ù‡ `Step 1 (Review Week)` Ø¨Ø±ÙˆÛŒØ¯.
- Ø¯Ø± Ø¨Ø®Ø´ `Experiments Reviewed This Week` Ø§ÛŒÙ† Ù…ÙˆØ§Ø±Ø¯ Ø±Ø§ Ø¨Ø±Ø±Ø³ÛŒ Ú©Ù†ÛŒØ¯:
  - experimentÙ‡Ø§ÛŒÛŒ Ø¨Ø§ `ExperimentStatus.RUNNING`
  - experimentÙ‡Ø§ÛŒÛŒ Ú©Ù‡ Ø¯Ø± Ø¨Ø§Ø²Ù‡ Ù‡Ù…ÛŒÙ† retro ØªÙ…Ø§Ù… Ø´Ø¯Ù‡â€ŒØ§Ù†Ø¯.
- Ø¨Ø±Ø§ÛŒ Ù‡Ø± experiment ÛŒÚ© ØªØµÙ…ÛŒÙ… Ø«Ø¨Øª Ú©Ù†ÛŒØ¯ (`ADOPT`ØŒ `REVERT`ØŒ `ITERATE`ØŒ `UNKNOWN`) Ùˆ Ø¯Ø± ØµÙˆØ±Øª Ù†ÛŒØ§Ø² rationale Ø¨Ù†ÙˆÛŒØ³ÛŒØ¯.
- Ù‡Ù†Ú¯Ø§Ù… submitØŒ Ù‡Ø± ØªØµÙ…ÛŒÙ… Ø§Ù†ØªØ®Ø§Ø¨â€ŒØ´Ø¯Ù‡:
  - Ø¯Ø± `RetroExperimentOutcome` Ø«Ø¨Øª/Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù…ÛŒâ€ŒØ´ÙˆØ¯ØŒ
  - Ùˆ experiment Ø¨Ø§ `close_experiment` Ø¨Ù‡ `ExperimentStatus.DECIDED` Ø¨Ø³ØªÙ‡ Ù…ÛŒâ€ŒØ´ÙˆØ¯.

#### Step 2: Update KRs
- ÙˆØ§Ø±Ø¯ `Step 2 (Update KRs)` Ø´ÙˆÛŒØ¯.
- Ø¨Ø±Ø§ÛŒ Ù‡Ø± check-in Ø±ÙˆÛŒ KRØŒ Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒ ØªØºÛŒÛŒØ± Ø§Ø¬Ø¨Ø§Ø±ÛŒ Ø§Ø³Øª:
  - `Common Cause` ÛŒØ§ `Special Cause` (Ù†Ú¯Ø§Ø´Øª Ø¨Ù‡ `VariationType`).
- Ù…Ø³ÛŒØ± `Common Cause`:
  - Ø§ØªØµØ§Ù„ Ø§Ø®ØªÛŒØ§Ø±ÛŒ Ø¨Ù‡ experiment ÙØ¹Ø§Ù„ (`RUNNING`)ØŒ ÛŒØ§
  - Ø³Ø§Ø®Øª experiment Ø¬Ø¯ÛŒØ¯ Ø¨Ù‡â€ŒØµÙˆØ±Øª inline Ø¨Ø§ `Start New Experiment`.
- Ù…Ø³ÛŒØ± Ø³Ø§Ø®Øª inline:
  - `Common Cause -> Start New Experiment`
  - ÙÛŒÙ„Ø¯Ù‡Ø§ÛŒ hypothesis Ùˆ change description (Ø¨Ù‡â€ŒÙ‡Ù…Ø±Ø§Ù‡ expected direction/size Ø¯Ø± ØµÙˆØ±Øª Ù†ÛŒØ§Ø²) Ø±Ø§ Ù¾Ø± Ú©Ù†ÛŒØ¯
  - Ø¨Ø§ submitØŒ experiment Ø³Ø§Ø®ØªÙ‡ Ù…ÛŒâ€ŒØ´ÙˆØ¯ Ùˆ Ø³Ù¾Ø³ Ø¨Ù‡ `ExperimentStatus.RUNNING` Ù…ÛŒâ€ŒØ±ÙˆØ¯.
- Ù…Ø³ÛŒØ± `Special Cause`:
  - Ù…Ù‚Ø¯Ø§Ø± `special_cause_note` (Ø­Ø¯Ø§Ù‚Ù„ Ûµ Ú©Ø§Ø±Ø§Ú©ØªØ±) Ø§Ù„Ø²Ø§Ù…ÛŒ Ø§Ø³ØªØŒ
  - Ù„ÛŒÙ†Ú© experiment Ù…Ø¬Ø§Ø² Ù†ÛŒØ³Øª Ùˆ Ù¾Ø§Ú© Ù…ÛŒâ€ŒØ´ÙˆØ¯.

#### Step 3: Plan Next Week
- Ø§ÙˆÙ„ÙˆÛŒØªâ€ŒÙ‡Ø§ÛŒ Ù‡ÙØªÙ‡ Ø¨Ø¹Ø¯ Ø±Ø§ Ø·Ø¨Ù‚ Ø±ÙˆØ§Ù„ Ù…Ø¹Ù…ÙˆÙ„ Ø«Ø¨Øª Ú©Ù†ÛŒØ¯.
- Ø§ÛŒÙ† Ù…Ø±Ø­Ù„Ù‡ Ù…Ø³ØªÙ‚ÛŒÙ…Ø§ experiment Ø§ÛŒØ¬Ø§Ø¯ ÛŒØ§ Ø¨Ø³ØªÙ‡ Ù†Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

### Troubleshooting

#### No experiments to review this week
Ø§Ú¯Ø± Ø¯Ø± `Step 1` Ù¾ÛŒØ§Ù… `No experiments to review this week` Ù…ÛŒâ€ŒØ¨ÛŒÙ†ÛŒØ¯:
- experiment Ø±Ø§ Ø§Ø² `Step 2` Ø¯Ø± Ù…Ø³ÛŒØ± `Common Cause -> Start New Experiment` Ø¨Ø³Ø§Ø²ÛŒØ¯.
- Ù‚Ø§Ù†ÙˆÙ† Ù„ÛŒØ³Øª Ø±Ø§ Ø¨Ø±Ø±Ø³ÛŒ Ú©Ù†ÛŒØ¯:
  - Ù‡Ù…Ù‡ experimentÙ‡Ø§ÛŒ `RUNNING` Ù†Ù…Ø§ÛŒØ´ Ø¯Ø§Ø¯Ù‡ Ù…ÛŒâ€ŒØ´ÙˆÙ†Ø¯ØŒ
  - experimentÙ‡Ø§ÛŒÛŒ Ú©Ù‡ `end_at` Ø¢Ù†â€ŒÙ‡Ø§ Ø¯Ø§Ø®Ù„ Ø¨Ø§Ø²Ù‡ retro ÙØ¹Ù„ÛŒ Ø§Ø³Øª Ù†ÛŒØ² Ù†Ù…Ø§ÛŒØ´ Ø¯Ø§Ø¯Ù‡ Ù…ÛŒâ€ŒØ´ÙˆÙ†Ø¯.
- Ø§Ú¯Ø± Ø§ÛŒÙ† Ù‡ÙØªÙ‡ ÙÙ‚Ø· `SPECIAL_CAUSE` Ø«Ø¨Øª Ú©Ø±Ø¯Ù‡ Ø¨Ø§Ø´ÛŒØ¯ØŒ experiment Ø¬Ø¯ÛŒØ¯ÛŒ Ø³Ø§Ø®ØªÙ‡ Ù†Ù…ÛŒâ€ŒØ´ÙˆØ¯.

### Glossary
Ø§Ø² Ù‡Ù…Ø§Ù† Ø¬Ø¯ÙˆÙ„ ÙˆØ§Ú˜Ú¯Ø§Ù† Ù…Ø´ØªØ±Ú© EN/FA Ø¯Ø± Ø¨Ø®Ø´ EN Ø§Ø³ØªÙØ§Ø¯Ù‡ Ú©Ù†ÛŒØ¯ ØªØ§ ØªØ±Ø¬Ù…Ù‡ Ø§ØµØ·Ù„Ø§Ø­Ø§Øª ØªÛŒÙ… Ø«Ø§Ø¨Øª Ø¨Ù…Ø§Ù†Ø¯.


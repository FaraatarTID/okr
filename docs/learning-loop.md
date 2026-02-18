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

### Weekly Ritual Flow

#### Step 1: Review Week
- Open Weekly Ritual and go to `Step 1 (Review Week)`.
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
| Common Cause | علت مشترک |
| Special Cause | علت ویژه |
| Experiment | آزمایش |
| Decision | تصمیم |
| Retro Outcome | خروجی بازنگری |

## FA

### Purpose
Learning Loop به‌روزرسانی هفتگی KR را به چرخه بهبود کنترل‌شده تبدیل می‌کند:
- هر check-in باید نوع تغییر را با `VariationType` مشخص کند.
- در `COMMON_CAUSE` می‌توان check-in را به `Experiment` فعال متصل کرد.
- در `SPECIAL_CAUSE` ثبت توضیح کوتاه اجباری است و اتصال به experiment مجاز نیست.
- تصمیم‌های بازنگری هفتگی، experiment را می‌بندند و خروجی سازمانی را ثبت می‌کنند.

### Weekly Ritual Flow

#### Step 1: Review Week
- Weekly Ritual را باز کنید و به `Step 1 (Review Week)` بروید.
- در بخش `Experiments Reviewed This Week` این موارد را بررسی کنید:
  - experimentهایی با `ExperimentStatus.RUNNING`
  - experimentهایی که در بازه همین retro تمام شده‌اند.
- برای هر experiment یک تصمیم ثبت کنید (`ADOPT`، `REVERT`، `ITERATE`، `UNKNOWN`) و در صورت نیاز rationale بنویسید.
- هنگام submit، هر تصمیم انتخاب‌شده:
  - در `RetroExperimentOutcome` ثبت/به‌روزرسانی می‌شود،
  - و experiment با `close_experiment` به `ExperimentStatus.DECIDED` بسته می‌شود.

#### Step 2: Update KRs
- وارد `Step 2 (Update KRs)` شوید.
- برای هر check-in روی KR، دسته‌بندی تغییر اجباری است:
  - `Common Cause` یا `Special Cause` (نگاشت به `VariationType`).
- مسیر `Common Cause`:
  - اتصال اختیاری به experiment فعال (`RUNNING`)، یا
  - ساخت experiment جدید به‌صورت inline با `Start New Experiment`.
- مسیر ساخت inline:
  - `Common Cause -> Start New Experiment`
  - فیلدهای hypothesis و change description (به‌همراه expected direction/size در صورت نیاز) را پر کنید
  - با submit، experiment ساخته می‌شود و سپس به `ExperimentStatus.RUNNING` می‌رود.
- مسیر `Special Cause`:
  - مقدار `special_cause_note` (حداقل ۵ کاراکتر) الزامی است،
  - لینک experiment مجاز نیست و پاک می‌شود.

#### Step 3: Plan Next Week
- اولویت‌های هفته بعد را طبق روال معمول ثبت کنید.
- این مرحله مستقیما experiment ایجاد یا بسته نمی‌کند.

### Troubleshooting

#### No experiments to review this week
اگر در `Step 1` پیام `No experiments to review this week` می‌بینید:
- experiment را از `Step 2` در مسیر `Common Cause -> Start New Experiment` بسازید.
- قانون لیست را بررسی کنید:
  - همه experimentهای `RUNNING` نمایش داده می‌شوند،
  - experimentهایی که `end_at` آن‌ها داخل بازه retro فعلی است نیز نمایش داده می‌شوند.
- اگر این هفته فقط `SPECIAL_CAUSE` ثبت کرده باشید، experiment جدیدی ساخته نمی‌شود.

### Glossary
از همان جدول واژگان مشترک EN/FA در بخش EN استفاده کنید تا ترجمه اصطلاحات تیم ثابت بماند.

# راهنمای مدیر سیستم (Admin)
Documentation HQ: [README](../README.md)

این راهنما با رفتار فعلی کد هم‌راستا است (`streamlit_app/app.py`، `streamlit_app/src/ui/*`، `streamlit_app/src/crud.py`، `streamlit_app/src/domain/*`).

## ۱. RBAC و قواعد تغییر داده

نقش‌ها:
- `admin`: دید کامل سازمان، مدیریت کاربران/چرخه‌ها، اختیار ویرایش گسترده.
- `manager`: دید و اختیار تغییر در محدوده افراد مستقیم زیرمجموعه، همراه با مسئولیت پایش هفتگی تیم، مربی‌گری و انضباط Ritual.
- `member`: اجرا و به‌روزرسانی در محدوده شخصی.

تفکیک مهم direct-report و same-team:
- `direct-report`: مالک نود مستقیما به همان مدیر گزارش می‌دهد (`owner.manager_id == manager.id`).
- `same-team`: مالک نود با مدیر `team_id` مشترک دارد، اما ممکن است به مدیر دیگری گزارش دهد.
- دلیل این تفکیک: برای هماهنگی تیمی، دید وسیع‌تر لازم است؛ اما اختیار ویرایش باید نزد خط‌مدیریتی پاسخ‌گو بماند.
- سیاست فعلی مدیر:
  - `READ`: آیتم‌های خود + direct-report + same-team.
  - `UPDATE/DELETE`: آیتم‌های خود + direct-report (فقط `manager-of-owner`).

قید اصلی تغییرات:
- عملیات نوشتنی وابسته به Goal از کنترل مجوز (`_authorize_goal_mutation`) عبور می‌کند.
- عملیات نوشتنی هم‌راستاسازی Objective (`create_alignment` / `delete_alignment`) نیز قبل از commit کنترل مجوز می‌شوند.
- در مسیر خواندن داده برای AI/Inspector می‌توان از `get_node(..., actor_username=...)` برای اعمال `READ` استفاده کرد.

## ۲. سطوح کنترلی ادمین

سطوح اصلی مدیریت در UI:
- دیالوگ `Admin Panel`: مدیریت کاربران، ریست رمز، عملیات چرخه، و بررسی `AI Health`.
- `Atlas Workspace`: انتخاب scope بر اساس نقش (`All Users` برای ادمین)، Focus Map و Inspector.
- `Strategic Dashboard`: شاخص‌های تجمیعی و نمایش ریسک تیم.

### اطلس به عنوان Cockpit ادمین

در سایدبار Focus Map (در scope ادمین) می‌توانید:
- `AI Progress Sync`
- `Preview mode (no writes)`
- `Apply AI overall score to KR progress`
- `Max KR progress delta`
- `Allow progress decreases`
- `Undo Last AI Progress Apply` (محدود به بازه زمانی)

از این cockpit برای همگام‌سازی کنترل‌شده استفاده کنید، نه به‌روزرسانی کور.

### معماری Runtime برای اپراتور ادمین

توپولوژی پیشنهادی تولید:
- `okr` (Streamlit UI)
- `backend-api` (کنترل‌پلین داخلی برای mutation + timer + job)
- `backend-worker` (اجرای async برای AI/PDF)
- پایگاه‌داده مشترک Supabase PostgreSQL

نکات wiring:
- `OKR_BACKEND_API_URL` از `okr` به `backend-api`
- `OKR_BACKEND_SERVICE_TOKEN` باید بین caller و backend-api یکسان باشد
- `OKR_BACKEND_PROXY_MUTATIONS=true` باعث می‌شود جریان‌های نوشتنی فرانت‌اند (نودها، تایمر، کاربران/چرخه‌ها/تیم‌ها، و تغییرات Learning Loop) از مسیر backend API انجام شوند
- پورت backend-api باید داخلی/خصوصی بماند و عمومی expose نشود

رفتار فنی فعلی:
- مسیرهای read-heavy هنوز در خود Streamlit اجرا می‌شوند (`Streamlit -> src/crud.py -> DB`).
- مسیرهای نوشتنی فرانت‌اند (نودها، timer، مدیریت کاربران/چرخه‌ها/تیم‌ها، Learning Loop و alignment) از backend API عبور می‌کنند؛ در Production رفتار پیش‌فرض fail-closed است و fallback محلی فقط با `OKR_ALLOW_LOCAL_BACKEND_FALLBACK=true` فعال می‌شود.
- عملیات سنگین AI/PDF به‌صورت async توسط `backend-worker` و جدول `async_job` اجرا می‌شود.

## ۳. قواعد چرخه‌حیات و Rollup که باید رعایت شوند

برای Objective و KR:
- وضعیت‌ها: `DRAFT`، `ACTIVE`، `GRADING`، `ARCHIVED`.
- فعال‌سازی Objective بدون حداقل یک KR مجاز نیست.
- تغییر وضعیت Objective به KRهای فرزند cascade می‌شود.
- آیتم‌های `DRAFT` از rollup امتیاز حذف می‌شوند.

مدل امتیازدهی:
- امتیاز KR از `start_value`، `current_value`، `target_value` و `metric_type` محاسبه می‌شود.
- Score mode در Objective می‌تواند `UNWEIGHTED` یا `WEIGHTED` باشد.
- Rollup Goal از پیشرفت/وزن Objectiveها محاسبه می‌شود.

## ۴. روتین هفتگی ادمین

1. چرخه فعال و تخصیص کاربران را تایید کنید.
2. Strategic Dashboard را باز کرده و این شاخص‌ها را بررسی کنید:
   - `Data Hygiene`
   - `Avg Confidence`
   - `At-Risk KRs`
   - `Overdue Tasks`
   - `At Risk Tasks`
3. لیست `At-Risk Key Results` و `Overdue Tasks` را مرور کنید.
4. با Scope و Branch Lens در Atlas، نقطه اصلاح دقیق را پیدا کنید.
5. در صورت نیاز، `AI Progress Sync` را ابتدا در حالت Preview اجرا کنید.
6. در `Leadership Insights -> Strategy Pulse`، سیگنال‌های burnout/شکاف را مرور و اقدام مربی‌گری یا بازتوزیع بار را هدایت کنید.

### Playbook پایش تیم برای مدیر نمونه (گام‌به‌گام)

این بخش برای اعتبارسنجی رفتار نقش `manager` در محیط sandbox/UAT با حساب‌های dummy است.

برای مدل کامل اجرای نقش مدیر (visibility، ماتریس مجوز، زمان‌بندی گزارش‌ها و اسکریپت UAT)، از این سند استفاده کنید:
- [راهنمای عملیاتی مدیر](MANAGER_PLAYBOOK_FA.md)

پیش‌نیازهای setup (توسط ادمین):
1. یک کاربر dummy با نقش `manager` و `team_id` مشخص بسازید.
2. ۳ تا ۵ عضو dummy بسازید و `manager_id` هرکدام را به همان مدیر نمونه وصل کنید.
3. یک چرخه فعال داشته باشید و برای هر عضو حداقل یک Goal -> Objective -> KR ایجاد کنید.
4. Objective/KRها را از `DRAFT` به `ACTIVE` منتقل کنید تا در rollupهای پایش دیده شوند.

روند پایش هفتگی (توسط مدیر نمونه):
1. خط مبنا (ابتدای هفته): `Leadership Insights -> Execution` را باز کنید، فیلتر تیم مدیر را اعمال کنید، شاخص‌های `Data Hygiene`، `Avg Confidence`، `At-Risk KRs`، `Overdue Tasks`، `At Risk Tasks` را ثبت کنید.
2. کنترل میان‌هفته: `At-Risk Key Results` و `Overdue Tasks` را مرور کنید؛ در Atlas با `Branch` lens گره‌های مسئله‌دار را باز کنید و مالکیت، deadline یا فیلدهای متریک KR را اصلاح کنید.
3. حاکمیت Ritual (پایان هفته): تکمیل `Weekly Ritual` همه direct reportها را تایید کنید (مرحله ۲ check-in KR + مرحله ۳ برنامه هفته بعد). از `RetroBox` فقط به‌عنوان شواهد بازبینی استفاده کنید، نه مسیر به‌روزرسانی.
4. گذر ریسک استراتژیک: `Strategy Pulse` را باز کنید، burnout و ghost-goal gap را بررسی کنید، سپس پیش‌بینی AI و اقدامات اصلاحی را تولید کنید.
5. مربی‌گری و escalation: موارد پرریسک را به اقدام صریح تیمی تبدیل کنید (owner + due date + اثر مورد انتظار روی متریک) و blockerهای سیستمی را به ادمین escalate کنید.
6. بستن شواهد: `Weekly Report` را export کنید و یک artifact قابل اشتراک برای مرور هفتگی مدیر نگه دارید.

مرز اختیارات مدیر نمونه:
1. دامنه مجاز: سلسله‌مراتب direct report و context تیم تخصیص‌داده‌شده.
2. خارج از دامنه: ویرایش بین‌تیمی/سراسری که در اختیار `admin` است.

Definition of done برای کیفیت پایش مدیر:
1. نرخ تکمیل Ritual برای direct reportها در هر هفته ۱۰۰٪ باشد.
2. هیچ KR در حالت ACTIVE بدون check-in تازه (بیش از آستانه سیاست) باقی نماند.
3. برای هر KR پرریسک، owner مشخص، اقدام اصلاحی، و تاریخ پیگیری ثبت شده باشد.

## ۵. حاکمیت Ritual، Retro و Report

تفکیک فرآیند:
- `Weekly Ritual` مسیر اصلی به‌روزرسانی KR (check-in + برنامه هفتگی) است.
- متن retrospective در مرحله ۱ Ritual ثبت می‌شود.
- `RetroBox` فقط نمایش retrospectiveهای ذخیره‌شده (شخصی/تیمی) است و check-in KR نیست.

زمان‌بندی گزارش:
- `Daily Report`: پنجره امروز.
- `Weekly Report`: پنجره ۷ روز اخیر.
- هر دو بر اساس Work Log هستند و خروجی‌پذیرند (مسیر PDF با `pdfshift` و fallback به HTML).

## ۶. Playbook رخدادها

### الف) KR قدیمی/ناسازگار به نظر می‌رسد
1. KR را در Inspector باز کنید و `start/current/target` و metric type را بررسی کنید.
2. وجود check-in اخیر را در Weekly Ritual مرحله ۲ تایید کنید.
3. در صورت نیاز KR را دستی اصلاح کنید و Dashboard را دوباره بررسی کنید.

### ب) سلسله‌مراتب یا تخصیص اشتباه است
1. Task را در Inspector باز کنید.
2. فیلدهای assignee/schedule را اصلاح کنید.
3. اگر اتصال والد اشتباه است، Task را زیر KR صحیح بازسازی/منتقل کنید.

### ج) جهش ریسک تیم (overdue/at-risk زیاد)
1. از لیست‌های Dashboard برای تفکیک مالک و ناحیه مشکل استفاده کنید.
2. در Atlas با Branch Lens هر شاخه هدف را جداگانه اصلاح کنید.
3. از مدیران بخواهید Weekly Ritual را کامل کنند و confidence/comment با کیفیت ثبت کنند.

## ۷. محدودیت‌های فعلی (مهم)

در UI فعلی وجود ندارد:
- صفحه مستقل `Global Sync Status` یا `Refresh All`،
- گردش‌کار ویرایش مستقیم Work Log با آیکون مداد (مسیر موجود: حذف و ثبت مجدد)،
- به‌روزرسانی KR از طریق RetroBox (RetroBox نمایش‌محور است).

نکته تایم‌لاین:
- Project Timeline اکنون به چرخه فعال (`active_cycle_id`) محدود است و با دامنه نقش‌ها (member/manager/admin) فیلتر می‌شود.

## ۸. چک‌لیست سریع ممیزی

1. درستی محدوده نقش‌ها (admin/manager/member).
2. درستی چرخه فعال و عدم هم‌پوشانی غیرمجاز.
3. انتقال آیتم‌های DRAFT به ACTIVE هنگام شروع اجرا.
4. نرخ استفاده تیم از Weekly Ritual برای check-in KR.
5. مرور روند ریسک Dashboard و اقدام اصلاحی.
6. استفاده از AI sync با رویکرد Preview-first.

## ۹. ماتریس ابزارهای ادمین: فرآیند و زمان‌بندی

نکته زمان‌بندی:
- این ریتم، پیشنهاد حاکمیتی است و برنامه روزهای ثابت را اجبار نمی‌کند.

| ابزار / قابلیت | مالک اصلی | فرآیند | زمان پیشنهادی | تناوب | خروجی مورد انتظار |
|---|---|---|---|---|---|
| Admin Panel | ادمین | مدیریت کاربر، ریست رمز و کنترل‌های عملیاتی. | پنجره‌های onboarding/offboarding و رخدادهای اضطراری. | موردی. | بهداشت دسترسی و تداوم عملیات. |
| Manage Cycles | ادمین | ایجاد/فعال‌سازی/غیرفعال‌سازی چرخه‌ها و تایید چرخه فعال. | آماده‌سازی ابتدای فصل و انتقال پایان فصل. | فصلی (یا موردی). | مرز زمانی صحیح چرخه و دامنه فعال درست. |
| Strategic Dashboard | ادمین / مدیر | مرور KPIها، KRهای پرریسک، overdueها و توزیع تیم. | جلسه راهبری هفتگی؛ میان‌هفته در صورت افزایش ریسک. | هفتگی + رویدادمحور. | برنامه مداخله اولویت‌بندی‌شده. |
| Strategy Pulse (Leadership Insights) | ادمین / مدیر | مرور ریسک burnout، شکاف استراتژی، پیش‌بینی AI و شواهد کارنامه دستاورد برای هدایت مداخله/مربی‌گری. | بعد از مرور سیگنال‌های اجرایی Strategic Dashboard. | هفتگی + هنگام جهش ریسک. | تصمیم ظرفیت پیش‌دستانه و برنامه مربی‌گری رهبری. |
| Team Filter (Dashboard) | ادمین / مدیر | ایزوله‌سازی تیم/افراد برای تحلیل علت ریشه‌ای. | حین بازبینی داشبورد. | هر جلسه بازبینی. | مربی‌گری هدفمند و پاسخگویی دقیق. |
| Atlas Inspector (اصلاح داده) | ادمین / مدیر | اصلاح متریک KR، وضعیت چرخه‌حیات، تخصیص و تاریخ‌ها. | بلافاصله پس از کشف ناهماهنگی. | موردی (اغلب هفتگی). | داده عملیاتی پاک و قابل دفاع. |
| AI Progress Sync (Atlas) | ادمین / مدیر | preview -> apply محدود -> verify -> undo در صورت نیاز. | پس از refresh تحلیل یا قبل از check-in مدیریتی. | هفتگی یا موردی. | همگام‌سازی کنترل‌شده تحلیل/پیشرفت در سطح سازمان. |
| AI Team Coach (Dashboard) | ادمین / مدیر | تولید راهنمای مربی‌گری از داده تجمیعی تیم. | پس از مرور داشبورد. | هفتگی. | اولویت‌های اقدام، quick win و هشدار کلیدی. |
| پایش انضباط Weekly Ritual | مدیر / ادمین | بررسی تکمیل Ritual و check-inهای KR توسط تیم. | پایان چرخه راهبری هفتگی. | هفتگی. | ریتم قابل اتکا برای check-in و پیش‌بینی بهتر. |
| RetroBox (retros تیم) | مدیر / ادمین | مرور بازتاب‌های تیمی و شناسایی blockerهای سیستمی. | بعد از Ritual و در جلسه تیم. | هفتگی. | حلقه بهبود مستند و فهرست موانع. |
| Weekly Report (شواهد تیم) | ادمین / مدیر | استفاده از خروجی گزارش برای بازبینی و escalation مبتنی بر داده. | پایان هفته، پس از Ritual. | هفتگی. | artifact قابل اشتراک برای تصمیم‌گیری. |
| Project Timeline | ادمین / مدیر | اعتبارسنجی فشار زمان‌بندی و خوشه‌های deadline در تسک‌ها. | برنامه‌ریزی اسپرینت و triage رخدادها. | ۱ تا ۲ بار در هفته. | دید ریسک deadline برای تصمیم ظرفیت. |

## ۱۰. Secrets و پیکربندی Runtime

برای پایداری تولید:
1. اطلاعات محرمانه AI را فقط در Streamlit secrets یا env امن نگه دارید و هرگز داخل repository قرار ندهید.
2. `AI_PROVIDER` را صریح تنظیم کنید (`gemini` یا `openai_compatible`) و از مسیر `Admin Panel -> AI Health` یا دستور `python streamlit_app/scripts/ai_provider_health_check.py` وضعیت را بررسی کنید.
3. اگر Gemini استفاده می‌کنید، `GEMINI_API_KEY` را تنظیم کنید.
4. برای خروجی PDF فقط `PDF_METHOD=pdfshift` را با کلید معتبر PDFShift در secrets تنظیم کنید.
5. در نبود پیکربندی PDF، خروجی HTML همچنان در دسترس است.
6. در هر محیط فقط یک مسیر deployment/pdf را فعال نگه دارید (از ترکیب همزمان pipelineها پرهیز کنید).
7. حالت fail-fast اختیاری: با `OKR_STRICT_RUNTIME_PREFLIGHT=1` در صورت خطای بحرانی runtime، startup برنامه متوقف می‌شود.



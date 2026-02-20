# راهنمای قابلیت‌های هوش مصنوعی (AI)
Documentation HQ: [README](../README.md)

این راهنما قابلیت‌های AI را که در کد فعلی پیاده‌سازی شده‌اند مستند می‌کند (`streamlit_app/src/services/ai_service.py`، `streamlit_app/src/ui/components.py`، `streamlit_app/src/ui/dialogs.py`).

## ۱. AI دقیقا کجا در UI وجود دارد

AI در این بخش‌ها استفاده می‌شود:
- `Inspector` (تحلیل KR/Objective با `analyze_node`).
- مرحله ۱ `Weekly Ritual` (تولید خلاصه هفتگی).
- `Weekly Report` (تولید executive brief).
- سایدبار `Atlas -> Focus Map` (کنترل‌های `AI Progress Sync`).
- `Leadership Insights -> Execution` (بخش `AI Team Coach` برای مدیر/ادمین).
- `Leadership Insights -> Strategy Pulse` (burnout، شکاف استراتژی، پیش‌بینی AI، کارنامه دستاورد PDF).

## ۱.۱ مسیر اجرای Runtime

درخواست‌های AI می‌توانند در دو حالت اجرا شوند:
- حالت مستقیم: Streamlit در همان پروسه provider را صدا می‌زند.
- حالت backend-assisted (پیشنهادی): Streamlit درخواست `ai.generate_json` را به `backend-api` می‌فرستد و `backend-worker` آن را async اجرا می‌کند.

این تفکیک باعث کاهش فشار روی rerunهای Streamlit و پایداری بهتر در عملیات سنگین AI می‌شود.

جزئیات معماری مرتبط:
- با `OKR_BACKEND_PROXY_MUTATIONS=true`، نوشتن داده‌هایی که خروجی AI را persist می‌کنند (مثل فیلدهای تحلیل KR) می‌تواند از endpointهای mutation در backend API عبور کند.
- در خطاهای backend، رفتار پیش‌فرض Production به‌صورت fail-closed است؛ fallback محلی فقط با `OKR_ALLOW_LOCAL_BACKEND_FALLBACK=true` فعال می‌شود.

## ۲. قابلیت‌های پیاده‌سازی‌شده AI

### الف) تحلیل گره (Magic Wand / Run Analysis)

دامنه:
- عمدتا برای Key Result، با زمینه مرتبط Objective.

خروجی‌های معمول:
- `efficiency_score`
- `effectiveness_score`
- `overall_score`
- `gap_analysis`
- `proposed_tasks`
- خلاصه کوتاه و هشدارها

نحوه اعمال:
- تحلیل فقط به‌صورت درخواستی اجرا می‌شود.
- نتیجه در فیلد تحلیل KR ذخیره می‌شود.
- هیچ تغییر ساختاری خودکار بدون اقدام صریح کاربر اعمال نمی‌شود.

### ب) خلاصه هفتگی AI

در این بخش‌ها:
- Weekly Ritual (مرحله Review Week)
- Weekly Report

مبنای ورودی:
- متن Work Log
- مجموع زمان
- تعداد تسک تکمیل‌شده
- تعداد KR به‌روزرسانی‌شده

شکل خروجی:
- خلاصه markdown
- لیست highlights
- یک جمله focus analysis

### ج) AI Progress Sync در Atlas

محل:
- Focus Map sidebar در بخش `AI`.

قابلیت‌ها:
- به‌روزرسانی تحلیل AI برای KRهای قابل مشاهده.
- گزینه `Apply AI overall score to KR progress`.
- کنترل سیاست: preview mode، سقف delta، اجازه/عدم اجازه کاهش.
- امکان Undo برای اعمال اخیر پیشرفت.

رفتار مهم:
- KRهای DRAFT در bulk sync نادیده گرفته می‌شوند.
- نوشتن پیشرفت فقط وقتی انجام می‌شود که کاربر sync را در حالت write اجرا کند.

### د) Suggested Next Task

دو منبع وجود دارد:
- رتبه‌بندی محلی Atlas (`Suggested Next`).
- پیشنهاد اختیاری AI (`suggest_critical_task`) در جریان AI sync.

هدف:
- انتخاب یک تسک بعدی با اولویت بالا بر اساس فوریت، پیشرفت و زمینه استراتژیک.

### ه) AI Team Coach (Dashboard)

برای manager/admin در Strategic Dashboard فعال است.

بر اساس شاخص‌های تجمیعی تیم، این موارد را می‌دهد:
- امتیاز/رتبه سلامت کلی
- تحلیل ابعادی (بهره‌وری، deadline، هم‌راستایی، توازن بار، مومنتوم)
- اولویت‌های اصلی، quick wins و هشدار مهم

### و) Strategy Pulse (Leadership Insights)

محل:
- `Strategic Dashboard` را باز کنید و در دیالوگ `Leadership Insights` به تب `Strategy Pulse` بروید.

قابلیت‌ها:
- امتیازدهی ریسک burnout از سیگنال effort/output (`calculate_burnout_risk`).
- شناسایی شکاف هدف/استراتژی برای Objectiveهای فعال (`detect_strategy_gaps`).
- تولید پیش‌بینی AI (`generate_predictive_outlook`).
- تولید کارنامه دستاورد و خروجی PDF (`generate_achievement_portfolio`، `generate_achievement_portfolio_pdf`).

کاربرد رهبری مدیر:
- پایش تیم: کشف زودهنگام ریسک بارکاری و Objectiveهای متوقف.
- تیم‌سازی/مربی‌گری: استفاده از پیشنهادهای اصلاحی و شواهد کارنامه در 1:1 و مرور تیم.

## ۳. قواعد Human-in-the-Loop

- پیشنهاد AI تا زمان اقدام کاربر صرفا پیشنهادی است.
- تغییر پیشرفت KR از مسیر AI نیازمند اقدام صریح کاربر است.
- ویرایش دستی KR و check-in همچنان مسیر اصلی و قابل اتکا است.

## ۴. نیازمندی‌های کیفیت داده

کیفیت خروجی AI به این موارد وابسته است:
- عنوان و توضیح دقیق KR
- به‌روز بودن مقادیر متریک KR (`start/current/target`)
- خلاصه‌های تمیز در Work Log
- تکمیل منظم Weekly Ritual (confidence + comment)

ضعف در این ورودی‌ها باعث توصیه‌های عمومی و کم‌کیفیت می‌شود.

## ۵. محدودیت‌ها و قابلیت‌های غیرموجود (نسخه فعلی)

در پیاده‌سازی فعلی تضمین نمی‌شود:
- خروجی استنادی شماره‌دار در همه پاسخ‌ها،
- بازآموزی خودکار پس‌زمینه از تمام ویرایش‌های کاربر،
- اجرای خودکار تسک‌های پیشنهادی AI،
- پنل کنترل جهانی AI جدا از Atlas/Dashboard.

## ۶. الگوهای پرامپت عملی

در Inspector از پرامپت کوتاه و محدود استفاده کنید:
- «مهم‌ترین مانع رسیدن این KR به target چیست؟»
- «در ۳ روز آینده کدام تسک بیشترین اثر را دارد؟»
- «با توجه به effort ثبت‌شده، پیشرفت فعلی واقع‌بینانه است؟»

برای Team Coach:
- «سه مداخله اصلی هفته بعد را با tradeoff توضیح بده.»

## ۷. مرزهای دسترسی RBAC در AI

- در فراخوانی‌های UI برای تحلیل، هویت actor به `analyze_node` پاس می‌شود.
- `analyze_node` در صورت وجود actor، داده گره را از مسیر مجاز `get_node(..., actor_username=...)` می‌خواند.
- `get_node` قبل از بازگشت داده، مجوز `READ` را روی Goal بالادستی کنترل می‌کند.
- ذخیره نتایج AI همچنان از مسیر mutation مجاز (مثل `update_key_result(..., actor_username=...)`) عبور می‌کند.
- ایجاد/حذف alignment هم به صورت مستقل با مجوز mutation کنترل می‌شود.

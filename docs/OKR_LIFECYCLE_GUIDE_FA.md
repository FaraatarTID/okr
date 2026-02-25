# راهنمای چرخه حیات OKR
Documentation HQ: [README](../README.md)

این راهنما با منطق چرخه‌حیات پیاده‌سازی‌شده در `streamlit_app/src/models.py`، `streamlit_app/src/domain/lifecycle.py` و `streamlit_app/src/crud.py` هم‌راستا است.

## مدل مفهومی (Goal، Objective، KR)

- `Goal`: نیت، جهت، و تغییر استراتژیک موردنظر (`چرا + به کجا`).
- `Objective`: تعهد خروجی در بازه چرخه (`چه چیزی تغییر می‌کند`).
- `KR`: خط اثبات عددی (`چطور تغییر را می‌سنجیم`).

نتیجه عملی:
- پیشرفت Objective از پیشرفت KRها محاسبه می‌شود.
- پیشرفت Goal از پیشرفت Objectiveها محاسبه می‌شود.
- شرط فعال‌سازی Objective داشتن حداقل یک KR است، چون Objective به‌تنهایی self-scoring نیست.

## ۱. وضعیت‌های چرخه حیات

برای Objective و Key Result چهار وضعیت وجود دارد:
- `DRAFT`
- `ACTIVE`
- `GRADING`
- `ARCHIVED`

کارکرد وضعیت‌ها:
- `DRAFT`: وضعیت برنامه‌ریزی؛ در rollup پیشرفت لحاظ نمی‌شود.
- `ACTIVE`: وضعیت اصلی اجرا و پایش.
- `GRADING`: وضعیت بازبینی و جمع‌بندی پایان دوره.
- `ARCHIVED`: وضعیت بایگانی/بسته‌شده (در صورت نیاز قابل بازگشت به ACTIVE).

## ۲. گذارهای مجاز

نقشه گذار فعلی:
- `DRAFT -> ACTIVE`
- `ACTIVE -> GRADING` یا `ACTIVE -> DRAFT`
- `GRADING -> ARCHIVED` یا `GRADING -> ACTIVE`
- `ARCHIVED -> ACTIVE`

اعتبار گذارها در منطق lifecycle کنترل می‌شود.

## ۳. قواعد کلیدی اعمال‌شده

- Objective بدون حداقل یک KR نمی‌تواند به `ACTIVE` برود.
- تغییر وضعیت Objective به KRهای فرزند cascade می‌شود.
- Objective/KRهای `DRAFT` از rollup هدف و Goal حذف می‌شوند.

## ۴. گراف هم‌راستایی (Objective به Objective)

علاوه بر سلسله‌مراتب Goal->Objective->KR، می‌توان بین Objectiveها لینک هم‌راستایی ایجاد کرد.

رفتار:
- لینک‌ها جهت‌دار هستند.
- لینک‌هایی که چرخه ایجاد کنند مسدود می‌شوند.
- مدیریت لینک‌ها در Objective Inspector و بخش `Organizational Alignment` انجام می‌شود.
- ایجاد/حذف لینک‌ها نیازمند مجوز تغییر (mutation authorization) روی Goalهای درگیر است.

## ۵. حالت‌های امتیازدهی و Rollup

حالت امتیازدهی Objective:
- `UNWEIGHTED`: سهم مساوی برای همه KRها.
- `WEIGHTED`: وزن KRها روی امتیاز Objective اثر می‌گذارد.

ورودی امتیاز KR:
- `start_value`، `current_value`، `target_value`، `metric_type`.

Rollup Goal:
- از پیشرفت Objectiveها (با وزن Objective) محاسبه می‌شود.

## ۶. محل مدیریت چرخه حیات در UI

در Inspector:
- بخش `Lifecycle & Closing`: تنظیم وضعیت و final reflection.
- Objective inspector: مدیریت لینک‌های alignment و score mode.
- KR inspector: مدیریت وزن KR و فیلدهای متریک.

## ۷. راهنمای Final Reflection

در فیلد `Final Reflection` برای Objective/KR این موارد را ثبت کنید:
- خلاصه نتیجه,
- مهم‌ترین موانع,
- تصمیم‌های دوره بعد.

این کار باعث می‌شود استدلال پایان‌دوره برای برنامه‌ریزی بعدی قابل ممیزی باشد.
